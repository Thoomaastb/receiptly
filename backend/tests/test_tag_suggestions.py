"""
Tests für `suggest_tags_for_receipt` (app/services/tag_suggestions.py, Feature
"Tag-Vorschläge aus Händler-Historie", siehe concepts/tag-vorschlaege.md). Läuft wie
test_receipt_shares.py gegen eine echte Postgres-Testinstanz (conftest.py), keine
gemockte DB — die Query nutzt eine Subquery + GROUP BY/HAVING, die sich mit einer
In-Memory-Simulation nicht sinnvoll nachbilden ließe.

Deckt ab:
- Fehlender Merchant → leere Liste, ohne die DB überhaupt zu befragen.
- Schwellenwert: ein Tag mit nur einem Vorkommen in der Händler-Historie wird nicht
  vorgeschlagen, ab zwei Vorkommen schon (_MIN_OCCURRENCES).
- N-Grenze: ein Tag, das nur in Belegen außerhalb der letzten 10 (nach created_at)
  vorkommt, wird trotz ausreichender Gesamt-Häufigkeit nicht vorgeschlagen
  (_RECENT_RECEIPT_LIMIT).
- Bereits am Ziel-Beleg zugewiesene Tags tauchen nicht erneut als Vorschlag auf.
- Bucket-Sichtbarkeit: Tags aus Belegen in einem privaten Bucket eines anderen
  Haushaltsmitglieds fließen nicht in den Vorschlag ein (visible_bucket_ids_query).
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import engine
from app.main import app
from app.models.bucket import Bucket, BucketType, BucketVisibility
from app.models.merchant import Merchant
from app.models.receipt import Receipt, ReceiptStatus
from app.models.tag import Tag
from app.models.user import User
from app.services.tag_suggestions import suggest_tags_for_receipt

pytestmark = pytest.mark.asyncio

_PASSWORD = "supersecret123"


@pytest_asyncio.fixture(autouse=True)
async def _clean_tables():
    """Wie test_receipt_shares.py, zusätzlich tags/receipt_tags/merchants/bucket_access."""
    yield
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "TRUNCATE households, users, receipts, receipt_tags, tags, merchants, "
                "buckets, bucket_access, webauthn_credentials, audit_log, "
                "household_security_settings, totp_recovery_codes RESTART IDENTITY CASCADE"
            )
        )


async def _fresh_client() -> AsyncClient:
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


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


async def _get_user(db: AsyncSession, user_id: str) -> User:
    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    return result.scalar_one()


async def _mark_totp_enrolled(db: AsyncSession, user_id: str) -> None:
    """Wie test_receipt_shares.py — require_admin hängt an require_totp_enrolled, /invite
    (Admin-only) wäre sonst mit 403 gesperrt."""
    user = await _get_user(db, user_id)
    user.totp_enabled = True
    await db.commit()


async def _default_bucket_id(db: AsyncSession, household_id: str) -> uuid.UUID:
    result = await db.execute(
        select(Bucket).where(
            Bucket.household_id == uuid.UUID(household_id), Bucket.is_default.is_(True)
        )
    )
    return result.scalar_one().id


async def _create_private_bucket(db: AsyncSession, *, household_id: uuid.UUID, owner_id: uuid.UUID) -> Bucket:
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


async def _create_merchant(db: AsyncSession, name: str = "Testmarkt") -> Merchant:
    merchant = Merchant(name=name, normalized_name=name.lower())
    db.add(merchant)
    await db.commit()
    await db.refresh(merchant)
    return merchant


async def _create_tag(db: AsyncSession, *, household_id: uuid.UUID, name: str) -> Tag:
    tag = Tag(household_id=household_id, name=name, normalized_name=name.lower(), color="blue")
    db.add(tag)
    await db.commit()
    await db.refresh(tag)
    return tag


async def _create_receipt(
    db: AsyncSession,
    *,
    bucket_id: uuid.UUID,
    user_id: uuid.UUID,
    merchant_id: uuid.UUID | None,
    tags: list[Tag] | None = None,
    created_at: datetime | None = None,
) -> Receipt:
    receipt = Receipt(
        user_id=user_id,
        bucket_id=bucket_id,
        merchant_id=merchant_id,
        file_path=f"/tmp/{uuid.uuid4()}.jpg",
        content_hash=f"hash-{uuid.uuid4()}",
        status=ReceiptStatus.PROCESSED,
        currency="EUR",
    )
    if created_at is not None:
        receipt.created_at = created_at
    if tags:
        receipt.tags = tags
    db.add(receipt)
    await db.commit()
    await db.refresh(receipt)
    return receipt


async def _load_with_tags(db: AsyncSession, receipt_id: uuid.UUID) -> Receipt:
    """Simuliert die in B2 vorausgesetzte Vorabladung von `receipt.tags`."""
    result = await db.execute(
        select(Receipt).where(Receipt.id == receipt_id).options(selectinload(Receipt.tags))
    )
    return result.scalar_one()


# --- 1. Fehlender Merchant -----------------------------------------------------------------


async def test_no_merchant_returns_empty_list(db: AsyncSession):
    admin = await _register_admin(await _fresh_client())
    user = await _get_user(db, admin["id"])
    bucket_id = await _default_bucket_id(db, admin["household_id"])

    receipt = await _create_receipt(db, bucket_id=bucket_id, user_id=user.id, merchant_id=None)
    receipt = await _load_with_tags(db, receipt.id)

    assert await suggest_tags_for_receipt(db, receipt, user) == []


# --- 2. Schwellenwert: 1 vs. 2 Vorkommen ----------------------------------------------------


async def test_threshold_requires_at_least_two_occurrences(db: AsyncSession):
    admin = await _register_admin(await _fresh_client())
    user = await _get_user(db, admin["id"])
    household_id = uuid.UUID(admin["household_id"])
    bucket_id = await _default_bucket_id(db, admin["household_id"])
    merchant = await _create_merchant(db)

    tag_once = await _create_tag(db, household_id=household_id, name="Einmalig")
    tag_twice = await _create_tag(db, household_id=household_id, name="Wiederkehrend")

    await _create_receipt(db, bucket_id=bucket_id, user_id=user.id, merchant_id=merchant.id, tags=[tag_once, tag_twice])
    await _create_receipt(db, bucket_id=bucket_id, user_id=user.id, merchant_id=merchant.id, tags=[tag_twice])

    target = await _create_receipt(db, bucket_id=bucket_id, user_id=user.id, merchant_id=merchant.id)
    target = await _load_with_tags(db, target.id)

    suggestions = await suggest_tags_for_receipt(db, target, user)

    assert [t.id for t in suggestions] == [tag_twice.id]


# --- 3. N-Grenze: nur die letzten 10 Belege fließen ein --------------------------------------


async def test_only_last_n_receipts_considered(db: AsyncSession):
    admin = await _register_admin(await _fresh_client())
    user = await _get_user(db, admin["id"])
    household_id = uuid.UUID(admin["household_id"])
    bucket_id = await _default_bucket_id(db, admin["household_id"])
    merchant = await _create_merchant(db)

    tag_old = await _create_tag(db, household_id=household_id, name="Alte Gewohnheit")
    tag_recent = await _create_tag(db, household_id=household_id, name="Aktuell")

    now = datetime.now(UTC)

    # Zwei alte Belege (außerhalb der letzten 10) tragen tag_old zweimal.
    for i in range(2):
        await _create_receipt(
            db,
            bucket_id=bucket_id,
            user_id=user.id,
            merchant_id=merchant.id,
            tags=[tag_old],
            created_at=now - timedelta(days=100 + i),
        )

    # Zehn neuere Belege füllen das N=10-Fenster, zwei davon tragen tag_recent.
    for i in range(10):
        tags = [tag_recent] if i < 2 else []
        await _create_receipt(
            db,
            bucket_id=bucket_id,
            user_id=user.id,
            merchant_id=merchant.id,
            tags=tags,
            created_at=now - timedelta(days=i),
        )

    target = await _create_receipt(db, bucket_id=bucket_id, user_id=user.id, merchant_id=merchant.id)
    target = await _load_with_tags(db, target.id)

    suggestions = await suggest_tags_for_receipt(db, target, user)

    assert tag_recent.id in [t.id for t in suggestions]
    assert tag_old.id not in [t.id for t in suggestions]


# --- 4. Bereits zugewiesene Tags werden nicht erneut vorgeschlagen ---------------------------


async def test_already_assigned_tags_are_excluded(db: AsyncSession):
    admin = await _register_admin(await _fresh_client())
    user = await _get_user(db, admin["id"])
    household_id = uuid.UUID(admin["household_id"])
    bucket_id = await _default_bucket_id(db, admin["household_id"])
    merchant = await _create_merchant(db)

    tag = await _create_tag(db, household_id=household_id, name="Lebensmittel")

    await _create_receipt(db, bucket_id=bucket_id, user_id=user.id, merchant_id=merchant.id, tags=[tag])
    await _create_receipt(db, bucket_id=bucket_id, user_id=user.id, merchant_id=merchant.id, tags=[tag])

    target = await _create_receipt(db, bucket_id=bucket_id, user_id=user.id, merchant_id=merchant.id, tags=[tag])
    target = await _load_with_tags(db, target.id)

    suggestions = await suggest_tags_for_receipt(db, target, user)

    assert suggestions == []


# --- 5. Bucket-Sichtbarkeit: private Buckets anderer Mitglieder bleiben unsichtbar -----------


async def test_private_bucket_of_other_member_is_not_a_suggestion_source(db: AsyncSession):
    admin_client = await _fresh_client()
    admin = await _register_admin(admin_client)
    await _mark_totp_enrolled(db, admin["id"])
    member = await _invite_member(admin_client, username="member1")
    await admin_client.aclose()

    admin_user = await _get_user(db, admin["id"])
    member_user = await _get_user(db, member["id"])
    household_id = uuid.UUID(admin["household_id"])
    merchant = await _create_merchant(db)
    tag = await _create_tag(db, household_id=household_id, name="Geheim")

    private_bucket = await _create_private_bucket(
        db, household_id=household_id, owner_id=member_user.id
    )
    # Zwei Belege im privaten Bucket von member1 — würden ohne Sichtbarkeitsfilter den
    # Schwellenwert erreichen.
    await _create_receipt(db, bucket_id=private_bucket.id, user_id=member_user.id, merchant_id=merchant.id, tags=[tag])
    await _create_receipt(db, bucket_id=private_bucket.id, user_id=member_user.id, merchant_id=merchant.id, tags=[tag])

    target_bucket_id = await _default_bucket_id(db, admin["household_id"])
    target = await _create_receipt(db, bucket_id=target_bucket_id, user_id=admin_user.id, merchant_id=merchant.id)
    target = await _load_with_tags(db, target.id)

    suggestions = await suggest_tags_for_receipt(db, target, admin_user)

    assert suggestions == []
