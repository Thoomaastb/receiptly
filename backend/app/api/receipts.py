import calendar
import uuid
from datetime import date

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy import exists, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models.bucket import Bucket, BucketAccess, BucketVisibility
from app.models.item import Item
from app.models.merchant import Merchant
from app.models.receipt import Receipt, ReceiptStatus
from app.models.user import User
from app.schemas.receipt import (
    ItemCreate,
    ItemResponse,
    ItemUpdate,
    ReceiptDetail,
    ReceiptListItem,
    ReceiptUpdate,
    ReceiptUploadResponse,
)
from app.services.bucket_access import visible_bucket_ids_query
from app.services.storage import (
    FileTooLargeError,
    UnsupportedFileTypeError,
    store_upload,
)

router = APIRouter(prefix="/receipts", tags=["receipts"])

_RECEIPT_DETAIL_OPTIONS = (selectinload(Receipt.merchant), selectinload(Receipt.items))


def _normalize_merchant_name(name: str) -> str:
    return " ".join(name.strip().lower().split())


async def _get_or_create_merchant(db: AsyncSession, name: str) -> Merchant:
    normalized = _normalize_merchant_name(name)
    result = await db.execute(select(Merchant).where(Merchant.normalized_name == normalized))
    merchant = result.scalar_one_or_none()
    if merchant is None:
        merchant = Merchant(name=name.strip(), normalized_name=normalized)
        db.add(merchant)
        await db.flush()
    return merchant


def _add_months(d: date, months: int) -> date:
    month_index = d.month - 1 + months
    year = d.year + month_index // 12
    month = month_index % 12 + 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


async def _assert_bucket_writable(db: AsyncSession, bucket_id: uuid.UUID, user: User) -> Bucket:
    """
    Prüft Schreibzugriff auf den Bucket: Owner darf immer, sonst nur mit 'edit' in
    bucket_access. Bei privaten Buckets ist fehlender Zugriff wie 'nicht gefunden'
    zu behandeln (Sichtbarkeit inkl. Existenz), nicht wie 403.
    """
    result = await db.execute(select(Bucket).where(Bucket.id == bucket_id))
    bucket = result.scalar_one_or_none()

    if bucket is None or bucket.household_id != user.household_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bucket nicht gefunden")

    if bucket.owner_id == user.id:
        return bucket

    if bucket.visibility == BucketVisibility.TRANSPARENT:
        # Transparent: jeder im Haushalt darf lesen, aber nur mit explizitem 'edit' schreiben
        access = await db.execute(
            select(BucketAccess).where(
                BucketAccess.bucket_id == bucket_id, BucketAccess.user_id == user.id
            )
        )
        grant = access.scalar_one_or_none()
        if grant is None or grant.access_level.value != "edit":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Keine Schreibrechte auf Bucket"
            )
        return bucket

    # Privat: ohne Freigabe ist der Bucket wie nicht vorhanden zu behandeln
    access = await db.execute(
        select(BucketAccess).where(
            BucketAccess.bucket_id == bucket_id, BucketAccess.user_id == user.id
        )
    )
    grant = access.scalar_one_or_none()
    if grant is None or grant.access_level.value != "edit":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bucket nicht gefunden")
    return bucket


