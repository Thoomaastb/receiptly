"""
Stufe B der Konto-Löschung (DSGVO Art. 17, 14-Tage-Karenzzeit, siehe
concepts/konto-loeschen-datenexport.md 3.2) — der irreversible Teardown fälliger
`scheduled_deletion_at`-Konten. Skript-Muster wie
app/scripts/warranty_notifications.py/cleanup_notifications.py: eigene
`AsyncSessionLocal()`, täglich per APScheduler-Job (app/scheduler.py) angestoßen.
Manueller Aufruf (innerhalb des Backend-Containers):
`python -m app.scripts.account_deletion_teardown`

Reihenfolge pro User (Konzept 3.2 Stufe B):
1. Gate erneut prüfen (Rollen könnten sich in der Karenzzeit geändert haben).
2. Nachfolger-Admin ermitteln.
3. Private Buckets (visibility=PRIVATE — NICHT type=personal, siehe
   app/models/bucket.py) löschen, inkl. Original-/Thumbnail-Dateien.
4. Geteilte Buckets (visibility=TRANSPARENT, inkl. Household-Bucket) per Bulk-Update auf
   den Nachfolger übertragen — verhindert die buckets.owner_id ON DELETE CASCADE-Kaskade.
5. Verbleibende Belege dieses Users (jetzt nur noch in geteilten Buckets) auf einen
   Platzhalter-User umschreiben statt zu löschen (Konzept 4.2: Uploader-Link kappen,
   gemeinsamen Beleg-Inhalt erhalten).
6. Audit-Log-Zeilen dieses Users anonymisieren (Konzept 4.1: Zeilen bleiben, PII raus).
7. Ein `account_deleted`-Abschluss-Event (ohne PII).
8. User löschen — der Rest kaskadiert sauber (bucket_access, notifications,
   totp_recovery_codes, webauthn_credentials, receipt_shares.created_by,
   audit_log.user_id → NULL via FK).

Letztes Haushaltsmitglied: kompletten Storage-Baum des Haushalts löschen, dann den
Haushalt selbst (kaskadiert alles). KEIN `account_deleted`-Event in diesem Fall — es
würde durch die Household-Kaskade sofort mitgelöscht, niemand könnte es mehr einsehen
(bewusste, im genehmigten Plan festgehaltene Abweichung von einer wörtlichen Lesart des
Konzepts).

Jeder User läuft in einer EIGENEN Transaktion — ein Fehlschlag darf andere fällige
Haushalte nicht blockieren.
"""

import asyncio
import logging
import secrets
import shutil
import uuid
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.security import hash_password
from app.database import AsyncSessionLocal
from app.models.audit_log import AuditLog
from app.models.bucket import Bucket, BucketVisibility
from app.models.household import Household
from app.models.receipt import Receipt
from app.models.user import User, UserRole
from app.services.account_deletion import AdminGateBlockedError, check_admin_gate
from app.services.audit import record_event
from app.services.storage import ORIGINALS_DIR, THUMBS_DIR

logger = logging.getLogger(__name__)


async def run_scheduled_deletions() -> int:
    """
    Scheduler-Entry-Point: sammelt fällige User-IDs und führt Stufe B je User in einer
    eigenen Transaktion aus. Gibt die Anzahl erfolgreich abgeschlossener Konten zurück.
    """
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(User.id).where(
                User.scheduled_deletion_at.is_not(None),
                User.scheduled_deletion_at <= datetime.now(UTC),
            )
        )
        due_user_ids = [row[0] for row in result.all()]

    completed = 0
    for user_id in due_user_ids:
        try:
            await _teardown_due_user(user_id)
            completed += 1
        except Exception:
            logger.exception("Konto-Teardown fehlgeschlagen für User %s", user_id)

    logger.info(
        "Konto-Löschung Stufe B: %s von %s fälligen Konten abgeschlossen",
        completed,
        len(due_user_ids),
    )
    return completed


async def _teardown_due_user(user_id: uuid.UUID) -> None:
    async with AsyncSessionLocal() as db, db.begin():
        # Immutability-Trigger auf audit_log (Migration 0012) blockiert auch
        # Postgres-interne ON DELETE SET NULL/CASCADE-Operationen — ohne dieses SET LOCAL
        # scheitert die gesamte Transaktion, sobald der User jemals ein Audit-Ereignis
        # ausgelöst hat (gleiches Muster wie app/scripts/cleanup_audit_log.py). Muss vor
        # jedem UPDATE/DELETE auf audit_log in dieser Transaktion stehen.
        await db.execute(text("SET LOCAL audit.allow_delete = 'true'"))

        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if user is None or user.scheduled_deletion_at is None:
            # Zwischenzeitlich reaktiviert (oder bereits von einem vorherigen, teilweise
            # fehlgeschlagenen Lauf entfernt) — no-op.
            return

        try:
            await check_admin_gate(db, user)
        except AdminGateBlockedError:
            logger.warning(
                "Konto-Teardown für User %s blockiert (einziger Admin, weitere Mitglieder "
                "vorhanden) — scheduled_deletion_at bleibt gesetzt, nächster Lauf versucht "
                "es erneut.",
                user_id,
            )
            return

        household_result = await db.execute(
            select(Household).where(Household.id == user.household_id)
        )
        household = household_result.scalar_one()

        remaining_result = await db.execute(
            select(func.count())
            .select_from(User)
            .where(
                User.household_id == household.id,
                User.id != user.id,
                User.is_placeholder.is_(False),
            )
        )
        remaining_members = remaining_result.scalar_one()

        if remaining_members == 0:
            await _dissolve_household(db, user, household)
        else:
            await _teardown_departing_member(db, user, household)


