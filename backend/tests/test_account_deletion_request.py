"""
Konto-Löschung Stufe A (Löschantrag, DSGVO Art. 17, siehe
concepts/konto-loeschen-datenexport.md 3.2/3.3) — Admin-Gate, erfolgreicher Antrag samt
Session-Invalidierung, Re-Auth über Passwort/TOTP/Passkey-Bestätigung, sowie der
Login-Hook, der einen Login-Versuch während der Karenzzeit auf die
Reaktivierungs-Bestätigung umlenkt statt eine Session zu erstellen.

Läuft wie test_webauthn.py/test_passkey_exclusive_login.py gegen eine echte Postgres-/
Redis-Testinstanz (conftest.py), keine gemockte DB. Eigene, lokale `_clean_tables` +
Redis-Flush aus demselben Grund wie test_passkey_exclusive_login.py (mehrere Logins mit
denselben Usernamen über Testfälle hinweg würden sonst am `login_ip_username`-Rate-Limit
scheitern).

BEWUSSTE GRENZE (wie test_webauthn.py): eine echte Passkey-Verify-Ceremony lässt sich
ohne Browser-Authenticator nicht durchspielen — der Passkey-Re-Auth-Zweig wird deshalb
nur bis zur Options-Generierung und dem "Passkey-Bestätigung erforderlich"-Fehlerfall
(fehlende credential/options) verifiziert, nicht die eigentliche Signaturprüfung.
"""

import io
import json
import uuid
import zipfile
from datetime import UTC, datetime, timedelta

import pyotp
import pytest
import pytest_asyncio
import redis.asyncio as redis
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import engine
from app.main import app
from app.models.audit_log import AuditLog
from app.models.user import User, UserRole
from app.models.webauthn_credential import WebauthnCredential
from app.services.crypto import encrypt_secret
from app.services.totp import generate_secret

pytestmark = pytest.mark.asyncio

_PASSWORD = "supersecret123"
_DELETION_PATH = "/api/account/deletion"
_EXPORT_PATH = "/api/account/export"
_REACTIVATE_PATH = "/api/account/reactivate"
_POLICY_PATH = "/api/settings/security-policy"


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
    redis_client = redis.from_url(get_settings().redis_url, decode_responses=True)
    try:
        await redis_client.flushdb()
    finally:
        await redis_client.aclose()


def _policy_payload(*, exclusive: bool) -> dict:
    return {
        "totp_required_for_household": False,
        "audit_retention_days": 90,
        "log_attempted_username": True,
        "passkey_exclusive_login": exclusive,
    }


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
    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one()
    user.totp_enabled = True
    await db.commit()


async def _enable_real_totp(db: AsyncSession, user_id: str) -> str:
    """Aktiviert TOTP mit einem echten, entschlüsselbaren Secret — gibt das Klartext-Secret zurück."""
    secret = generate_secret()
    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one()
    user.totp_enabled = True
    user.totp_secret = encrypt_secret(secret)
    await db.commit()
    return secret


