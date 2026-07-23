from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.rate_limit import rate_limit
from app.database import get_db
from app.models.receipt import Receipt
from app.schemas.receipt_share import PublicReceiptShare
from app.services.audit import record_event
from app.services.receipt_shares import consume_share_for_file_access, resolve_valid_share_readonly

# Cross-Modul-Import eines `_`-präfixierten Namens — unüblich, aber nicht präzedenzlos:
# app/api/webauthn.py importiert bereits `_finalize_first_factor` aus app/api/auth.py. Die
# Alternative (Verschieben in ein eigenes Konstanten-Modul) hätte an dieser Datei-Kante keinen
# echten Mehrwert, da _CONTENT_TYPE_BY_EXTENSION nirgends sonst als in receipts.py gebraucht wird.
from app.api.receipts import _CONTENT_TYPE_BY_EXTENSION

router = APIRouter(prefix="/share", tags=["share"])


def _not_valid() -> HTTPException:
    """
    Ein einziger Fehlerpfad für JEDEN Ungültigkeits-Grund (unbekannter Token, abgelaufen,
    widerrufen, verbrauchter Einmal-Link, Beleg gelöscht, Datei fehlt) — macht es
    strukturell unmöglich, dass die Zweige später auseinanderdriften und dem anonymen
    Aufrufer unterscheidbare Information liefern.
    """
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Link nicht gültig")


@router.get(
    "/{token}",
    response_model=PublicReceiptShare,
    dependencies=[Depends(rate_limit("share_view", limit=30, window_seconds=60))],
)
async def get_shared_receipt(token: str, db: AsyncSession = Depends(get_db)) -> PublicReceiptShare:
    """
    Anonyme Metadaten-Vorschau — rührt `accessed_at`/`access_count` NICHT an (siehe
    `resolve_valid_share_readonly`), damit ein Einmal-Link nicht schon durch das bloße
    Ansehen der Landing-Page verbraucht wird.
    """
    share = await resolve_valid_share_readonly(db, token)
    if share is None:
        raise _not_valid()

    # Nur `merchant` eager laden (für merchant_name), nicht das volle
    # _RECEIPT_DETAIL_OPTIONS-Paar aus receipts.py — `items` wird hier nicht gebraucht.
    result = await db.execute(
        select(Receipt)
        .options(selectinload(Receipt.merchant))
        .where(Receipt.id == share.receipt_id)
    )
    receipt = result.scalar_one_or_none()
    if receipt is None:
        raise _not_valid()

    content_type = _CONTENT_TYPE_BY_EXTENSION.get(Path(receipt.file_path).suffix.lower())
    if content_type is None:
        raise _not_valid()

    return PublicReceiptShare(
        merchant_name=receipt.merchant_name,
        receipt_date=receipt.receipt_date,
        total_amount=receipt.total_amount,
        currency=receipt.currency,
        content_type=content_type,
    )


@router.get(
    "/{token}/file",
    dependencies=[Depends(rate_limit("share_file", limit=30, window_seconds=60))],
)
async def get_shared_receipt_file(
    token: str, request: Request, db: AsyncSession = Depends(get_db)
) -> FileResponse:
    """
    Konsumiert Einmal-Links hier (nicht in der Metadaten-Route, siehe `get_shared_receipt`)
    über ein atomares `UPDATE ... RETURNING` (`consume_share_for_file_access`), das TOCTOU
    zwischen zwei gleichzeitigen Downloads desselben Links ausschließt.
    """
    share = await consume_share_for_file_access(db, token)
    if share is None:
        raise _not_valid()

    result = await db.execute(select(Receipt).where(Receipt.id == share.receipt_id))
    receipt = result.scalar_one_or_none()
    if receipt is None:
        raise _not_valid()

    file_path = Path(receipt.file_path)
    if not file_path.is_file():
        raise _not_valid()

    # commit=True (Default) committet hier bewusst sowohl das UPDATE der Share-Zeile aus
    # consume_share_for_file_access() (die selbst nicht committet) als auch diesen neuen
    # AuditLog-Eintrag in einer gemeinsamen Transaktion.
    await record_event(
        db,
        household_id=share.household_id,
        event_type="share_link_accessed",
        user_id=None,
        request=request,
        metadata={"receipt_id": str(receipt.id), "share_id": str(share.id)},
    )

    return FileResponse(file_path, filename=file_path.name, content_disposition_type="inline")
