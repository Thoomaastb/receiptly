"""
Tests für das Beleg-Teilen-Feature (`ReceiptShare`, siehe app/models/receipt_share.py,
app/services/receipt_shares.py, app/api/share.py, app/api/receipts.py). Läuft wie
test_webauthn.py/test_passkey_exclusive_login.py gegen eine echte Postgres-/
Redis-Testinstanz (conftest.py), keine gemockte DB — insbesondere der TOCTOU-Race-Test
unten braucht einen echten `UPDATE ... RETURNING`-Roundtrip gegen Postgres, keinen Mock.

Deckt ab:
- Determinismus von hash_token() (kein versehentliches Salzen).
- _active_conditions()-Gültigkeitslogik für alle vier Ungültig-Zustände (widerrufen,
  abgelaufen, Einmal-Link bereits verbraucht, unbekannter Token) sowie den Gültig-Fall.
- Die zentrale Q1-Garantie: der Metadaten-Pfad (resolve_valid_share_readonly) verbraucht
  einen Einmal-Link nicht, nur der Datei-Pfad (consume_share_for_file_access) tut das.
- TOCTOU-Race: zwei gleichzeitige consume_share_for_file_access()-Aufrufe auf denselben
  Einmal-Link — genau einer darf gewinnen.
- Das harte 10er-Limit pro Beleg (ShareLimitExceededError) und dass es nur AKTIVE, nicht
  je-erstellte Links zählt (ein Widerruf macht wieder Platz).
- API-Ebene: identische generische 404-Antwort für alle vier Ungültig-Zustände auf beiden
  öffentlichen Endpoints (kein Leak unterscheidbarer Information).
- API-Ebene: Erstellen ist an Bucket-Schreibzugriff gekoppelt, Widerrufen ist eng auf
  Ersteller-oder-Admin beschränkt (Q7).
"""

import asyncio
import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal, engine
from app.main import app
from app.models.bucket import Bucket
from app.models.receipt import Receipt, ReceiptStatus
from app.models.receipt_share import ReceiptShare
from app.models.user import User
from app.services.receipt_shares import (
    ShareLimitExceededError,
    consume_share_for_file_access,
    count_active_shares,
    create_share,
    hash_token,
    resolve_valid_share_readonly,
)

pytestmark = pytest.mark.asyncio

_PASSWORD = "supersecret123"


@pytest_asyncio.fixture(autouse=True)
async def _clean_tables():
    """Wie test_webauthn.py — läuft NACH jedem Test, räumt zusätzlich receipt_shares/receipts/buckets ab."""
    yield
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "TRUNCATE households, users, receipt_shares, receipts, buckets, "
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


async def _mark_totp_enrolled(db: AsyncSession, user_id: str) -> None:
    """Wie test_webauthn.py — require_totp_enrolled sperrt receipts/buckets-Router sonst mit 403."""
    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one()
    user.totp_enabled = True
    await db.commit()


