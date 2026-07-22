"""
WebAuthn/Passkey-Integrationstests (Security-Hardening Phase 3, siehe
concepts/security-hardening.md Abschnitt 4.3) — laufen gegen eine echte Postgres-/
Redis-Testinstanz (conftest.py), keine gemockte DB.

Deckt ab, was OHNE echten Browser-Authenticator verifizierbar ist:
- Optionen-Generierung (/register/options, /authenticate/options) liefert plausible,
  spezifikationskonforme JSON-Strukturen.
- Credential-Verwaltung (list/rename/delete) gegen direkt in die Test-DB eingefügte
  Dummy-Credential-Zeilen — reine CRUD-/Ownership-Pfade brauchen keine echte Ceremony.
- passkey_setup_required in /auth/me: True für User ohne Credential, False sobald eine
  Zeile existiert, immer False für Admins.
- _finalize_first_factor()-Verzweigung (Passwort-Login-Regression): weiterhin volle
  Session ohne TOTP-Pflicht, Pre-Auth-Zustand (requires_totp) bei aktivem totp_enabled.

BEWUSSTE GRENZE: die eigentliche kryptographische Verify-Ceremony (register/verify,
authenticate/verify mit einer ECHTEN Signatur) lässt sich nicht ohne echten Browser/
virtuellen WebAuthn-Authenticator (z.B. Chrome-DevTools-Protocol) durchspielen — ein
handgestricktes Fake-Payload scheitert bereits an der clientDataJSON-Origin-Bindung bzw.
der Attestation-/Assertion-Signaturprüfung in py_webauthn. Dieser Pfad bleibt hier
unverifiziert (siehe Bericht der Hauptinstanz für Details zur Grenze).
"""

import json
import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import engine
from app.main import app
from app.models.user import User
from app.models.webauthn_credential import WebauthnCredential

pytestmark = pytest.mark.asyncio

_PASSWORD = "supersecret123"


@pytest_asyncio.fixture(autouse=True)
async def _clean_tables():
    """
    Bewusst lokal in diesem Modul statt in conftest.py (siehe dortiger Docstring) — läuft
    NACH jedem Test (nicht davor), damit ein fehlgeschlagener Test zur Fehlersuche
    inspizierbare Daten in der Test-DB hinterlässt.
    """
    yield
    async with engine.begin() as conn:
        # CASCADE räumt automatisch auch alle Tabellen mit FK auf households/users
        # (buckets, receipts, ai_usage_events, ...) mit ab — kein vollständiges Listing
        # jeder abhängigen Tabelle nötig.
        await conn.execute(
            text(
                "TRUNCATE households, users, webauthn_credentials, audit_log, "
                "household_security_settings, totp_recovery_codes RESTART IDENTITY CASCADE"
            )
        )


