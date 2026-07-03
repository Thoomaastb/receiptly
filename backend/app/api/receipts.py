import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models.bucket import Bucket, BucketAccess, BucketVisibility
from app.models.receipt import Receipt, ReceiptStatus
from app.models.user import User
from app.schemas.receipt import ReceiptDetail, ReceiptListItem, ReceiptUploadResponse
from app.services.bucket_access import visible_bucket_ids_query
from app.services.storage import (
    FileTooLargeError,
    UnsupportedFileTypeError,
    store_upload,
)

router = APIRouter(prefix="/receipts", tags=["receipts"])


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
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> list[Receipt]:
    """Belege aus allen für den User sichtbaren Buckets, neueste zuerst."""
    result = await db.execute(
        select(Receipt)
        .where(Receipt.bucket_id.in_(visible_bucket_ids_query(user)))
        .order_by(Receipt.created_at.desc())
    )
    return list(result.scalars().all())


@router.get("/{receipt_id}", response_model=ReceiptDetail)
async def get_receipt(
    receipt_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Receipt:
    result = await db.execute(
        select(Receipt).where(
            Receipt.id == receipt_id, Receipt.bucket_id.in_(visible_bucket_ids_query(user))
        )
    )
    receipt = result.scalar_one_or_none()
    if receipt is None:
        # Bewusst 404 statt 403 — Bucket-Existenz privater Buckets bleibt verborgen
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Beleg nicht gefunden")
    return receipt
