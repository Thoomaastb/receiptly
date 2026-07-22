"""
Passkey-Exklusiv-Login-Tests (Security-Hardening Phase 4, siehe
concepts/security-hardening.md Abschnitt 4.1) — deckt die drei Bausteine des Auftrags ab:
Precondition-Gate (GET-Live-Status + PUT-Durchsetzung), Passwort-Login-Ablehnung bei
aktivem Schalter, Löschschutz für den letzten Passkey. Zusätzlich der vom Auftrag
explizit verlangte Edge-Case-Nachweis: ein NACH Aktivierung eingeladenes Mitglied ohne
Passkey wäre ohne den zusätzlich eingebauten Invite-Guard unrettbar ausgesperrt (weder
Passwort- noch Passkey-Login möglich) — siehe
test_member_without_passkey_locked_out_of_password_login_when_exclusive_active.

Läuft wie test_webauthn.py gegen eine echte Postgres-/Redis-Testinstanz (conftest.py),
keine gemockte DB. Eigene, lokale `_clean_tables` aus demselben Grund wie dort (läuft
NACH jedem Test, damit ein Fehlschlag inspizierbare Daten hinterlässt).

BEWUSSTE GRENZE (wie test_webauthn.py): der eigentliche Passkey-Login
(/webauthn/authenticate/verify mit einer echten Signatur) lässt sich ohne echten
Browser-Authenticator nicht durchspielen. Dass Baustein 2 (Login-Ablehnung) den
Passkey-Pfad NICHT berührt, wird deshalb nur indirekt verifiziert: der öffentliche
erste Schritt (/webauthn/authenticate/options) bleibt bei aktivem Schalter erreichbar,
und app/api/webauthn.py enthält (Code-Review-Fakt, nicht testbar) keinerlei Referenz auf
`passkey_exclusive_login` im Authenticate-Pfad.
"""

import asyncio
import uuid

import pytest
import pytest_asyncio
import redis.asyncio as redis
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.security import hash_password
from app.config import get_settings
from app.database import engine
from app.main import app
from app.models.audit_log import AuditLog
from app.models.household_security_settings import HouseholdSecuritySettings
from app.models.user import User, UserRole
from app.models.webauthn_credential import WebauthnCredential

pytestmark = pytest.mark.asyncio

_PASSWORD = "supersecret123"

_POLICY_PATH = "/api/settings/security-policy"
_GATE_PATH = "/api/settings/security-policy/passkey-exclusive-gate"


def _policy_payload(*, exclusive: bool) -> dict:
    return {
        "totp_required_for_household": False,
        "audit_retention_days": 90,
        "log_attempted_username": True,
        "passkey_exclusive_login": exclusive,
    }


@pytest_asyncio.fixture(autouse=True)
async def _clean_tables():
    """
    Zusätzlich zur Tabellen-Bereinigung aus test_webauthn.py ein Redis-FLUSHDB: dieses
    Modul ruft /auth/login öfter mit derselben Username/IP-Kombination auf als
    test_webauthn.py (mehrere Aktivierungs-/Ablehnungs-Szenarien pro Test-Session) — ohne
    Flush würde der `login_ip_username`-Rate-Limit-Zähler (app/auth/rate_limit.py, Redis,
    NICHT von der Postgres-Truncate erfasst) über Testdatei-Grenzen hinweg bestehen bleiben
    und andere Tests mit 429 statt des erwarteten Status scheitern lassen (in der Praxis
    beobachtet: test_webauthn.py-Logins schlugen dadurch fehl). Ein vollständiger FLUSHDB
    ist hier unkritisch — jeder Test baut seinen State (Registrierung, Sessions,
    Challenges) ohnehin frisch auf.
    """
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
    """Wie test_webauthn.py — require_admin/require_totp_enrolled sperrt Admin-only-Endpoints sonst mit 403."""
    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one()
    user.totp_enabled = True
    await db.commit()


async def _add_credential(
    db: AsyncSession, user_id: str, device_label: str = "Testgerät"
) -> WebauthnCredential:
    credential = WebauthnCredential(
        user_id=uuid.UUID(user_id),
        credential_id=f"dummy-{uuid.uuid4()}",
        public_key=b"\x00\x01",
        device_label=device_label,
    )
    db.add(credential)
    await db.commit()
    await db.refresh(credential)
    return credential


