"""
Tests für GET /api/receipts/{receipt_id}/adjacent (app/api/receipts.py:get_adjacent_receipts)
— "vorheriger/nächster Beleg"-Navigation in der Detailansicht. Läuft wie
test_receipt_shares.py gegen eine echte Postgres-Testinstanz (conftest.py).

Deckt ab:
- Randfälle der sortierten Liste: der jeweils neueste/älteste Beleg im Bucket liefert
  `null` für die fehlende Richtung, ein Beleg dazwischen liefert beide Nachbarn.
- 404, wenn receipt_id nicht im angegebenen bucket_id liegt (anderer, aber für den Nutzer
  sichtbarer Bucket).
- 404, wenn der angegebene Bucket für den Nutzer gar nicht sichtbar ist (privater Bucket
  eines anderen Haushaltsmitglieds) — Bucket-Existenz bleibt verborgen, analog zu den
  übrigen Endpoints in dieser Datei.
"""

import uuid
from datetime import date, timedelta

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import engine
from app.models.bucket import Bucket, BucketType, BucketVisibility
from app.models.receipt import Receipt, ReceiptStatus
from app.models.user import User

pytestmark = pytest.mark.asyncio

_PASSWORD = "supersecret123"


@pytest_asyncio.fixture(autouse=True)
async def _clean_tables():
    """Wie test_receipt_shares.py, zusätzlich bucket_access für den Fremd-Bucket-Test."""
    yield
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "TRUNCATE households, users, receipts, buckets, bucket_access, "
                "webauthn_credentials, audit_log, household_security_settings, "
                "totp_recovery_codes RESTART IDENTITY CASCADE"
            )
        )