async def _invite_member(client: AsyncClient, username: str = "member1") -> dict:
    response = await client.post(
        "/api/auth/invite",
        json={"username": username, "email": f"{username}@example.com", "password": _PASSWORD},
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _fresh_client() -> AsyncClient:
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


# --- Admin-Gate --------------------------------------------------------------------------


async def test_deletion_blocked_when_sole_admin_with_other_members(client: AsyncClient, db: AsyncSession):
    admin = await _register_admin(client)
    secret = await _enable_real_totp(db, admin["id"])
    await _invite_member(client)

    response = await client.post(
        _DELETION_PATH,
        json={
            "current_password": _PASSWORD,
            "confirmation_text": "admin1",
            "totp_code": pyotp.TOTP(secret).now(),
        },
    )

    assert response.status_code == 409
    assert "einzige" in response.json()["detail"] or "Admin" in response.json()["detail"]

    result = await db.execute(select(User).where(User.username == "admin1"))
    user = result.scalar_one()
    assert user.scheduled_deletion_at is None


async def test_deletion_succeeds_once_admin_gate_no_longer_applies(
    client: AsyncClient, db: AsyncSession
):
    """Sobald ein zweiter Admin existiert, greift das Gate nicht mehr."""
    admin = await _register_admin(client)
    secret = await _enable_real_totp(db, admin["id"])
    member = await _invite_member(client)

    result = await db.execute(select(User).where(User.id == uuid.UUID(member["id"])))
    member_user = result.scalar_one()
    member_user.role = UserRole.ADMIN
    await db.commit()

    response = await client.post(
        _DELETION_PATH,
        json={
            "current_password": _PASSWORD,
            "confirmation_text": "LÖSCHEN",
            "totp_code": pyotp.TOTP(secret).now(),
        },
    )
    assert response.status_code == 200
    assert response.json()["scheduled_deletion_at"] is not None


# --- Erfolgreicher Antrag + Session-Invalidierung ----------------------------------------


async def test_deletion_request_succeeds_and_sets_scheduled_deletion_at(
    client: AsyncClient, db: AsyncSession
):
    admin = await _register_admin(client)
    secret = await _enable_real_totp(db, admin["id"])

    response = await client.post(
        _DELETION_PATH,
        json={
            "current_password": _PASSWORD,
            "confirmation_text": "LÖSCHEN",
            "totp_code": pyotp.TOTP(secret).now(),
        },
    )

    assert response.status_code == 200
    body = response.json()
    scheduled_at = datetime.fromisoformat(body["scheduled_deletion_at"])
    now = datetime.now(UTC)
    assert timedelta(days=13) < (scheduled_at - now) < timedelta(days=15)

    result = await db.execute(select(User).where(User.username == "admin1"))
    user = result.scalar_one()
    assert user.scheduled_deletion_at is not None

    audit_result = await db.execute(
        select(AuditLog).where(AuditLog.event_type == "account_deletion_requested")
    )
    assert audit_result.scalar_one_or_none() is not None


async def test_deletion_request_invalidates_all_sessions_including_current(
    client: AsyncClient, db: AsyncSession
):
    admin = await _register_admin(client)
    secret = await _enable_real_totp(db, admin["id"])

    response = await client.post(
        _DELETION_PATH,
        json={
            "current_password": _PASSWORD,
            "confirmation_text": "LÖSCHEN",
            "totp_code": pyotp.TOTP(secret).now(),
        },
    )
    assert response.status_code == 200

    me_response = await client.get("/api/auth/me")
    assert me_response.status_code == 401


# --- Re-Auth: Tipp-Bestätigung + Passwort -------------------------------------------------


async def test_deletion_rejects_wrong_confirmation_text(client: AsyncClient, db: AsyncSession):
    admin = await _register_admin(client)
    await _enable_real_totp(db, admin["id"])

    response = await client.post(
        _DELETION_PATH,
        json={"current_password": _PASSWORD, "confirmation_text": "falsch"},
    )

    assert response.status_code == 400
    result = await db.execute(select(User).where(User.username == "admin1"))
    assert result.scalar_one().scheduled_deletion_at is None


async def test_deletion_rejects_wrong_password(client: AsyncClient, db: AsyncSession):
    admin = await _register_admin(client)
    await _enable_real_totp(db, admin["id"])

    response = await client.post(
        _DELETION_PATH,
        json={"current_password": "definitiv-falsch", "confirmation_text": "LÖSCHEN"},
    )

    assert response.status_code == 400
    assert "Passwort" in response.json()["detail"]
    result = await db.execute(select(User).where(User.username == "admin1"))
    assert result.scalar_one().scheduled_deletion_at is None


async def test_deletion_requires_password_field_when_not_passkey_exclusive(
    client: AsyncClient, db: AsyncSession
):
    admin = await _register_admin(client)
    await _enable_real_totp(db, admin["id"])

    response = await client.post(_DELETION_PATH, json={"confirmation_text": "LÖSCHEN"})

    assert response.status_code == 400
    assert "Passwort" in response.json()["detail"]


# --- Re-Auth: TOTP ------------------------------------------------------------------------


async def test_deletion_requires_totp_code_when_enabled(client: AsyncClient, db: AsyncSession):
    admin = await _register_admin(client)
    secret = await _enable_real_totp(db, admin["id"])

    missing_code = await client.post(
        _DELETION_PATH,
        json={"current_password": _PASSWORD, "confirmation_text": "LÖSCHEN"},
    )
    assert missing_code.status_code == 400
    assert "TOTP" in missing_code.json()["detail"]

    wrong_code = await client.post(
        _DELETION_PATH,
        json={
            "current_password": _PASSWORD,
            "confirmation_text": "LÖSCHEN",
            "totp_code": "000000",
        },
    )
    assert wrong_code.status_code == 400

    correct_code = pyotp.TOTP(secret).now()
    success = await client.post(
        _DELETION_PATH,
        json={
            "current_password": _PASSWORD,
            "confirmation_text": "LÖSCHEN",
            "totp_code": correct_code,
        },
    )
    assert success.status_code == 200

    result = await db.execute(select(User).where(User.username == "admin1"))
    assert result.scalar_one().scheduled_deletion_at is not None


# --- Re-Auth: Passkey-Bestätigung (nur bis zur fehlenden Signatur, siehe Modul-Docstring) --


async def test_deletion_requires_passkey_when_exclusive_login_active(
    client: AsyncClient, db: AsyncSession
):
    admin = await _register_admin(client)
    await _mark_totp_enrolled(db, admin["id"])
    db.add(
        WebauthnCredential(
            user_id=uuid.UUID(admin["id"]),
            credential_id="dummy-credential-abc",
            public_key=b"\x00\x01",
            device_label="Testgerät",
        )
    )
    await db.commit()

    activate = await client.put(_POLICY_PATH, json=_policy_payload(exclusive=True))
    assert activate.status_code == 200

    # Passwort allein reicht nicht mehr — die Passkey-Bestätigung fehlt.
    response = await client.post(
        _DELETION_PATH,
        json={"current_password": _PASSWORD, "confirmation_text": "LÖSCHEN"},
    )
    assert response.status_code == 400
    assert "Passkey" in response.json()["detail"]

    result = await db.execute(select(User).where(User.username == "admin1"))
    assert result.scalar_one().scheduled_deletion_at is None


async def test_deletion_passkey_options_endpoint_scoped_to_own_credentials(
    client: AsyncClient, db: AsyncSession
):
    admin = await _register_admin(client)
    await _mark_totp_enrolled(db, admin["id"])
    db.add(
        WebauthnCredential(
            user_id=uuid.UUID(admin["id"]),
            credential_id="dummy-credential-own",
            public_key=b"\x00\x01",
            device_label="Testgerät",
        )
    )
    await db.commit()

    response = await client.post("/api/account/deletion/reauth/passkey-options")

    assert response.status_code == 200
    body = response.json()
    assert body["options_id"]
    assert body["options"]


# --- Reaktivierung während der Karenzzeit -------------------------------------------------


async def test_login_during_grace_period_offers_reactivation_then_reactivates(
    client: AsyncClient, db: AsyncSession
):
    """
    Nutzt bewusst ein normales Mitglied (Rolle USER) statt eines Admins: require_totp_
    enrolled verlangt totp_enabled nur für Admins, member1 kann sich also ohne TOTP-Setup
    normal per Passwort einloggen — das hält den Test frei von TOTP-Verkettung und deckt
    trotzdem exakt den Login-Hook ab (_finalize_first_factor, app/api/auth.py).
    """
    admin = await _register_admin(client)
    await _mark_totp_enrolled(db, admin["id"])
    await _invite_member(client)

    async with await _fresh_client() as member_client:
        login_response = await member_client.post(
            "/api/auth/login", json={"username": "member1", "password": _PASSWORD}
        )
        assert login_response.status_code == 200
        assert "receiptly_session" in login_response.cookies

        deletion_response = await member_client.post(
            _DELETION_PATH,
            json={"current_password": _PASSWORD, "confirmation_text": "member1"},
        )
        assert deletion_response.status_code == 200

        # Aktuelle Session wurde durch die Löschanfrage selbst invalidiert.
        assert (await member_client.get("/api/auth/me")).status_code == 401

    async with await _fresh_client() as reactivation_client:
        second_login = await reactivation_client.post(
            "/api/auth/login", json={"username": "member1", "password": _PASSWORD}
        )
        assert second_login.status_code == 200
        body = second_login.json()
        assert body["requires_reactivation"] is True
        assert body["scheduled_deletion_at"] is not None
        assert "receiptly_pending_reactivation" in second_login.cookies
        assert "receiptly_session" not in second_login.cookies

        reactivate_response = await reactivation_client.post(_REACTIVATE_PATH)
        assert reactivate_response.status_code == 200
        assert reactivate_response.json()["username"] == "member1"
        assert "receiptly_session" in reactivate_response.cookies

        me_response = await reactivation_client.get("/api/auth/me")
        assert me_response.status_code == 200

    result = await db.execute(select(User).where(User.username == "member1"))
    assert result.scalar_one().scheduled_deletion_at is None


async def test_reactivate_without_pending_cookie_rejected(client: AsyncClient):
    async with await _fresh_client() as fresh_client:
        response = await fresh_client.post(_REACTIVATE_PATH)
        assert response.status_code == 401


# --- Daten-Export --------------------------------------------------------------------------


async def test_export_returns_zip_with_expected_structure(client: AsyncClient, db: AsyncSession):
    admin = await _register_admin(client)
    await _mark_totp_enrolled(db, admin["id"])

    response = await client.get(_EXPORT_PATH)

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"

    archive = zipfile.ZipFile(io.BytesIO(response.content))
    names = archive.namelist()
    assert "daten.json" in names
    assert "README.txt" in names

    data = json.loads(archive.read("daten.json"))
    assert data["profil"]["username"] == "admin1"
    assert data["belege"] == []
    assert "password_hash" not in json.dumps(data)
    assert "totp_secret" not in json.dumps(data)