async def _fresh_client() -> AsyncClient:
    """Eigener Client mit leerem Cookie-Jar — simuliert einen zweiten Browser/eine neue Session."""
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


def _pause_first_call(original, *, pause_before_effect: bool = False):
    """
    Wrappt eine beliebige Coroutine-Funktion (lock_household_security ODER record_event,
    je nach Testfall — daher generisch über *args/**kwargs statt einer festen Signatur)
    so, dass der erste tatsächlich ankommende Aufruf pausiert, bis der Test ihn über
    `hold` freigibt.

    `pause_before_effect` steuert WANN pausiert wird, je nachdem ob `original(...)` selbst
    schon die commit-auslösende Wirkung ist:
    - False (Default, für lock_household_security): pausiert NACH original(...) — der
      Lock ist bereits erworben, nur das Timing danach (vor dem Rest der Transaktion)
      wird kontrolliert.
    - True (für record_event): pausiert VOR original(...) — record_event committet
      intern selbst, ein Pausieren danach wäre zu spät, die Transaktion wäre schon zu.

    `calls["count"]` wird zwischen zwei parallelen Tasks nie inkonsistent erhöht, weil
    Python zwischen zwei awaits stets nur einen Task laufen lässt (kein echtes
    Multithreading) — die Reihenfolge, WER zuerst hier ankommt, hängt aber davon ab, ob
    vorheriger Code (z.B. der echte Advisory-Lock) den zweiten Aufruf schon real in
    Postgres serialisiert hat oder nicht (Mutationstest: zweiter Aufruf kommt unbehindert
    ebenfalls durch).

    Damit lässt sich das in den Race-Condition-Tests unten benötigte Überlapp-Fenster
    deterministisch erzwingen, statt zu hoffen, dass zwei `asyncio.gather()`-Requests
    zufällig im richtigen Moment überlappen.
    """
    calls = {"count": 0}
    started = asyncio.Event()
    hold = asyncio.Event()

    async def wrapper(*args, **kwargs):
        calls["count"] += 1
        is_first = calls["count"] == 1
        if pause_before_effect and is_first:
            started.set()
            await hold.wait()
        result = await original(*args, **kwargs)
        if not pause_before_effect and is_first:
            started.set()
            await hold.wait()
        return result

    return wrapper, started, hold


# --- Baustein 1: Precondition-Gate --------------------------------------------------------


async def test_gate_status_reports_missing_then_eligible(client: AsyncClient, db: AsyncSession):
    admin = await _register_admin(client)
    await _mark_totp_enrolled(db, admin["id"])

    before = await client.get(_GATE_PATH)
    assert before.status_code == 200
    body_before = before.json()
    assert body_before == {
        "eligible": False,
        "total_members": 1,
        "missing_count": 1,
        "missing_usernames": ["admin1"],
    }

    await _add_credential(db, admin["id"])

    after = await client.get(_GATE_PATH)
    body_after = after.json()
    assert body_after == {
        "eligible": True,
        "total_members": 1,
        "missing_count": 0,
        "missing_usernames": [],
    }


async def test_gate_status_and_put_require_admin(client: AsyncClient, db: AsyncSession):
    admin = await _register_admin(client)
    await _mark_totp_enrolled(db, admin["id"])
    invite_response = await client.post(
        "/api/auth/invite",
        json={"username": "member1", "email": "member1@example.com", "password": _PASSWORD},
    )
    assert invite_response.status_code == 201

    async with await _fresh_client() as member_client:
        login_response = await member_client.post(
            "/api/auth/login", json={"username": "member1", "password": _PASSWORD}
        )
        assert login_response.status_code == 200

        assert (await member_client.get(_GATE_PATH)).status_code == 403
        assert (
            await member_client.put(_POLICY_PATH, json=_policy_payload(exclusive=True))
        ).status_code == 403


async def test_activation_rejected_when_member_missing_passkey(
    client: AsyncClient, db: AsyncSession
):
    admin = await _register_admin(client)
    await _mark_totp_enrolled(db, admin["id"])
    # Admin hat bewusst noch keinen Passkey registriert.

    response = await client.put(_POLICY_PATH, json=_policy_payload(exclusive=True))

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["eligible"] is False
    assert detail["missing_count"] == 1
    assert detail["missing_usernames"] == ["admin1"]

    # Nichts darf trotz Ablehnung persistiert worden sein (kein Teil-Update).
    result = await db.execute(select(HouseholdSecuritySettings))
    settings_row = result.scalar_one_or_none()
    assert settings_row is None or settings_row.passkey_exclusive_login is False