async def _get_or_create_placeholder_user(db: AsyncSession, household_id: uuid.UUID) -> User:
    """
    Get-or-create über den partiellen Unique-Index aus Migration 0022 (höchstens ein
    Platzhalter pro Haushalt). `password_hash` ist ein zufälliger, nie ausgegebener Wert
    (kein Login möglich) — der Platzhalter ist ausschließlich eine Fremdschlüssel-Senke
    für anonymisierte Uploader-Referenzen, kein echtes Konto.
    """
    result = await db.execute(
        select(User).where(User.household_id == household_id, User.is_placeholder.is_(True))
    )
    placeholder = result.scalar_one_or_none()
    if placeholder is not None:
        return placeholder

    placeholder = User(
        username=f"geloescht-{household_id}",
        email=f"geloescht-{household_id}@invalid.local",
        password_hash=hash_password(secrets.token_urlsafe(32)),
        role=UserRole.USER,
        household_id=household_id,
        is_placeholder=True,
    )
    db.add(placeholder)
    await db.flush()
    return placeholder


async def _teardown_departing_member(db: AsyncSession, user: User, household: Household) -> None:
    successor_result = await db.execute(
        select(User).where(
            User.household_id == household.id,
            User.id != user.id,
            User.role == UserRole.ADMIN,
            User.is_placeholder.is_(False),
        )
    )
    successor = successor_result.scalars().first()
    if successor is None:
        # Sollte durch den soeben bestandenen check_admin_gate()-Aufruf bereits
        # ausgeschlossen sein — ohne Nachfolger gäbe es niemanden, dem der
        # Household-Bucket übertragen werden könnte. Sicherheitsnetz statt stillem
        # Datenverlust: loggen und abbrechen, scheduled_deletion_at bleibt gesetzt.
        logger.error(
            "Konto-Teardown für User %s abgebrochen: kein Nachfolger-Admin gefunden trotz "
            "bestandenem Gate-Check.",
            user.id,
        )
        return

    # Private Buckets (Trennachse ist visibility, NICHT type — ein PERSONAL-Bucket ist
    # standardmäßig transparent und muss übertragen, nicht gelöscht werden, siehe
    # app/models/bucket.py) komplett löschen, inkl. Dateien (gleiches Muster wie
    # DELETE /receipts/{id} in app/api/receipts.py).
    private_buckets_result = await db.execute(
        select(Bucket).where(
            Bucket.owner_id == user.id, Bucket.visibility == BucketVisibility.PRIVATE
        )
    )
    private_buckets = list(private_buckets_result.scalars().all())

    for bucket in private_buckets:
        receipts_result = await db.execute(select(Receipt).where(Receipt.bucket_id == bucket.id))
        for receipt in receipts_result.scalars().all():
            Path(receipt.file_path).unlink(missing_ok=True)
            if receipt.thumb_path:
                Path(receipt.thumb_path).unlink(missing_ok=True)
            await db.delete(receipt)
        await db.delete(bucket)

    await db.flush()

    # Geteilte Buckets (inkl. Household-Bucket) auf den Nachfolger übertragen — verhindert
    # die buckets.owner_id ON DELETE CASCADE-Kaskade beim gleich folgenden User-Delete.
    await db.execute(
        update(Bucket)
        .where(Bucket.owner_id == user.id, Bucket.visibility == BucketVisibility.TRANSPARENT)
        .values(owner_id=successor.id)
    )

    # Verbleibende Belege dieses Users (jetzt nur noch in geteilten Buckets, private sind
    # bereits weg) auf einen Platzhalter-User umschreiben statt zu löschen — der
    # Beleg-Inhalt ist gemeinsame Haushaltsfinanz-Historie, nur der personenbezogene
    # Uploader-Link wird gekappt (Konzept 3.2/4.2, Q3/Q12).
    remaining_receipts_result = await db.execute(
        select(func.count()).select_from(Receipt).where(Receipt.user_id == user.id)
    )
    if remaining_receipts_result.scalar_one() > 0:
        placeholder = await _get_or_create_placeholder_user(db, household.id)
        await db.execute(
            update(Receipt).where(Receipt.user_id == user.id).values(user_id=placeholder.id)
        )

    # Audit-Log-Zeilen dieses Users anonymisieren statt löschen (Immutable-Prinzip UND
    # DSGVO gleichzeitig erfüllt, Konzept 4.1) — läuft im bereits aktiven
    # SET LOCAL audit.allow_delete-Scope dieser Transaktion. user_id selbst wird NICHT
    # hier genullt, sondern gleich automatisch über die FK (ondelete=SET NULL) beim
    # anschließenden User-Delete.
    await db.execute(
        update(AuditLog)
        .where(AuditLog.user_id == user.id)
        .values(ip=None, user_agent=None, attempted_username=None)
    )

    await record_event(
        db,
        household_id=household.id,
        event_type="account_deleted",
        user_id=None,
        request=None,
        commit=False,
    )

    await db.delete(user)


async def _dissolve_household(db: AsyncSession, user: User, household: Household) -> None:
    """Letztes Haushaltsmitglied — kein Nachfolger nötig, der gesamte Haushalt wird aufgelöst."""
    await asyncio.to_thread(shutil.rmtree, ORIGINALS_DIR / str(household.id), True)
    await asyncio.to_thread(shutil.rmtree, THUMBS_DIR / str(household.id), True)

    # Kein account_deleted-Event hier (bewusste, im genehmigten Plan festgehaltene
    # Abweichung von einer wörtlichen Lesart des Konzepts) — es würde durch die
    # Household-CASCADE sofort mitgelöscht, niemand könnte es mehr einsehen.
    await db.delete(household)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_scheduled_deletions())
