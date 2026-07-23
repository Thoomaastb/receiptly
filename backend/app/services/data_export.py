"""
DSGVO-Datenexport (Art. 15/20, siehe concepts/konto-loeschen-datenexport.md 3.1) —
modularer Collector, ein `collect_*()` je Datendomäne. Allowlist-getrieben statt
`SELECT *`: Secrets (password_hash, totp_secret, WebAuthn public_key/sign_count/
credential_id, receipt_shares.token_hash) verlassen das System nie, auch nicht hier
(Konzept 4.3).

build_export_zip() sammelt alle Domänen async und delegiert das eigentliche blockierende
zipfile-Schreiben an asyncio.to_thread() (Konvention siehe app/services/storage.py, dort
die Thumbnail-Generierung) — der Thread-Callable selbst greift nicht mehr auf die
DB/ORM-Objekte zu, alle benötigten Daten werden vorher in reine Python-Strukturen
überführt.
"""

import asyncio
import json
import uuid
import zipfile
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.session import list_user_sessions
from app.models.audit_log import AuditLog
from app.models.household import Household
from app.models.notification import Notification
from app.models.receipt import Receipt
from app.models.receipt_share import ReceiptShare
from app.models.user import User
from app.models.webauthn_credential import WebauthnCredential

_README_TEXT = (
    "receiptly – Datenexport (Art. 15/20 DSGVO)\n"
    "============================================\n\n"
    "Dieses Archiv enthält alle personenbezogenen Daten, die receiptly für dein Konto "
    "gespeichert hat.\n\n"
    "daten.json  – strukturierte Daten (Profil, Belege, Sitzungen, Sicherheits-Ereignisse, "
    "Benachrichtigungen, Beleg-Freigaben, 2FA-/Passkey-Metadaten)\n"
    "originale/  – die von dir hochgeladenen Original-Belegdateien\n\n"
    "Nicht enthalten sind Passwort-Hashes, Zwei-Faktor-Secrets und kryptographische "
    "Schlüssel/Sitzungs-Tokens — diese verlassen receiptly grundsätzlich nie.\n"
)


def _json_default(value: Any) -> Any:
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, Decimal):
        return float(value)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


async def collect_user_profile(db: AsyncSession, user: User) -> dict:
    """User-Stammdaten (Konzept 3.1) — NICHT password_hash, NICHT totp_secret."""
    household = await db.get(Household, user.household_id)
    return {
        "username": user.username,
        "email": user.email,
        "role": user.role.value,
        "household_name": household.name if household else None,
        "created_at": user.created_at,
        "last_login": user.last_login,
    }


async def collect_receipts(
    db: AsyncSession, user: User
) -> tuple[list[dict], list[tuple[Path, str]]]:
    """
    Alle vom User hochgeladenen Belege (user_id = User, über alle Buckets hinweg) inkl.
    Items/custom_fields. Gibt zusätzlich (Quellpfad, Zielname im `originale/`-Ordner) für
    jede noch vorhandene Originaldatei zurück — fehlende Dateien werden übersprungen statt
    einen Fehler zu werfen.
    """
    result = await db.execute(
        select(Receipt)
        .options(selectinload(Receipt.items), selectinload(Receipt.merchant))
        .where(Receipt.user_id == user.id)
        .order_by(Receipt.created_at.asc())
    )
    receipts = list(result.scalars().unique().all())

    receipt_dicts: list[dict] = []
    originals: list[tuple[Path, str]] = []
    for receipt in receipts:
        file_path = Path(receipt.file_path)
        has_original = file_path.is_file()
        arcname = f"originale/{receipt.id}{file_path.suffix}"
        if has_original:
            originals.append((file_path, arcname))

        receipt_dicts.append(
            {
                "id": receipt.id,
                "receipt_date": receipt.receipt_date,
                "total_amount": receipt.total_amount,
                "currency": receipt.currency,
                "shipping_cost": receipt.shipping_cost,
                "discount_amount": receipt.discount_amount,
                "tax_amount": receipt.tax_amount,
                "merchant_name": receipt.merchant_name,
                "category": receipt.category,
                "status": receipt.status.value,
                "is_high_value": receipt.is_high_value,
                "warranty_months": receipt.warranty_months,
                "warranty_expires_at": receipt.warranty_expires_at,
                "custom_fields": receipt.custom_fields,
                "created_at": receipt.created_at,
                "original_file": arcname if has_original else None,
                "items": [
                    {
                        "raw_name": item.raw_name,
                        "quantity": item.quantity,
                        "unit": item.unit,
                        "unit_price": item.unit_price,
                        "total_price": item.total_price,
                        "pack_amount": item.pack_amount,
                        "pack_unit": item.pack_unit,
                    }
                    for item in receipt.items
                ],
            }
        )

    return receipt_dicts, originals