async def test_activation_allowed_once_all_members_have_passkey(
    client: AsyncClient, db: AsyncSession
):
    admin = await _register_admin(client)
    await _mark_totp_enrolled(db, admin["id"])
    await _add_credential(db, admin["id"])

    response = await client.put(_POLICY_PATH, json=_policy_payload(exclusive=True))

    assert response.status_code == 200
    assert response.json()["passkey_exclusive_login"] is True


async def test_activation_rejected_when_only_one_of_two_members_has_passkey(
    client: AsyncClient, db: AsyncSession
):
    admin = await _register_admin(client)
    await _mark_totp_enrolled(db, admin["id"])
    await _add_credential(db, admin["id"])
    invite_response = await client.post(
        "/api/auth/invite",
        json={"username": "member1", "email": "member1@example.com", "password": _PASSWORD},
    )
    assert invite_response.status_code == 201
    # member1 hat bewusst KEINEN Passkey.

    response = await client.put(_POLICY_PATH, json=_policy_payload(exclusive=True))

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["total_members"] == 2
    assert detail["missing_count"] == 1
    assert detail["missing_usernames"] == ["member1"]


async def test_deactivation_always_allowed_even_without_precondition(
    client: AsyncClient, db: AsyncSession
):
    admin = await _register_admin(client)
    await _mark_totp_enrolled(db, admin["id"])

    # Inkonsistenten Zustand direkt in der DB erzeugen (Schalter an, kein Passkey) — so
    # ein Zustand sollte über die API nicht entstehen können, aber der Rettungsweg
    # (Deaktivieren, Konzept Q18) muss unabhängig davon IMMER funktionieren.
    db.add(HouseholdSecuritySettings(
        household_id=uuid.UUID(admin["household_id"]), passkey_exclusive_login=True
    ))
    await db.commit()

    response = await client.put(_POLICY_PATH, json=_policy_payload(exclusive=False))

    assert response.status_code == 200
    assert response.json()["passkey_exclusive_login"] is False


# --- Baustein 2: Login-Ablehnung ----------------------------------------------------------


async def test_password_login_rejected_when_exclusive_active(
    client: AsyncClient, db: AsyncSession
):
    admin = await _register_admin(client)
    await _mark_totp_enrolled(db, admin["id"])
    await _add_credential(db, admin["id"])
    activate = await client.put(_POLICY_PATH, json=_policy_payload(exclusive=True))
    assert activate.status_code == 200

    async with await _fresh_client() as fresh_client:
        login_response = await fresh_client.post(
            "/api/auth/login", json={"username": "admin1", "password": _PASSWORD}
        )
        assert login_response.status_code == 403
        assert "Passkey" in login_response.json()["detail"]
        assert "receiptly_session" not in login_response.cookies
        assert "receiptly_pending_2fa" not in login_response.cookies

    audit_result = await db.execute(
        select(AuditLog).where(AuditLog.event_type == "password_login_blocked")
    )
    assert audit_result.scalar_one_or_none() is not None


async def test_password_login_rejected_even_with_wrong_password(
    client: AsyncClient, db: AsyncSession
):
    """
    Beweist, dass die Ablehnung VOR verify_password greift (Baustein-2-Design-
    Entscheidung, analog zum bestehenden Rate-Limit-vor-Passwort-Muster in login()) —
    ein falsches Passwort ändert am 403 nichts, es wird nie 401.
    """
    admin = await _register_admin(client)
    await _mark_totp_enrolled(db, admin["id"])
    await _add_credential(db, admin["id"])
    activate = await client.put(_POLICY_PATH, json=_policy_payload(exclusive=True))
    assert activate.status_code == 200

    async with await _fresh_client() as fresh_client:
        login_response = await fresh_client.post(
            "/api/auth/login", json={"username": "admin1", "password": "definitiv-falsch"}
        )
        assert login_response.status_code == 403


