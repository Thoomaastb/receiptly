"""
Konto-Löschung Stufe B (Scheduler-Teardown, DSGVO Art. 17, siehe
concepts/konto-loeschen-datenexport.md 3.2 und app/scripts/account_deletion_teardown.py)
— der irreversible Teil am Ende der 14-Tage-Karenzzeit. Läuft gegen eine echte Postgres-/
Redis-Testinstanz (conftest.py). Setzt `scheduled_deletion_at` direkt in die Vergangenheit
und ruft `_teardown_due_user()`/`run_scheduled_deletions()` als Coroutine direkt auf —
kein Debug-Override-Flag für die 14 Tage (siehe Auftragskontext).

Deckt genau die im Auftrag geforderten Regressionsfälle ab:
- geteilter (transparent) Bucket wird übertragen statt gelöscht (Visibility-vs-Type-
  Erkenntnis aus dem technischen Plan),
- privater Bucket: Dateien verschwinden tatsächlich von der Platte, nicht nur die DB-Zeile,
- Audit-Log mit Vorgeschichte blockiert die Transaktion NICHT (Immutability-Trigger-Fix),
- letztes Haushaltsmitglied löscht den kompletten Storage-Baum + Haushalt,
- Rollenwechsel während der Karenzzeit wird beim Stufe-B-Re-Check erkannt,
- get_passkey_exclusive_gate_status bleibt nach einer Löschung im selben Haushalt korrekt
  (Platzhalter ausgeschlossen).
"""

import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.security import hash_password
from app.database import engine
from app.models.audit_log import AuditLog
from app.models.bucket import Bucket, BucketType, BucketVisibility
from app.models.household import Household
from app.models.receipt import Receipt
from app.models.user import User, UserRole
from app.models.webauthn_credential import WebauthnCredential
from app.scripts.account_deletion_teardown import _teardown_due_user
from app.services.audit import record_event
from app.services.household_security import get_passkey_exclusive_gate_status
from app.services.storage import ORIGINALS_DIR, THUMBS_DIR

pytestmark = pytest.mark.asyncio

_PASSWORD_HASH = hash_password("supersecret123")


@pytest_asyncio.fixture(autouse=True)
async def _clean_tables():
    yield
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "TRUNCATE households, users, webauthn_credentials, audit_log, "
                "household_security_settings, totp_recovery_codes RESTART IDENTITY CASCADE"
            )
        )


async def _create_household(db: AsyncSession, name: str = "Testhaushalt") -> Household:
    household = Household(name=name)
    db.add(household)
    await db.flush()
    return household


async def _create_user(
    db: AsyncSession,
    household_id: uuid.UUID,
    username: str,
    *,
    role: UserRole = UserRole.USER,
    scheduled_deletion_at: datetime | None = None,
) -> User:
    user = User(
        username=username,
        email=f"{username}@example.com",
        password_hash=_PASSWORD_HASH,
        role=role,
        household_id=household_id,
        scheduled_deletion_at=scheduled_deletion_at,
    )
    db.add(user)
    await db.flush()
    return user


async def _create_bucket(
    db: AsyncSession,
    household_id: uuid.UUID,
    owner_id: uuid.UUID,
    *,
    visibility: BucketVisibility,
    type_: BucketType = BucketType.PERSONAL,
    is_default: bool = False,
    name: str = "Bucket",
) -> Bucket:
    bucket = Bucket(
        household_id=household_id,
        owner_id=owner_id,
        name=name,
        type=type_,
        visibility=visibility,
        is_default=is_default,
    )
    db.add(bucket)
    await db.flush()
    return bucket


def _touch_file(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"dummy")


