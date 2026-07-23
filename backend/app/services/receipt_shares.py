"""
Zentrale Gültigkeits-/Verbrauchslogik für `ReceiptShare` (anonyme Freigabe-Links,
siehe app/models/receipt_share.py) — hält sowohl den öffentlichen Router
(app/api/share.py) als auch die Verwaltungs-Endpunkte (app/api/receipts.py) dünn.

Keiner der Schreibpfade hier committet selbst (`create_share`/
`consume_share_for_file_access` enden auf `db.flush()`, nicht `db.commit()`) — die
aufrufende API-Schicht committet erst, nachdem sie im selben Request zusätzlich einen
Audit-Event geschrieben hat, damit beides in einer Transaktion landet (Präzedenzfall:
`services/notifications.py::create_notification` mit `commit=False` in
`services/audit.py::record_event`).
"""

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.receipt_share import ReceiptShare

# Q10: hartes Limit statt Partial-Index/Aufräum-Job — hält die Zeilenzahl pro Beleg klein.
_MAX_ACTIVE_SHARES_PER_RECEIPT = 10

EXPIRY_PRESETS: dict[str, timedelta | None] = {
    "7d": timedelta(days=7),
    "30d": timedelta(days=30),
    "90d": timedelta(days=90),
    "unlimited": None,
}


class ShareLimitExceededError(Exception):
    """10 aktive Links pro Beleg erreicht (Q10)."""


def hash_token(token: str) -> str:
    """
    SHA-256 statt Argon2id (anders als Recovery-Codes/Passwörter) — deterministisch und
    damit über den Unique-Index auf `token_hash` lookupbar, siehe Docstring in
    app/models/receipt_share.py für die volle Begründung.
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _active_conditions(now: datetime) -> tuple:
    """
    Einzige Quelle der Wahrheit für "Link aktuell gültig" — geteilt von Zählung, Liste
    und Konsum-Query, damit die drei nicht auseinanderdriften.
    """
    return (
        ReceiptShare.revoked_at.is_(None),
        (ReceiptShare.expires_at.is_(None)) | (ReceiptShare.expires_at > now),
        (ReceiptShare.single_use.is_(False)) | (ReceiptShare.accessed_at.is_(None)),
    )


async def count_active_shares(db: AsyncSession, receipt_id: uuid.UUID) -> int:
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(func.count())
        .select_from(ReceiptShare)
        .where(ReceiptShare.receipt_id == receipt_id, *_active_conditions(now))
    )
    return result.scalar_one()


async def list_all_shares(db: AsyncSession, receipt_id: uuid.UUID) -> list[ReceiptShare]:
    """
    Volle Historie aller je für diesen Beleg erstellten Links, ohne den
    _active_conditions()-Filter — für die Verwaltungsansicht (GET /receipts/{id}/shares),
    die auch widerrufene/abgelaufene/verbrauchte Links weiter anzeigen soll (siehe
    _share_status()). Ersetzt das frühere list_active_shares(), das nach dieser Änderung
    von nirgends mehr aufgerufen wurde (count_active_shares() bleibt für den 10er-Cap
    unverändert bestehen).
    """
    result = await db.execute(
        select(ReceiptShare)
        .where(ReceiptShare.receipt_id == receipt_id)
        .order_by(ReceiptShare.created_at.desc())
    )
    return list(result.scalars().all())


def _share_status(share: ReceiptShare, now: datetime) -> str:
    """
    Menschenlesbares Spiegelbild von _active_conditions() — dieselbe Präzedenz, nur als
    einzelner Status statt als Boolean-Filter, damit beide nie auseinanderdriften können.
    """
    if share.revoked_at is not None:
        return "revoked"
    if share.expires_at is not None and share.expires_at <= now:
        return "expired"
    if share.single_use and share.accessed_at is not None:
        return "consumed"
    return "active"


async def create_share(
    db: AsyncSession,
    *,
    receipt_id: uuid.UUID,
    household_id: uuid.UUID,
    created_by: uuid.UUID,
    single_use: bool,
    expiry_preset: str,
    label: str | None = None,
) -> tuple[ReceiptShare, str]:
    """
    Gibt den Klartext-Token nur hier zurück — danach ist ausschließlich der Hash
    gespeichert, der Token selbst nirgends mehr abrufbar. Committet nicht selbst (siehe
    Moduldocstring), aber `flush()`t, damit `share.id`/`share.created_at` für die
    Response der aufrufenden Route bereits populiert sind.
    """
    if await count_active_shares(db, receipt_id) >= _MAX_ACTIVE_SHARES_PER_RECEIPT:
        raise ShareLimitExceededError()

    delta = EXPIRY_PRESETS[expiry_preset]
    expires_at = datetime.now(timezone.utc) + delta if delta is not None else None

    token = secrets.token_urlsafe(32)
    share = ReceiptShare(
        receipt_id=receipt_id,
        household_id=household_id,
        created_by=created_by,
        token_hash=hash_token(token),
        single_use=single_use,
        expires_at=expires_at,
        label=label,
    )
    db.add(share)
    await db.flush()

    return share, token


async def resolve_valid_share_readonly(db: AsyncSession, token: str) -> ReceiptShare | None:
    """
    Für `GET /share/{token}` (Metadaten-Vorschau) — rührt `accessed_at`/`access_count`
    NICHT an. Macht Q1 in sich konsistent: ein bloßer Landing-Page-Aufruf darf einen
    Einmal-Link nicht verbrauchen, nur der Datei-Endpoint (`consume_share_for_file_access`)
    tut das.
    """
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(ReceiptShare).where(
            ReceiptShare.token_hash == hash_token(token), *_active_conditions(now)
        )
    )
    return result.scalar_one_or_none()


async def consume_share_for_file_access(db: AsyncSession, token: str) -> ReceiptShare | None:
    """
    Für `GET /share/{token}/file`: ein einziges atomares `UPDATE ... RETURNING` statt
    getrennter Gültigkeitsprüfung + Update — verhindert ein TOCTOU-Fenster zwischen zwei
    gleichzeitigen Downloads desselben Einmal-Links. Committet nicht selbst (siehe
    Moduldocstring) — die Route committet zusammen mit dem `share_link_accessed`-Audit-Event.
    """
    now = datetime.now(timezone.utc)
    stmt = (
        update(ReceiptShare)
        .where(ReceiptShare.token_hash == hash_token(token), *_active_conditions(now))
        .values(accessed_at=now, access_count=ReceiptShare.access_count + 1)
        .returning(ReceiptShare)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()