async def _invite_member(client: AsyncClient, db: AsyncSession, username: str = "member1") -> dict:
    response = await client.post(
        "/api/auth/invite",
        json={"username": username, "email": f"{username}@example.com", "password": _PASSWORD},
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _fresh_client() -> AsyncClient:
    """Eigener Client mit leerem Cookie-Jar — simuliert einen zweiten Browser/eine neue Session."""
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


async def _default_bucket_id(db: AsyncSession, household_id: str) -> uuid.UUID:
    """Registrierung legt automatisch einen Household-Default-Bucket an (siehe app/api/auth.py)."""
    result = await db.execute(
        select(Bucket).where(
            Bucket.household_id == uuid.UUID(household_id), Bucket.is_default.is_(True)
        )
    )
    return result.scalar_one().id


async def _create_receipt(
    db: AsyncSession, *, bucket_id: uuid.UUID, user_id: uuid.UUID, file_path: str = "/tmp/does-not-matter.jpg"
) -> Receipt:
    receipt = Receipt(
        user_id=user_id,
        bucket_id=bucket_id,
        file_path=file_path,
        content_hash=f"hash-{uuid.uuid4()}",
        status=ReceiptStatus.PROCESSED,
        currency="EUR",
        receipt_date=date(2026, 1, 15),
        total_amount=42.50,
    )
    db.add(receipt)
    await db.commit()
    await db.refresh(receipt)
    return receipt


async def _make_share(
    db: AsyncSession,
    receipt: Receipt,
    household_id: uuid.UUID,
    created_by: uuid.UUID,
    *,
    single_use: bool = False,
    expiry_preset: str = "unlimited",
) -> tuple[ReceiptShare, str]:
    return await create_share(
        db,
        receipt_id=receipt.id,
        household_id=household_id,
        created_by=created_by,
        single_use=single_use,
        expiry_preset=expiry_preset,
    )


# --- 1. Token-Hashing --------------------------------------------------------------------


async def test_hash_token_is_deterministic_not_salted():
    token = "some-example-token-value"
    assert hash_token(token) == hash_token(token)
    assert len(hash_token(token)) == 64  # sha256 hex
    assert hash_token(token) != hash_token(token + "x")


# --- 2. Gültigkeitslogik für alle vier Ungültig-Zustände + den Gültig-Fall ----------------


async def test_validity_across_all_invalid_states_and_the_valid_case(db: AsyncSession):
    admin = await _register_admin(await _fresh_client())
    bucket_id = await _default_bucket_id(db, admin["household_id"])
    receipt = await _create_receipt(
        db, bucket_id=bucket_id, user_id=uuid.UUID(admin["id"])
    )
    household_id = uuid.UUID(admin["household_id"])
    user_id = uuid.UUID(admin["id"])

    # Gültiger Link.
    valid_share, valid_token = await _make_share(db, receipt, household_id, user_id)
    await db.commit()
    assert await resolve_valid_share_readonly(db, valid_token) is not None
    assert await consume_share_for_file_access(db, valid_token) is not None
    await db.commit()

    # Widerrufen.
    revoked_share, revoked_token = await _make_share(db, receipt, household_id, user_id)
    revoked_share.revoked_at = datetime.now(timezone.utc)
    await db.commit()
    assert await resolve_valid_share_readonly(db, revoked_token) is None
    assert await consume_share_for_file_access(db, revoked_token) is None
    await db.commit()

    # Abgelaufen.
    expired_share, expired_token = await _make_share(db, receipt, household_id, user_id)
    expired_share.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    await db.commit()
    assert await resolve_valid_share_readonly(db, expired_token) is None
    assert await consume_share_for_file_access(db, expired_token) is None
    await db.commit()

    # Einmal-Link, bereits verbraucht.
    single_share, single_token = await _make_share(
        db, receipt, household_id, user_id, single_use=True
    )
    await db.commit()
    consumed = await consume_share_for_file_access(db, single_token)
    assert consumed is not None
    await db.commit()
    assert await resolve_valid_share_readonly(db, single_token) is None
    assert await consume_share_for_file_access(db, single_token) is None
    await db.commit()

    # Unbekannter Token — nie existiert.
    random_token = "never-issued-token-abc123"
    assert await resolve_valid_share_readonly(db, random_token) is None
    assert await consume_share_for_file_access(db, random_token) is None
    await db.commit()


# --- 3. Einmal-Link-Verbrauchszeitpunkt (Q1) ----------------------------------------------


async def test_single_use_link_not_consumed_by_metadata_reads_only_by_file_access(
    db: AsyncSession,
):
    admin = await _register_admin(await _fresh_client())
    bucket_id = await _default_bucket_id(db, admin["household_id"])
    receipt = await _create_receipt(db, bucket_id=bucket_id, user_id=uuid.UUID(admin["id"]))

    share, token = await _make_share(
        db, receipt, uuid.UUID(admin["household_id"]), uuid.UUID(admin["id"]), single_use=True
    )
    await db.commit()

    # Mehrere Metadaten-Aufrufe (simuliert die Landing-Page) dürfen den Link nicht anrühren.
    for _ in range(3):
        resolved = await resolve_valid_share_readonly(db, token)
        assert resolved is not None
        assert resolved.accessed_at is None
        assert resolved.access_count == 0

    # Erster Datei-Zugriff verbraucht den Link.
    consumed = await consume_share_for_file_access(db, token)
    await db.commit()
    assert consumed is not None
    assert consumed.accessed_at is not None
    assert consumed.access_count == 1

    # Zweiter Datei-Zugriff (simuliert einen zweiten Download-Versuch) schlägt fehl.
    second_attempt = await consume_share_for_file_access(db, token)
    await db.commit()
    assert second_attempt is None

    # Der verbrauchte Zustand spiegelt sich auch im Metadaten-Pfad wider (dieselbe
    # _active_conditions()-Quelle der Wahrheit).
    assert await resolve_valid_share_readonly(db, token) is None


# --- 4. TOCTOU-Race auf Einmal-Links -------------------------------------------------------


async def test_concurrent_file_access_on_single_use_link_only_one_wins():
    """
    Zwei parallele consume_share_for_file_access()-Aufrufe auf denselben Einmal-Link, je
    mit einer eigenen DB-Session/Connection (wie zwei echte, gleichzeitige HTTP-Requests
    das täten) — beweist, dass das atomare UPDATE...RETURNING das TOCTOU-Fenster
    tatsächlich schließt: von zwei simultanen Downloads darf nur einer gewinnen.
    """
    async with AsyncSessionLocal() as setup_db:
        admin_client = await _fresh_client()
        try:
            admin = await _register_admin(admin_client)
        finally:
            await admin_client.aclose()

        bucket_id = await _default_bucket_id(setup_db, admin["household_id"])
        receipt = await _create_receipt(
            setup_db, bucket_id=bucket_id, user_id=uuid.UUID(admin["id"])
        )
        share, token = await _make_share(
            setup_db,
            receipt,
            uuid.UUID(admin["household_id"]),
            uuid.UUID(admin["id"]),
            single_use=True,
        )
        await setup_db.commit()

    async def _attempt() -> ReceiptShare | None:
        async with AsyncSessionLocal() as session:
            result = await consume_share_for_file_access(session, token)
            await session.commit()
            return result

    result_a, result_b = await asyncio.gather(_attempt(), _attempt())

    winners = [r for r in (result_a, result_b) if r is not None]
    losers = [r for r in (result_a, result_b) if r is None]
    assert len(winners) == 1, "genau ein gleichzeitiger Zugriff darf einen Einmal-Link konsumieren"
    assert len(losers) == 1

    async with AsyncSessionLocal() as verify_db:
        result = await verify_db.execute(select(ReceiptShare).where(ReceiptShare.id == share.id))
        final = result.scalar_one()
        assert final.access_count == 1
        assert final.accessed_at is not None


# --- 5. 10er-Limit pro Beleg (Q10) ---------------------------------------------------------


async def test_active_share_cap_counts_active_not_total_ever_created(db: AsyncSession):
    admin = await _register_admin(await _fresh_client())
    bucket_id = await _default_bucket_id(db, admin["household_id"])
    receipt = await _create_receipt(db, bucket_id=bucket_id, user_id=uuid.UUID(admin["id"]))
    household_id = uuid.UUID(admin["household_id"])
    user_id = uuid.UUID(admin["id"])

    shares = []
    for _ in range(10):
        share, _token = await _make_share(db, receipt, household_id, user_id)
        await db.commit()
        shares.append(share)

    assert await count_active_shares(db, receipt.id) == 10

    with pytest.raises(ShareLimitExceededError):
        await _make_share(db, receipt, household_id, user_id)

    # Ein Widerruf macht wieder Platz — der Cap zählt aktive, nicht je-erstellte Links.
    shares[0].revoked_at = datetime.now(timezone.utc)
    await db.commit()

    assert await count_active_shares(db, receipt.id) == 9
    eleventh_share, _eleventh_token = await _make_share(db, receipt, household_id, user_id)
    await db.commit()
    assert eleventh_share is not None
    assert await count_active_shares(db, receipt.id) == 10


# --- 6. API-Ebene: identische generische Fehlerantwort ------------------------------------


async def test_public_endpoints_return_byte_identical_404_for_every_invalid_state(
    client: AsyncClient, db: AsyncSession
):
    admin = await _register_admin(client)
    await _mark_totp_enrolled(db, admin["id"])
    bucket_id = await _default_bucket_id(db, admin["household_id"])
    receipt = await _create_receipt(db, bucket_id=bucket_id, user_id=uuid.UUID(admin["id"]))
    household_id = uuid.UUID(admin["household_id"])
    user_id = uuid.UUID(admin["id"])

    revoked_share, revoked_token = await _make_share(db, receipt, household_id, user_id)
    revoked_share.revoked_at = datetime.now(timezone.utc)
    await db.commit()

    expired_share, expired_token = await _make_share(db, receipt, household_id, user_id)
    expired_share.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    await db.commit()

    consumed_share, consumed_token = await _make_share(
        db, receipt, household_id, user_id, single_use=True
    )
    await db.commit()
    assert await consume_share_for_file_access(db, consumed_token) is not None
    await db.commit()

    unknown_token = "totally-unknown-token-xyz"

    tokens = [revoked_token, expired_token, consumed_token, unknown_token]

    metadata_responses = [await client.get(f"/api/share/{t}") for t in tokens]
    file_responses = [await client.get(f"/api/share/{t}/file") for t in tokens]

    for response in metadata_responses:
        assert response.status_code == 404
        assert response.json() == {"detail": "Link nicht gültig"}
    for response in file_responses:
        assert response.status_code == 404
        assert response.json() == {"detail": "Link nicht gültig"}

    # Byte-identisch untereinander, nicht nur einzeln korrekt.
    assert len({r.content for r in metadata_responses}) == 1
    assert len({r.content for r in file_responses}) == 1


# --- 7. API-Ebene: Autorisierung Erstellen vs. Widerrufen (Q7) ----------------------------


async def test_create_share_requires_bucket_write_access(client: AsyncClient, db: AsyncSession):
    admin = await _register_admin(client)
    await _mark_totp_enrolled(db, admin["id"])
    bucket_id = await _default_bucket_id(db, admin["household_id"])
    receipt = await _create_receipt(db, bucket_id=bucket_id, user_id=uuid.UUID(admin["id"]))

    response = await client.post(
        f"/api/receipts/{receipt.id}/shares",
        json={"single_use": False, "expiry_preset": "7d"},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["url"].startswith("http")
    assert "/share/" in body["url"]
    assert body["single_use"] is False


async def test_revoke_narrower_than_create_creator_and_admin_allowed_other_member_forbidden(
    client: AsyncClient, db: AsyncSession
):
    """
    Q7: Erstellen ist an Bucket-Schreibzugriff gekoppelt (jedes Mitglied mit Edit-Recht auf
    den Household-Bucket), Widerrufen ist enger — nur der Ersteller des jeweiligen Links
    oder ein Admin. Ein anderes Mitglied mit Edit-Recht, das den Link nicht selbst erstellt
    hat, bekommt 403.
    """
    admin = await _register_admin(client, username="admin1")
    await _mark_totp_enrolled(db, admin["id"])
    member = await _invite_member(client, db, username="member1")
    bucket_id = await _default_bucket_id(db, admin["household_id"])
    receipt = await _create_receipt(db, bucket_id=bucket_id, user_id=uuid.UUID(admin["id"]))

    # member1 bekommt explizites Edit-Recht auf den (transparenten) Household-Bucket — sonst
    # würde jeder Zugriffsversuch schon an _get_writable_receipt (Bucket-Ebene) mit 403
    # scheitern, ohne die hier eigentlich zu testende, share-spezifische Ersteller-Prüfung
    # überhaupt zu erreichen.
    grant_response = await client.put(
        f"/api/buckets/{bucket_id}/access/{member['id']}", json={"access_level": "edit"}
    )
    assert grant_response.status_code == 200, grant_response.text

    # Admin erstellt einen Link.
    admin_share, _token = await _make_share(
        db, receipt, uuid.UUID(admin["household_id"]), uuid.UUID(admin["id"])
    )
    await db.commit()

    async with await _fresh_client() as member_client:
        login_response = await member_client.post(
            "/api/auth/login", json={"username": "member1", "password": _PASSWORD}
        )
        assert login_response.status_code == 200

        forbidden_response = await member_client.delete(
            f"/api/receipts/{receipt.id}/shares/{admin_share.id}"
        )
        assert forbidden_response.status_code == 403

    # Der Ersteller selbst (Admin) darf widerrufen.
    creator_response = await client.delete(f"/api/receipts/{receipt.id}/shares/{admin_share.id}")
    assert creator_response.status_code == 204

    # Ein von member1 selbst erstellter Link darf von einem Admin widerrufen werden,
    # obwohl der Admin nicht der Ersteller ist.
    member_share, _member_token = await _make_share(
        db, receipt, uuid.UUID(admin["household_id"]), uuid.UUID(member["id"])
    )
    await db.commit()

    admin_revoke_response = await client.delete(
        f"/api/receipts/{receipt.id}/shares/{member_share.id}"
    )
    assert admin_revoke_response.status_code == 204


# --- 8. Verwaltungsliste zeigt volle Historie statt nur aktive Links ----------------------


async def test_list_endpoint_shows_revoked_share_with_revoked_status_instead_of_hiding_it(
    client: AsyncClient, db: AsyncSession
):
    """
    Regressionstest für die eigentliche Änderung dieses Schritts: GET .../shares zeigte
    vorher nur aktive Links (list_active_shares()), ein widerrufener/verbrauchter/
    abgelaufener Link verschwand also sofort aus der Liste. Jetzt zeigt der Endpoint die
    volle Historie inkl. Status-Badge — ein Link darf nach Widerruf nicht aus der Liste
    verschwinden, sondern muss mit status="revoked" weiter auftauchen.
    """
    admin = await _register_admin(client)
    await _mark_totp_enrolled(db, admin["id"])
    bucket_id = await _default_bucket_id(db, admin["household_id"])
    receipt = await _create_receipt(db, bucket_id=bucket_id, user_id=uuid.UUID(admin["id"]))

    create_response = await client.post(
        f"/api/receipts/{receipt.id}/shares",
        json={"single_use": False, "expiry_preset": "7d", "label": "Für Versicherung XY"},
    )
    assert create_response.status_code == 201, create_response.text
    share_id = create_response.json()["id"]
    assert create_response.json()["label"] == "Für Versicherung XY"

    before_revoke = await client.get(f"/api/receipts/{receipt.id}/shares")
    assert before_revoke.status_code == 200
    [item] = before_revoke.json()
    assert item["status"] == "active"
    assert item["label"] == "Für Versicherung XY"

    revoke_response = await client.delete(f"/api/receipts/{receipt.id}/shares/{share_id}")
    assert revoke_response.status_code == 204

    after_revoke = await client.get(f"/api/receipts/{receipt.id}/shares")
    assert after_revoke.status_code == 200
    items = after_revoke.json()
    assert len(items) == 1, "widerrufener Link muss weiter in der Liste auftauchen, nicht verschwinden"
    assert items[0]["id"] == share_id
    assert items[0]["status"] == "revoked"
    assert items[0]["label"] == "Für Versicherung XY"


async def test_create_share_normalizes_blank_label_to_null(client: AsyncClient, db: AsyncSession):
    """Ein leeres/nur-Leerzeichen-Label soll NULL speichern statt "" (siehe
    ReceiptShareCreateRequest._blank_label_to_none)."""
    admin = await _register_admin(client)
    await _mark_totp_enrolled(db, admin["id"])
    bucket_id = await _default_bucket_id(db, admin["household_id"])
    receipt = await _create_receipt(db, bucket_id=bucket_id, user_id=uuid.UUID(admin["id"]))

    response = await client.post(
        f"/api/receipts/{receipt.id}/shares",
        json={"single_use": False, "expiry_preset": "7d", "label": "   "},
    )
    assert response.status_code == 201, response.text
    assert response.json()["label"] is None