async def test_password_login_works_again_after_deactivation(
    client: AsyncClient, db: AsyncSession
):
    """
    `_mark_totp_enrolled` setzt beim Admin (Vorbedingung für require_admin/require_totp_
    enrolled, siehe Helper oben) auch `totp_enabled=True` — nach der Deaktivierung landet
    ein erfolgreicher Passwort-Login deshalb korrekt im Pending-2FA-Zustand statt direkt
    in einer vollen Session (dieselbe Verzweigung wie in test_webauthn.py). Entscheidend
    hier ist nur: die Passwort-Prüfung selbst wird wieder erreicht (kein 403 mehr) — genau
    das beweist `requires_totp: true` plus das Pending-Cookie, ein 403 wäre vor der
    Passwort-Prüfung aufgetreten (siehe test_password_login_rejected_even_with_wrong_password).
    """
    admin = await _register_admin(client)
    await _mark_totp_enrolled(db, admin["id"])
    await _add_credential(db, admin["id"])
    await client.put(_POLICY_PATH, json=_policy_payload(exclusive=True))
    deactivate = await client.put(_POLICY_PATH, json=_policy_payload(exclusive=False))
    assert deactivate.status_code == 200

    async with await _fresh_client() as fresh_client:
        login_response = await fresh_client.post(
            "/api/auth/login", json={"username": "admin1", "password": _PASSWORD}
        )
        assert login_response.status_code == 200
        assert login_response.json() == {"requires_totp": True}
        assert "receiptly_pending_2fa" in login_response.cookies


async def test_passkey_login_options_endpoint_still_reachable_when_exclusive_active(
    client: AsyncClient, db: AsyncSession
):
    """Baustein 2 darf ausschließlich den Passwort-Pfad sperren — der Passkey-Login-Weg bleibt unangetastet."""
    admin = await _register_admin(client)
    await _mark_totp_enrolled(db, admin["id"])
    await _add_credential(db, admin["id"])
    activate = await client.put(_POLICY_PATH, json=_policy_payload(exclusive=True))
    assert activate.status_code == 200

    async with await _fresh_client() as fresh_client:
        options_response = await fresh_client.post(
            "/api/webauthn/authenticate/options", json={"username": "admin1"}
        )
        assert options_response.status_code == 200


# --- Baustein 3: Löschschutz letzter Passkey ----------------------------------------------


async def test_delete_last_credential_blocked_when_exclusive_active(
    client: AsyncClient, db: AsyncSession
):
    admin = await _register_admin(client)
    await _mark_totp_enrolled(db, admin["id"])
    credential = await _add_credential(db, admin["id"])
    activate = await client.put(_POLICY_PATH, json=_policy_payload(exclusive=True))
    assert activate.status_code == 200

    delete_response = await client.delete(f"/api/webauthn/credentials/{credential.id}")
    assert delete_response.status_code == 409

    list_response = await client.get("/api/webauthn/credentials")
    assert len(list_response.json()) == 1

    audit_result = await db.execute(
        select(AuditLog).where(AuditLog.event_type == "passkey_delete_blocked")
    )
    assert audit_result.scalar_one_or_none() is not None


async def test_delete_last_credential_allowed_when_exclusive_inactive(
    client: AsyncClient, db: AsyncSession
):
    admin = await _register_admin(client)
    await _mark_totp_enrolled(db, admin["id"])
    credential = await _add_credential(db, admin["id"])
    # Schalter bewusst NICHT aktiviert.

    delete_response = await client.delete(f"/api/webauthn/credentials/{credential.id}")
    assert delete_response.status_code == 204


async def test_delete_non_last_credential_allowed_when_exclusive_active(
    client: AsyncClient, db: AsyncSession
):
    admin = await _register_admin(client)
    await _mark_totp_enrolled(db, admin["id"])
    credential_a = await _add_credential(db, admin["id"], device_label="Erst")
    await _add_credential(db, admin["id"], device_label="Zweit")
    activate = await client.put(_POLICY_PATH, json=_policy_payload(exclusive=True))
    assert activate.status_code == 200

    delete_response = await client.delete(f"/api/webauthn/credentials/{credential_a.id}")
    assert delete_response.status_code == 204

    list_response = await client.get("/api/webauthn/credentials")
    remaining = list_response.json()
    assert len(remaining) == 1
    assert remaining[0]["device_label"] == "Zweit"


# --- Edge Case: neues Mitglied nach Aktivierung -------------------------------------------