async def _create_receipt(
    db: AsyncSession,
    user_id: uuid.UUID,
    bucket_id: uuid.UUID,
    file_path: Path,
    thumb_path: Path | None = None,
) -> Receipt:
    _touch_file(file_path)
    if thumb_path is not None:
        _touch_file(thumb_path)
    receipt = Receipt(
        user_id=user_id,
        bucket_id=bucket_id,
        file_path=str(file_path),
        thumb_path=str(thumb_path) if thumb_path else None,
    )
    db.add(receipt)
    await db.flush()
    return receipt


_PAST = datetime.now(UTC) - timedelta(days=1)


# --- Geteilter Bucket wird übertragen, nicht gelöscht -------------------------------------


async def test_shared_bucket_transferred_to_successor_admin_and_receipt_anonymized(
    db: AsyncSession,
):
    household = await _create_household(db)
    departing = await _create_user(
        db, household.id, "admin1", role=UserRole.ADMIN, scheduled_deletion_at=_PAST
    )
    successor = await _create_user(db, household.id, "admin2", role=UserRole.ADMIN)

    # Ein PERSONAL-Bucket ist standardmäßig TRANSPARENT (siehe app/models/bucket.py) —
    # genau die Trennachse, die das technische Plan-Review als kritisch markiert hat.
    shared_bucket = await _create_bucket(
        db,
        household.id,
        departing.id,
        visibility=BucketVisibility.TRANSPARENT,
        name="Geteilter persönlicher Bucket",
    )
    receipt = await _create_receipt(
        db,
        departing.id,
        shared_bucket.id,
        ORIGINALS_DIR / str(household.id) / "shared.jpg",
    )
    await db.commit()

    await _teardown_due_user(departing.id)

    async with db.begin():
        # `db` (Fixture-Session) hat Bucket/Receipt aus dem Setup oben bereits im
        # Identity-Map zwischengespeichert (expire_on_commit=False) — ohne
        # populate_existing=True würden diese Selects die VERALTETEN Python-Objekte
        # zurückgeben statt die von _teardown_due_user() (eigene, längst committete
        # Session) geänderten Werte. Gezielt nur auf diese beiden Queries angewandt statt
        # eines pauschalen db.expire_all() — Letzteres würde auch successor.id/departing.id
        # weiter unten expiren und bei synchronem Attributzugriff (außerhalb eines awaits)
        # zu MissingGreenlet-Fehlern führen.
        bucket_result = await db.execute(
            select(Bucket)
            .where(Bucket.id == shared_bucket.id)
            .execution_options(populate_existing=True)
        )
        bucket = bucket_result.scalar_one()
        assert bucket.owner_id == successor.id

        receipt_result = await db.execute(
            select(Receipt)
            .where(Receipt.id == receipt.id)
            .execution_options(populate_existing=True)
        )
        reloaded_receipt = receipt_result.scalar_one()
        assert reloaded_receipt.user_id != departing.id
        assert reloaded_receipt.user_id != successor.id  # anonymisiert auf Platzhalter

        placeholder_result = await db.execute(
            select(User).where(User.household_id == household.id, User.is_placeholder.is_(True))
        )
        placeholder = placeholder_result.scalar_one()
        assert reloaded_receipt.user_id == placeholder.id

        # Der Beleg-Inhalt (gemeinsame Haushaltsfinanz-Historie) bleibt erhalten — Datei
        # wird NICHT gelöscht, nur der Uploader-Link gekappt.
        assert Path(reloaded_receipt.file_path).is_file()

        departing_gone = await db.execute(select(User).where(User.id == departing.id))
        assert departing_gone.scalar_one_or_none() is None


# --- Privater Bucket: Dateien verschwinden tatsächlich -------------------------------------