async def _register_admin(client: AsyncClient) -> dict:
    response = await client.post(
        "/api/auth/register",
        json={
            "household_name": "Testhaushalt",
            "username": "admin1",
            "email": "admin1@example.com",
            "password": _PASSWORD,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _mark_totp_enrolled(db: AsyncSession, user_id: str) -> None:
    """
    Setzt totp_enabled direkt in der DB statt über den echten Enroll+Confirm-Flow —
    require_totp_enrolled (app/auth/dependencies.py) sperrt Admin-only-Endpoints wie
    /auth/invite sonst mit 403, solange ein frisch registrierter Admin seine (laut
    Konzept 4.1 verpflichtende) TOTP-Einrichtung noch nicht abgeschlossen hat. Die
    Einrichtung selbst ist hier nicht Testgegenstand.
    """
    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one()
    user.totp_enabled = True
    await db.commit()


async def _invite_member(client: AsyncClient, db: AsyncSession, admin_id: str) -> dict:
    await _mark_totp_enrolled(db, admin_id)
    response = await client.post(
        "/api/auth/invite",
        json={"username": "member1", "email": "member1@example.com", "password": _PASSWORD},
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _fresh_client() -> AsyncClient:
    """Eigener Client mit leerem Cookie-Jar — simuliert einen zweiten Browser/eine neue Session."""
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


# --- Optionen-Generierung ---------------------------------------------------------------


async def test_register_options_returns_spec_conformant_json(client: AsyncClient):
    await _register_admin(client)

    response = await client.post("/api/webauthn/register/options")

    assert response.status_code == 200
    options = json.loads(response.json()["options"])
    assert isinstance(options["challenge"], str) and options["challenge"]
    assert options["rp"]["id"]  # aus public_app_url abgeleitete RP-ID (siehe app/config.py)
    assert options["user"]["name"] == "admin1"
    assert isinstance(options["pubKeyCredParams"], list) and options["pubKeyCredParams"]


async def test_register_options_requires_session(client: AsyncClient):
    response = await client.post("/api/webauthn/register/options")
    assert response.status_code == 401


async def test_authenticate_options_is_public_and_plausible_for_unknown_user(client: AsyncClient):
    response = await client.post(
        "/api/webauthn/authenticate/options", json={"username": "does-not-exist"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["options_id"]
    options = json.loads(body["options"])
    assert isinstance(options["challenge"], str) and options["challenge"]
    # Enumeration-Schutz (Security-Review-Nachbesserung): eine leere allowCredentials-
    # Liste würde zuverlässig verraten, dass der Account nicht existiert (normale User
    # sind zur Passkey-Registrierung gezwungen, siehe passkey_setup_required-Gate —
    # praktisch jeder echte Account hat mindestens einen Passkey). Unbekannter Username
    # liefert deshalb genau EINE deterministische Fake-Credential-ID statt einer leeren
    # Liste (webauthn_service.fake_allow_credential_ids).
    assert len(options["allowCredentials"]) == 1
    fake_id = options["allowCredentials"][0]["id"]
    assert fake_id

    # Determinismus: derselbe Username liefert bei einem zweiten Aufruf exakt dieselbe
    # Fake-ID — sonst wäre die Instabilität selbst wieder ein Unterscheidungsmerkmal.
    response_again = await client.post(
        "/api/webauthn/authenticate/options", json={"username": "does-not-exist"}
    )
    options_again = json.loads(response_again.json()["options"])
    assert options_again["allowCredentials"][0]["id"] == fake_id

    # Ein anderer unbekannter Username liefert eine andere Fake-ID (kein statischer Wert).
    response_other = await client.post(
        "/api/webauthn/authenticate/options", json={"username": "also-does-not-exist"}
    )
    options_other = json.loads(response_other.json()["options"])
    assert options_other["allowCredentials"][0]["id"] != fake_id


async def test_authenticate_verify_with_fake_credential_id_fails_generically(
    client: AsyncClient,
):
    """
    Ergänzt den obigen Test: die Fake-Credential-ID aus /authenticate/options darf bei
    /authenticate/verify nie zu einem 500 oder einem abweichenden Fehlerbild führen —
    credential_id_from_authentication_response() liest die ID nur aus dem rohen JSON,
    OHNE Signaturprüfung, deshalb reicht ein minimales Fake-Payload mit dieser ID.
    """
    options_response = await client.post(
        "/api/webauthn/authenticate/options", json={"username": "does-not-exist"}
    )
    options_id = options_response.json()["options_id"]
    fake_id = json.loads(options_response.json()["options"])["allowCredentials"][0]["id"]

    verify_response = await client.post(
        "/api/webauthn/authenticate/verify",
        json={
            "options_id": options_id,
            "credential": json.dumps(
                {
                    "id": fake_id,
                    "rawId": fake_id,
                    "type": "public-key",
                    "response": {
                        "clientDataJSON": "e30",
                        "authenticatorData": "AA",
                        "signature": "AA",
                    },
                }
            ),
        },
    )

    assert verify_response.status_code == 401
    assert verify_response.json()["detail"] == "Ungültige Anmeldedaten"


async def test_authenticate_options_lists_allow_credentials_for_known_user(
    client: AsyncClient, db: AsyncSession
):
    admin = await _register_admin(client)
    db.add(
        WebauthnCredential(
            user_id=uuid.UUID(admin["id"]),
            credential_id="dummy-credential-id-abc",
            public_key=b"\x00\x01\x02\x03",
            device_label="Dummy",
        )
    )
    await db.commit()

    response = await client.post("/api/webauthn/authenticate/options", json={"username": "admin1"})

    assert response.status_code == 200
    options = json.loads(response.json()["options"])
    assert len(options["allowCredentials"]) == 1
    assert options["allowCredentials"][0]["id"]  # base64url-kodierte Credential-ID


# --- Credential-Verwaltung (Dummy-Zeilen, keine echte Ceremony) -------------------------


async def test_credential_management_list_rename_delete(client: AsyncClient, db: AsyncSession):
    admin = await _register_admin(client)
    credential = WebauthnCredential(
        user_id=uuid.UUID(admin["id"]),
        credential_id="dummy-credential-id-xyz",
        public_key=b"\x00\x01",
        device_label="MacBook Touch ID",
    )
    db.add(credential)
    await db.commit()
    await db.refresh(credential)

    list_response = await client.get("/api/webauthn/credentials")
    assert list_response.status_code == 200
    body = list_response.json()
    assert len(body) == 1
    assert body[0]["device_label"] == "MacBook Touch ID"
    # Niemals public_key/credential_id roh exponieren (siehe Auftrag).
    assert "public_key" not in body[0]
    assert "credential_id" not in body[0]

    rename_response = await client.patch(
        f"/api/webauthn/credentials/{credential.id}", json={"device_label": "Neuer Name"}
    )
    assert rename_response.status_code == 200
    assert rename_response.json()["device_label"] == "Neuer Name"

    delete_response = await client.delete(f"/api/webauthn/credentials/{credential.id}")
    assert delete_response.status_code == 204

    list_after = await client.get("/api/webauthn/credentials")
    assert list_after.json() == []


async def test_cannot_manage_foreign_credential(client: AsyncClient, db: AsyncSession):
    admin = await _register_admin(client)
    member = await _invite_member(client, db, admin["id"])

    credential = WebauthnCredential(
        user_id=uuid.UUID(member["id"]),
        credential_id="dummy-credential-belongs-to-member",
        public_key=b"\x00",
        device_label="Members Key",
    )
    db.add(credential)
    await db.commit()
    await db.refresh(credential)

    # Weiterhin als Admin eingeloggt (Session-Cookie aus _register_admin) — versucht, das
    # Credential eines anderen Haushaltsmitglieds zu verwalten.
    rename_response = await client.patch(
        f"/api/webauthn/credentials/{credential.id}", json={"device_label": "Hack"}
    )
    assert rename_response.status_code == 404

    delete_response = await client.delete(f"/api/webauthn/credentials/{credential.id}")
    assert delete_response.status_code == 404


# --- passkey_setup_required --------------------------------------------------------------


async def test_passkey_setup_required_true_for_user_without_credential(
    client: AsyncClient, db: AsyncSession
):
    admin = await _register_admin(client)
    member = await _invite_member(client, db, admin["id"])
    assert member["passkey_setup_required"] is True

    async with await _fresh_client() as member_client:
        login_response = await member_client.post(
            "/api/auth/login", json={"username": "member1", "password": _PASSWORD}
        )
        assert login_response.status_code == 200
        assert login_response.json()["passkey_setup_required"] is True

        me_response = await member_client.get("/api/auth/me")
        assert me_response.json()["passkey_setup_required"] is True


async def test_passkey_setup_required_false_after_credential_registered(
    client: AsyncClient, db: AsyncSession
):
    admin = await _register_admin(client)
    member = await _invite_member(client, db, admin["id"])

    db.add(
        WebauthnCredential(
            user_id=uuid.UUID(member["id"]),
            credential_id="dummy-credential-member",
            public_key=b"\x00",
            device_label="Members Key",
        )
    )
    await db.commit()

    async with await _fresh_client() as member_client:
        login_response = await member_client.post(
            "/api/auth/login", json={"username": "member1", "password": _PASSWORD}
        )
        assert login_response.json()["passkey_setup_required"] is False


async def test_passkey_setup_required_always_false_for_admin(client: AsyncClient):
    admin = await _register_admin(client)
    assert admin["passkey_setup_required"] is False  # Admin, unabhängig von Passkey-Besitz

    me_response = await client.get("/api/auth/me")
    assert me_response.json()["passkey_setup_required"] is False


# --- _finalize_first_factor()-Verzweigung (Passwort-Login-Regression) -------------------


async def test_password_login_without_totp_still_creates_full_session(client: AsyncClient):
    await _register_admin(client)

    async with await _fresh_client() as fresh_client:
        response = await fresh_client.post(
            "/api/auth/login", json={"username": "admin1", "password": _PASSWORD}
        )
        assert response.status_code == 200
        body = response.json()
        assert body["username"] == "admin1"
        assert "passkey_setup_required" in body
        assert "receiptly_session" in response.cookies

        # Session tatsächlich nutzbar — nicht nur der Response-Body sieht richtig aus.
        me_response = await fresh_client.get("/api/auth/me")
        assert me_response.status_code == 200


async def test_password_login_with_totp_enabled_returns_pending_state_not_session(
    client: AsyncClient, db: AsyncSession
):
    admin = await _register_admin(client)
    user_result = await db.execute(select(User).where(User.id == uuid.UUID(admin["id"])))
    user = user_result.scalar_one()
    user.totp_enabled = True
    await db.commit()

    async with await _fresh_client() as fresh_client:
        response = await fresh_client.post(
            "/api/auth/login", json={"username": "admin1", "password": _PASSWORD}
        )
        assert response.status_code == 200
        assert response.json() == {"requires_totp": True}
        assert "receiptly_pending_2fa" in response.cookies
        assert "receiptly_session" not in response.cookies

        # Kein App-Zugriff über den Pre-Auth-Zustand.
        me_response = await fresh_client.get("/api/auth/me")
        assert me_response.status_code == 401