async def test_invite_rejected_while_exclusive_login_active(
    client: AsyncClient, db: AsyncSession
):
    admin = await _register_admin(client)
    await _mark_totp_enrolled(db, admin["id"])
    await _add_credential(db, admin["id"])
    activate = await client.put(_POLICY_PATH, json=_policy_payload(exclusive=True))
    assert activate.status_code == 200

    invite_response = await client.post(
        "/api/auth/invite",
        json={"username": "member1", "email": "member1@example.com", "password": _PASSWORD},
    )
    assert invite_response.status_code == 409

    result = await db.execute(select(User).where(User.username == "member1"))
    assert result.scalar_one_or_none() is None


async def test_invite_works_again_after_deactivation(client: AsyncClient, db: AsyncSession):
    admin = await _register_admin(client)
    await _mark_totp_enrolled(db, admin["id"])
    await _add_credential(db, admin["id"])
    await client.put(_POLICY_PATH, json=_policy_payload(exclusive=True))
    deactivate = await client.put(_POLICY_PATH, json=_policy_payload(exclusive=False))
    assert deactivate.status_code == 200

    invite_response = await client.post(
        "/api/auth/invite",
        json={"username": "member1", "email": "member1@example.com", "password": _PASSWORD},
    )
    assert invite_response.status_code == 201


async def test_member_without_passkey_locked_out_of_password_login_when_exclusive_active(
    client: AsyncClient, db: AsyncSession
):
    """
    Belegt explizit das im Auftrag beschriebene Lockout-Risiko: ein Mitglied ohne Passkey
    kann sich bei aktivem Exklusiv-Schalter weder per Passwort einloggen (403, Baustein 2)
    noch — mangels Session — einen Passkey registrieren (register/options braucht
    get_current_user). Der Invite-Guard (siehe test_invite_rejected_while_exclusive_login_active)
    verhindert genau diesen Zustand normalerweise — hier wird er bewusst per Direkt-Insert
    umgangen, um den zugrunde liegenden Lockout isoliert zu beweisen.
    """
    admin = await _register_admin(client)
    await _mark_totp_enrolled(db, admin["id"])
    await _add_credential(db, admin["id"])
    activate = await client.put(_POLICY_PATH, json=_policy_payload(exclusive=True))
    assert activate.status_code == 200

    locked_out_member = User(
        username="member1",
        email="member1@example.com",
        password_hash=hash_password(_PASSWORD),
        role=UserRole.USER,
        household_id=uuid.UUID(admin["household_id"]),
    )
    db.add(locked_out_member)
    await db.commit()

    async with await _fresh_client() as member_client:
        login_response = await member_client.post(
            "/api/auth/login", json={"username": "member1", "password": _PASSWORD}
        )
        assert login_response.status_code == 403

    async with await _fresh_client() as member_client:
        register_options_response = await member_client.post("/api/webauthn/register/options")
        assert register_options_response.status_code == 401


# --- Race Conditions (Security-Review Phase 4, M1/M2) — erzwungene Nebenläufigkeit ---------