async def collect_sessions(user: User) -> list[dict]:
    """Aktueller Redis-Snapshot (Konzept 3.1) — flüchtig, TTL-gebunden, nie der rohe Token."""
    sessions = await list_user_sessions(user.id, current_raw_token=None)
    return [
        {
            "user_agent": session["user_agent"],
            "ip": session["ip"],
            "created_at": session["created_at"],
            "last_seen_at": session["last_seen_at"],
        }
        for session in sessions
    ]


async def collect_audit_log(db: AsyncSession, user: User) -> list[dict]:
    result = await db.execute(
        select(AuditLog).where(AuditLog.user_id == user.id).order_by(AuditLog.created_at.asc())
    )
    return [
        {
            "event_type": entry.event_type,
            "created_at": entry.created_at,
            "ip": entry.ip,
            "user_agent": entry.user_agent,
        }
        for entry in result.scalars().all()
    ]


async def collect_notifications(db: AsyncSession, user: User) -> list[dict]:
    result = await db.execute(
        select(Notification)
        .where(Notification.user_id == user.id)
        .order_by(Notification.created_at.asc())
    )
    return [
        {
            "category": notification.category,
            "type": notification.type,
            "title": notification.title,
            "body": notification.body,
            "link": notification.link,
            "created_at": notification.created_at,
            "read_at": notification.read_at,
        }
        for notification in result.scalars().all()
    ]


async def collect_receipt_shares(db: AsyncSession, user: User) -> list[dict]:
    """Vom User erstellte Freigabe-Links — NICHT token_hash (Konzept 3.1)."""
    result = await db.execute(
        select(ReceiptShare)
        .where(ReceiptShare.created_by == user.id)
        .order_by(ReceiptShare.created_at.asc())
    )
    return [
        {
            "receipt_id": share.receipt_id,
            "single_use": share.single_use,
            "label": share.label,
            "expires_at": share.expires_at,
            "revoked_at": share.revoked_at,
            "accessed_at": share.accessed_at,
            "access_count": share.access_count,
            "created_at": share.created_at,
        }
        for share in result.scalars().all()
    ]


async def collect_security_metadata(db: AsyncSession, user: User) -> dict:
    """
    Nur Metadaten (Konzept 3.1) — NICHT totp_secret, NICHT Passkey-Public-Keys/sign_count/
    credential_id.
    """
    result = await db.execute(
        select(WebauthnCredential).where(WebauthnCredential.user_id == user.id)
    )
    return {
        "totp_enabled": user.totp_enabled,
        "passkeys": [
            {
                "device_label": credential.device_label,
                "created_at": credential.created_at,
                "last_used_at": credential.last_used_at,
            }
            for credential in result.scalars().all()
        ],
    }


def _write_zip(dest_path: Path, data: dict, originals: list[tuple[Path, str]]) -> None:
    """
    Synchron & blockierend (Datei-I/O über potenziell viele Belege) — vom Aufrufer per
    asyncio.to_thread() ausführen, nie direkt in einer async def (Konvention siehe
    app/services/storage.py).
    """
    with zipfile.ZipFile(dest_path, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "daten.json", json.dumps(data, default=_json_default, indent=2, ensure_ascii=False)
        )
        archive.writestr("README.txt", _README_TEXT)
        for source_path, arcname in originals:
            archive.write(source_path, arcname=arcname)


async def build_export_zip(db: AsyncSession, user: User, dest_path: Path) -> None:
    """Sammelt alle Export-Domänen async, schreibt die ZIP-Datei danach in einem Thread."""
    receipts, originals = await collect_receipts(db, user)
    data = {
        "profil": await collect_user_profile(db, user),
        "belege": receipts,
        "sitzungen": await collect_sessions(user),
        "sicherheitsereignisse": await collect_audit_log(db, user),
        "benachrichtigungen": await collect_notifications(db, user),
        "beleg_freigaben": await collect_receipt_shares(db, user),
        "sicherheit": await collect_security_metadata(db, user),
    }

    await asyncio.to_thread(_write_zip, dest_path, data, originals)