@router.post("/upload", response_model=ReceiptUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_receipt(
    bucket_id: uuid.UUID = Form(...),
    file: UploadFile = File(...),
    ocr_text: str | None = Form(default=None),
    ocr_confidence: float | None = Form(default=None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Receipt:
    """
    Nimmt Kamerascan oder Datei-Upload entgegen (PDF, JPG, PNG), inkl. optionalem
    client-seitig erzeugtem OCR-Text (das Originalbild selbst verlässt das Gerät nie).
    receipt_date/total_amount bleiben hier bewusst leer — Struktur-Extraktion aus dem
    OCR-Text übernimmt ein späteres KI-Paket.
    """
    await _assert_bucket_writable(db, bucket_id, user)

    try:
        file_path, thumb_path, content_hash = await store_upload(file, user.household_id)
    except UnsupportedFileTypeError as exc:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail=str(exc))
    except FileTooLargeError as exc:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=str(exc))

    receipt = Receipt(
        user_id=user.id,
        bucket_id=bucket_id,
        file_path=file_path,
        thumb_path=thumb_path,
        content_hash=content_hash,
        status=ReceiptStatus.PENDING,
        currency="EUR",
        ocr_raw_text=ocr_text,
        ocr_confidence=ocr_confidence,
    )
    db.add(receipt)
    await db.commit()
    await db.refresh(receipt)
    return receipt


@router.get("", response_model=list[ReceiptListItem])
async def list_receipts(
    q: str | None = Query(default=None, description="Volltext: Händler, OCR-Text, Artikel"),
    type: str | None = Query(
        default=None, description="Filter: high_value | warranty | needs_review"
    ),
    category: str | None = Query(default=None, description="Merchant-Kategorie"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[Receipt]:
    """
    Belege aus allen für den User sichtbaren Buckets, neueste zuerst. `q` durchsucht
    Händlername, OCR-Rohtext und Artikelnamen (Volltext-Suche laut Produkt-Konzept) über
    exists()-Subqueries statt Joins, damit kein Receipt durch Artikel-Treffer dupliziert wird.
    """
    stmt = (
        select(Receipt)
        .options(*_RECEIPT_DETAIL_OPTIONS)
        .where(Receipt.bucket_id.in_(visible_bucket_ids_query(user)))
    )

    if q and q.strip():
        pattern = f"%{q.strip()}%"
        merchant_match = exists(
            select(Merchant.id).where(
                Merchant.id == Receipt.merchant_id, Merchant.name.ilike(pattern)
            )
        )
        item_match = exists(
            select(Item.id).where(Item.receipt_id == Receipt.id, Item.raw_name.ilike(pattern))
        )
        stmt = stmt.where(
            or_(merchant_match, item_match, Receipt.ocr_raw_text.ilike(pattern))
        )

    if type == "high_value":
        stmt = stmt.where(Receipt.is_high_value.is_(True))
    elif type == "warranty":
        stmt = stmt.where(Receipt.warranty_months.is_not(None))
    elif type == "needs_review":
        stmt = stmt.where(Receipt.status == ReceiptStatus.NEEDS_REVIEW)

    if category:
        stmt = stmt.where(
            exists(
                select(Merchant.id).where(
                    Merchant.id == Receipt.merchant_id, Merchant.category == category
                )
            )
        )

    result = await db.execute(stmt.order_by(Receipt.created_at.desc()))
    return list(result.scalars().all())


@router.get("/{receipt_id}", response_model=ReceiptDetail)
async def get_receipt(
    receipt_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Receipt:
    result = await db.execute(
        select(Receipt)
        .options(*_RECEIPT_DETAIL_OPTIONS)
        .where(Receipt.id == receipt_id, Receipt.bucket_id.in_(visible_bucket_ids_query(user)))
    )
    receipt = result.scalar_one_or_none()
    if receipt is None:
        # Bewusst 404 statt 403 — Bucket-Existenz privater Buckets bleibt verborgen
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Beleg nicht gefunden")
    return receipt


async def _get_writable_receipt(db: AsyncSession, receipt_id: uuid.UUID, user: User) -> Receipt:
    """Wie get_receipt, aber prüft zusätzlich Schreibzugriff auf den Bucket des Belegs."""
    result = await db.execute(
        select(Receipt).where(
            Receipt.id == receipt_id, Receipt.bucket_id.in_(visible_bucket_ids_query(user))
        )
    )
    receipt = result.scalar_one_or_none()
    if receipt is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Beleg nicht gefunden")
    await _assert_bucket_writable(db, receipt.bucket_id, user)
    return receipt


async def _reload_receipt_detail(db: AsyncSession, receipt_id: uuid.UUID) -> Receipt:
    result = await db.execute(
        select(Receipt).options(*_RECEIPT_DETAIL_OPTIONS).where(Receipt.id == receipt_id)
    )
    return result.scalar_one()


@router.patch("/{receipt_id}", response_model=ReceiptDetail)
async def update_receipt(
    receipt_id: uuid.UUID,
    payload: ReceiptUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Receipt:
    """
    Manuelle Bearbeitung der Kernfelder, solange die KI-Struktur-Extraktion aus dem
    OCR-Text noch nicht existiert (siehe Backlog). merchant_name wird per Get-or-Create
    auf einen Merchant-Datensatz gemappt (dedupliziert über normalized_name).
    """
    receipt = await _get_writable_receipt(db, receipt_id, user)

    if payload.receipt_date is not None:
        receipt.receipt_date = payload.receipt_date
    if payload.total_amount is not None:
        receipt.total_amount = payload.total_amount
    if payload.merchant_name is not None:
        merchant = await _get_or_create_merchant(db, payload.merchant_name)
        receipt.merchant_id = merchant.id
    if payload.is_high_value is not None:
        receipt.is_high_value = payload.is_high_value
    if payload.warranty_months is not None:
        receipt.warranty_months = payload.warranty_months

    if receipt.warranty_months is not None and receipt.receipt_date is not None:
        receipt.warranty_expires_at = _add_months(receipt.receipt_date, receipt.warranty_months)

    await db.commit()
    return await _reload_receipt_detail(db, receipt_id)


@router.post(
    "/{receipt_id}/items", response_model=ItemResponse, status_code=status.HTTP_201_CREATED
)
async def add_item(
    receipt_id: uuid.UUID,
    payload: ItemCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Item:
    await _get_writable_receipt(db, receipt_id, user)

    item = Item(
        receipt_id=receipt_id,
        raw_name=payload.raw_name,
        quantity=payload.quantity,
        unit=payload.unit,
        unit_price=payload.unit_price,
        total_price=payload.total_price,
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item


@router.patch("/{receipt_id}/items/{item_id}", response_model=ItemResponse)
async def update_item(
    receipt_id: uuid.UUID,
    item_id: uuid.UUID,
    payload: ItemUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Item:
    await _get_writable_receipt(db, receipt_id, user)

    result = await db.execute(
        select(Item).where(Item.id == item_id, Item.receipt_id == receipt_id)
    )
    item = result.scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artikel nicht gefunden")

    if payload.raw_name is not None:
        item.raw_name = payload.raw_name
    if payload.quantity is not None:
        item.quantity = payload.quantity
    if payload.unit is not None:
        item.unit = payload.unit
    if payload.unit_price is not None:
        item.unit_price = payload.unit_price
    if payload.total_price is not None:
        item.total_price = payload.total_price

    await db.commit()
    await db.refresh(item)
    return item


@router.delete("/{receipt_id}/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_item(
    receipt_id: uuid.UUID,
    item_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    await _get_writable_receipt(db, receipt_id, user)

    result = await db.execute(
        select(Item).where(Item.id == item_id, Item.receipt_id == receipt_id)
    )
    item = result.scalar_one_or_none()
    if item is not None:
        await db.delete(item)
        await db.commit()