async def test_private_bucket_receipt_files_removed_from_disk(db: AsyncSession):
    household = await _create_household(db)
    departing = await _create_user(
        db, household.id, "admin1", role=UserRole.ADMIN, scheduled_deletion_at=_PAST
    )
    await _create_user(db, household.id, "admin2", role=UserRole.ADMIN)

    private_bucket = await _create_bucket(
        db, household.id, departing.id, visibility=BucketVisibility.PRIVATE, name="Privat"
    )
    file_path = ORIGINALS_DIR / str(household.id) / "private.jpg"
    thumb_path = THUMBS_DIR / str(household.id) / "private.jpg"
    receipt = await _create_receipt(db, departing.id, private_bucket.id, file_path, thumb_path)
    await db.commit()

    assert file_path.is_file()
    assert thumb_path.is_file()

    await _teardown_due_user(departing.id)

    assert not file_path.exists()
    assert not thumb_path.exists()

    async with db.begin():
        bucket_result = await db.execute(select(Bucket).where(Bucket.id == private_bucket.id))
        assert bucket_result.scalar_one_or_none() is None

        receipt_result = await db.execute(select(Receipt).where(Receipt.id == receipt.id))
        assert receipt_result.scalar_one_or_none() is None


# --- Audit-Log mit Vorgeschichte blockiert die Transaktion nicht ---------------------------


async def test_audit_log_history_does_not_block_teardown_transaction(db: AsyncSession):
    household = await _create_household(db)
    departing = await _create_user(
        db, household.id, "admin1", role=UserRole.ADMIN, scheduled_deletion_at=_PAST
    )
    await _create_user(db, household.id, "admin2", role=UserRole.ADMIN)
    await db.commit()

    await record_event(
        db,
        household_id=household.id,
        user_id=departing.id,
        event_type="login_success",
        request=None,
    )
    await record_event(
        db,
        household_id=household.id,
        user_id=departing.id,
        event_type="password_changed",
        request=None,
    )

    # Darf NICHT am audit_log_immutable_trigger (Migration 0012) scheitern.
    await _teardown_due_user(departing.id)

    async with db.begin():
        # populate_existing=True: die beiden record_event()-Aufrufe oben haben diese
        # AuditLog-Zeilen bereits über DIESE Session (db) anlegt/geladen — ohne das würden
        # die untenstehenden Assertions die alten, noch nicht anonymisierten Werte aus dem
        # Identity-Map sehen statt der von der Teardown-Routine committeten Änderungen.
        audit_result = await db.execute(
            select(AuditLog)
            .where(AuditLog.event_type.in_(["login_success", "password_changed"]))
            .execution_options(populate_existing=True)
        )
        rows = list(audit_result.scalars().all())
        assert len(rows) == 2
        for row in rows:
            # Zeilen bleiben bestehen (Immutable-Prinzip), aber anonymisiert (DSGVO) —
            # user_id wird automatisch über die FK (ondelete=SET NULL) beim User-Delete
            # genullt, ip/user_agent/attempted_username explizit von der Teardown-Routine.
            assert row.user_id is None
            assert row.ip is None
            assert row.user_agent is None

        completion_result = await db.execute(
            select(AuditLog).where(AuditLog.event_type == "account_deleted")
        )
        assert completion_result.scalar_one_or_none() is not None


# --- Letztes Haushaltsmitglied: kompletter Storage-Baum weg ---------------------------------


async def test_last_member_dissolves_household_and_removes_storage_tree(db: AsyncSession):
    household = await _create_household(db)
    sole_user = await _create_user(
        db, household.id, "solo", role=UserRole.ADMIN, scheduled_deletion_at=_PAST
    )
    bucket = await _create_bucket(
        db, household.id, sole_user.id, visibility=BucketVisibility.TRANSPARENT, is_default=True
    )
    await _create_receipt(
        db, sole_user.id, bucket.id, ORIGINALS_DIR / str(household.id) / "solo.jpg",
        THUMBS_DIR / str(household.id) / "solo.jpg",
    )
    await db.commit()

    originals_dir = ORIGINALS_DIR / str(household.id)
    thumbs_dir = THUMBS_DIR / str(household.id)
    assert originals_dir.is_dir()
    assert thumbs_dir.is_dir()

    await _teardown_due_user(sole_user.id)

    assert not originals_dir.exists()
    assert not thumbs_dir.exists()

    async with db.begin():
        household_result = await db.execute(select(Household).where(Household.id == household.id))
        assert household_result.scalar_one_or_none() is None

        user_result = await db.execute(select(User).where(User.id == sole_user.id))
        assert user_result.scalar_one_or_none() is None

        # Kein account_deleted-Event — der Haushalt (und damit audit_log darüber) ist weg,
        # niemand könnte es mehr einsehen (bewusste Plan-Abweichung, siehe Modul-Docstring
        # von app/scripts/account_deletion_teardown.py).
        audit_result = await db.execute(
            select(AuditLog).where(AuditLog.household_id == household.id)
        )
        assert audit_result.first() is None