async def test_concurrent_delete_of_last_two_credentials_serializes_via_household_lock(
    client: AsyncClient, db: AsyncSession, monkeypatch
):
    """
    M1: zwei parallele DELETE-Requests auf die letzten ZWEI Passkeys eines Users bei
    aktivem passkey_exclusive_login. Vor dem lock_household_security-Fix (kein Row-/
    Advisory-Lock) hätten beide Requests unter READ COMMITTED denselben Vorher-Stand
    "2 Passkeys" gesehen, bevor der jeweils andere committet — Ergebnis: 0 Passkeys
    übrig, trotz aktivem Schalter.

    Gepaust wird gezielt in record_event() (aufgerufen NACH der Zählung, aber direkt VOR
    dem committenden Aufruf) statt in lock_household_security() selbst — ein Pause-Punkt
    VOR jeder Zählung hätte die zwei Requests durch das Test-Timing selbst künstlich
    sequenzialisiert und so den echten Advisory-Lock gar nicht geprüft (per Mutationstest
    verifiziert: mit deaktiviertem Lock hätte diese frühere Variante trotzdem noch
    "zufällig" bestanden). Mit dem Pause-Punkt NACH der eigenen Zählung/Entscheidung
    beweist der Test tatsächlich den Lock: der zuerst ankommende Request pausiert hier
    knapp vor seinem eigenen Commit; ohne echten Advisory-Lock könnte der zweite Request
    in dieser Zeit unbehindert dieselbe (noch nicht committete) "2 Passkeys"-Zählung lesen
    und ebenfalls durchlaufen — mit Lock blockiert er stattdessen schon vorher real in
    Postgres bei seinem eigenen lock_household_security-Aufruf und sieht nach dessen
    Freigabe den bereits reduzierten, korrekten Bestand.
    """
    admin = await _register_admin(client)
    await _mark_totp_enrolled(db, admin["id"])
    credential_a = await _add_credential(db, admin["id"], device_label="Erst")
    credential_b = await _add_credential(db, admin["id"], device_label="Zweit")
    activate = await client.put(_POLICY_PATH, json=_policy_payload(exclusive=True))
    assert activate.status_code == 200

    import app.api.webauthn as webauthn_module

    wrapper, started, hold = _pause_first_call(
        webauthn_module.record_event, pause_before_effect=True
    )
    monkeypatch.setattr(webauthn_module, "record_event", wrapper)

    task_a = asyncio.create_task(client.delete(f"/api/webauthn/credentials/{credential_a.id}"))
    task_b = asyncio.create_task(client.delete(f"/api/webauthn/credentials/{credential_b.id}"))

    await asyncio.wait_for(started.wait(), timeout=5)
    # Verschnaufpause: gibt dem zweiten Request Zeit, seine eigene Zählung (ohne Lock:
    # unbehindert: mit Lock: blockiert bei lock_household_security) tatsächlich zu erreichen.
    await asyncio.sleep(0.2)
    hold.set()

    response_a, response_b = await asyncio.gather(task_a, task_b)

    assert sorted([response_a.status_code, response_b.status_code]) == [204, 409]

    remaining = await client.get("/api/webauthn/credentials")
    assert len(remaining.json()) == 1

    blocked_audit = await db.execute(
        select(AuditLog).where(AuditLog.event_type == "passkey_delete_blocked")
    )
    assert blocked_audit.scalar_one_or_none() is not None


async def test_concurrent_activation_and_invite_serializes_via_household_lock(
    client: AsyncClient, db: AsyncSession, monkeypatch
):
    """
    M2: der Aktivierungs-PUT (passkey_exclusive_login: false -> true) hat das
    Precondition-Gate erfolgreich geprüft, aber noch nicht committet, als parallel ein
    Invite feuert. Vor dem lock_household_security-Fix hätte der Invite-Guard
    (app/api/auth.py) den Schalter in genau diesem Moment noch als False gelesen und ein
    neues, passkeyloses Mitglied angelegt — der Lockout, den Gate + Invite-Guard
    gemeinsam verhindern sollen.

    Wie bei M1 wird der PUT gezielt angehalten, NACHDEM er den echten Advisory-Lock
    bereits hält (also nach dem erfolgreichen Gate-Check, vor dem Commit). Der parallel
    gestartete Invite muss in dieser Zeit real in Postgres auf denselben Lock warten und
    darf erst mit dem dann bereits committeten (aktiven) Schalterstand weiterlaufen.
    """
    admin = await _register_admin(client)
    await _mark_totp_enrolled(db, admin["id"])
    await _add_credential(db, admin["id"])

    import app.api.security_settings as security_settings_module

    wrapper, started, hold = _pause_first_call(security_settings_module.lock_household_security)
    monkeypatch.setattr(security_settings_module, "lock_household_security", wrapper)

    task_put = asyncio.create_task(client.put(_POLICY_PATH, json=_policy_payload(exclusive=True)))
    await asyncio.wait_for(started.wait(), timeout=5)

    task_invite = asyncio.create_task(
        client.post(
            "/api/auth/invite",
            json={"username": "member1", "email": "member1@example.com", "password": _PASSWORD},
        )
    )
    # Verschnaufpause: gibt dem Invite-Request Zeit, seinen eigenen
    # pg_advisory_xact_lock-Aufruf tatsächlich zu erreichen und dort real zu blockieren.
    await asyncio.sleep(0.2)
    hold.set()

    put_response, invite_response = await asyncio.gather(task_put, task_invite)

    assert put_response.status_code == 200
    assert put_response.json()["passkey_exclusive_login"] is True
    assert invite_response.status_code == 409

    result = await db.execute(select(User).where(User.username == "member1"))
    assert result.scalar_one_or_none() is None