async def _register_admin(client: AsyncClient, username: str = "admin1") -> dict:
    response = await client.post(
        "/api/auth/register",
        json={
            "household_name": "Testhaushalt",
            "username": username,
            "email": f"{username}@example.com",
            "password": _PASSWORD,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _invite_member(client: AsyncClient, username: str = "member1") -> dict:
    response = await client.post(
        "/api/auth/invite",
        json={"username": username, "email": f"{username}@example.com", "password": _PASSWORD},
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _mark_totp_enrolled(db: AsyncSession, user_id: str) -> None:
    """Wie test_receipt_shares.py — require_totp_enrolled sperrt den Router sonst mit 403."""
    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one()
    user.totp_enabled = True
    await db.commit()


async def _default_bucket_id(db: AsyncSession, household_id: str) -> uuid.UUID:
    result = await db.execute(
        select(Bucket).where(
            Bucket.household_id == uuid.UUID(household_id), Bucket.is_default.is_(True)
        )
    )
    return result.scalar_one().id


async def _create_private_bucket(
    db: AsyncSession, *, household_id: uuid.UUID, owner_id: uuid.UUID
) -> Bucket:
    bucket = Bucket(
        household_id=household_id,
        owner_id=owner_id,
        name="Privat",
        type=BucketType.PERSONAL,
        visibility=BucketVisibility.PRIVATE,
    )
    db.add(bucket)
    await db.commit()
    await db.refresh(bucket)
    return bucket


async def _create_receipt(
    db: AsyncSession, *, bucket_id: uuid.UUID, user_id: uuid.UUID, receipt_date: date | None
) -> Receipt:
    receipt = Receipt(
        user_id=user_id,
        bucket_id=bucket_id,
        file_path=f"/tmp/{uuid.uuid4()}.jpg",
        content_hash=f"hash-{uuid.uuid4()}",
        status=ReceiptStatus.PROCESSED,
        currency="EUR",
        receipt_date=receipt_date,
    )
    db.add(receipt)
    await db.commit()
    await db.refresh(receipt)
    return receipt


# --- 1. Randfälle: neuester/ältester Beleg liefert null für die fehlende Richtung ----------


async def test_edges_of_bucket_return_null_for_missing_direction(
    client: AsyncClient, db: AsyncSession
):
    admin = await _register_admin(client)
    await _mark_totp_enrolled(db, admin["id"])
    bucket_id = await _default_bucket_id(db, admin["household_id"])
    user_id = uuid.UUID(admin["id"])

    base = date(2026, 1, 15)
    oldest = await _create_receipt(db, bucket_id=bucket_id, user_id=user_id, receipt_date=base)
    middle = await _create_receipt(
        db, bucket_id=bucket_id, user_id=user_id, receipt_date=base + timedelta(days=1)
    )
    newest = await _create_receipt(
        db, bucket_id=bucket_id, user_id=user_id, receipt_date=base + timedelta(days=2)
    )

    newest_response = await client.get(
        f"/api/receipts/{newest.id}/adjacent", params={"bucket_id": str(bucket_id)}
    )
    assert newest_response.status_code == 200, newest_response.text
    assert newest_response.json() == {"newer_id": None, "older_id": str(middle.id)}

    middle_response = await client.get(
        f"/api/receipts/{middle.id}/adjacent", params={"bucket_id": str(bucket_id)}
    )
    assert middle_response.status_code == 200, middle_response.text
    assert middle_response.json() == {
        "newer_id": str(newest.id),
        "older_id": str(oldest.id),
    }

    oldest_response = await client.get(
        f"/api/receipts/{oldest.id}/adjacent", params={"bucket_id": str(bucket_id)}
    )
    assert oldest_response.status_code == 200, oldest_response.text
    assert oldest_response.json() == {"newer_id": str(middle.id), "older_id": None}


# --- 2. Beleg liegt nicht im angegebenen Bucket ---------------------------------------------


async def test_receipt_not_in_requested_bucket_returns_404(client: AsyncClient, db: AsyncSession):
    admin = await _register_admin(client)
    await _mark_totp_enrolled(db, admin["id"])
    user_id = uuid.UUID(admin["id"])
    household_id = uuid.UUID(admin["household_id"])
    default_bucket_id = await _default_bucket_id(db, admin["household_id"])

    other_bucket = await _create_private_bucket(
        db, household_id=household_id, owner_id=user_id
    )
    receipt_in_other_bucket = await _create_receipt(
        db, bucket_id=other_bucket.id, user_id=user_id, receipt_date=date(2026, 1, 15)
    )

    response = await client.get(
        f"/api/receipts/{receipt_in_other_bucket.id}/adjacent",
        params={"bucket_id": str(default_bucket_id)},
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "Beleg nicht gefunden"}


# --- 3. Angegebener Bucket ist für den Nutzer gar nicht sichtbar ----------------------------


async def test_bucket_not_visible_to_user_returns_404(client: AsyncClient, db: AsyncSession):
    """
    `client` bleibt als admin1 eingeloggt (Session aus der Registrierung) — kein separater
    Re-Login nötig bzw. sogar problematisch: admin1 hat hier `totp_enabled=True` (Router-Gate,
    siehe _mark_totp_enrolled), ein erneuter Passwort-Login würde also nur den ersten Faktor
    abschließen (`requires_totp`, keine volle Session) statt echten Zugriff zu liefern.
    """
    admin = await _register_admin(client)
    await _mark_totp_enrolled(db, admin["id"])
    member = await _invite_member(client, username="member1")

    household_id = uuid.UUID(admin["household_id"])
    member_id = uuid.UUID(member["id"])

    member_private_bucket = await _create_private_bucket(
        db, household_id=household_id, owner_id=member_id
    )
    receipt = await _create_receipt(
        db,
        bucket_id=member_private_bucket.id,
        user_id=member_id,
        receipt_date=date(2026, 1, 15),
    )

    # admin1 hat keinen Zugriff auf member1s privaten Bucket — muss wie "nicht gefunden"
    # behandelt werden, kein Leak über 403.
    response = await client.get(
        f"/api/receipts/{receipt.id}/adjacent",
        params={"bucket_id": str(member_private_bucket.id)},
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "Beleg nicht gefunden"}