# --- Rollenwechsel während der Karenzzeit ---------------------------------------------------


async def test_role_change_during_grace_period_detected_at_teardown(db: AsyncSession):
    household = await _create_household(db)
    sole_admin = await _create_user(
        db, household.id, "admin1", role=UserRole.ADMIN, scheduled_deletion_at=_PAST
    )
    member = await _create_user(db, household.id, "member1", role=UserRole.USER)
    await db.commit()

    # Gate blockiert weiterhin: admin1 ist noch der einzige Admin, member1 existiert noch.
    await _teardown_due_user(sole_admin.id)

    async with db.begin():
        still_there = await db.execute(
            select(User)
            .where(User.id == sole_admin.id)
            .execution_options(populate_existing=True)
        )
        reloaded = still_there.scalar_one()
        assert reloaded.scheduled_deletion_at is not None

    # Rollenwechsel während der Karenzzeit: member1 wird zum zweiten Admin befördert.
    async with db.begin():
        member_result = await db.execute(select(User).where(User.id == member.id))
        member_row = member_result.scalar_one()
        member_row.role = UserRole.ADMIN

    # Nächster Lauf: Gate greift nicht mehr, Teardown läuft durch.
    await _teardown_due_user(sole_admin.id)

    async with db.begin():
        gone = await db.execute(select(User).where(User.id == sole_admin.id))
        assert gone.scalar_one_or_none() is None


# --- Passkey-Exklusiv-Gate bleibt nach einer Löschung korrekt -------------------------------


async def test_passkey_exclusive_gate_status_correct_after_deletion(db: AsyncSession):
    household = await _create_household(db)
    departing = await _create_user(
        db, household.id, "admin1", role=UserRole.ADMIN, scheduled_deletion_at=_PAST
    )
    successor = await _create_user(db, household.id, "admin2", role=UserRole.ADMIN)
    db.add(
        WebauthnCredential(
            user_id=successor.id,
            credential_id=f"dummy-{uuid.uuid4()}",
            public_key=b"\x00\x01",
            device_label="Testgerät",
        )
    )

    # Erzwingt die Platzhalter-Erzeugung (verbleibender geteilter Beleg des departing Users).
    shared_bucket = await _create_bucket(
        db, household.id, departing.id, visibility=BucketVisibility.TRANSPARENT
    )
    await _create_receipt(
        db, departing.id, shared_bucket.id, ORIGINALS_DIR / str(household.id) / "gate.jpg"
    )
    await db.commit()

    await _teardown_due_user(departing.id)

    async with db.begin():
        placeholder_result = await db.execute(
            select(User).where(User.household_id == household.id, User.is_placeholder.is_(True))
        )
        assert placeholder_result.scalar_one_or_none() is not None

    missing_members, total_members = await get_passkey_exclusive_gate_status(db, household.id)
    await db.rollback()

    # Platzhalter zählt NICHT mit — sonst könnte passkey_exclusive_login in diesem
    # Haushalt nie wieder aktiviert werden (der Platzhalter hat nie einen Passkey).
    assert total_members == 1
    assert missing_members == []
