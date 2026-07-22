"""Schreibt Einträge in die immutable `audit_log`-Tabelle (siehe app/models/audit_log.py)."""

import uuid

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.request_meta import get_client_ip, get_user_agent
from app.models.audit_log import AuditLog
from app.models.user import User
from app.services.household_security import get_or_create_security_settings
from app.services.notifications import create_notification

# Die drei event_types, die einen abgeschlossenen (erfolgreichen) Login-Vorgang markieren —
# als eine Familie behandelt für die "Neuer Login"-Erkennung (Q7). Verifiziert gegen
# app/api/auth.py (_finalize_first_factor/login_with_totp) und app/api/webauthn.py
# (_finalize_first_factor-Aufruf mit success_event_type="passkey_login_success").
_LOGIN_SUCCESS_EVENT_TYPES = {"login_success", "passkey_login_success", "totp_login_success"}

# Kuratierte Teilmenge sicherheitsrelevanter event_types → (category, type) fürs
# Benachrichtigungssystem (v0.25) — bewusst NICHT jedes Audit-Event (normale Logins/Logout/
# Einzel-Fehlversuche/rate_limit_triggered/recovery_codes_regenerated zählen laut Konzept
# nicht als eigene Notification). Gegen die aktuellen event_type-Literale in
# app/api/auth.py, app/api/totp.py, app/api/webauthn.py, app/api/security_settings.py
# verifiziert (nicht blind aus einer älteren Planversion übernommen).
_DIRECT_NOTIFY_ALLOWLIST: dict[str, tuple[str, str]] = {
    "password_changed": ("sicherheit", "security_password_changed"),
    "password_reset_confirmed": ("sicherheit", "security_password_changed"),
    "totp_enabled": ("sicherheit", "security_totp_enabled"),
    "totp_disabled": ("sicherheit", "security_totp_disabled"),
    "passkey_registered": ("sicherheit", "security_passkey_registered"),
    "passkey_removed": ("sicherheit", "security_passkey_removed"),
    "recovery_code_used": ("sicherheit", "security_recovery_code_used"),
    "session_terminated": ("sicherheit", "security_session_terminated"),
    "passkey_exclusive_login_toggled": (
        "sicherheit",
        "security_passkey_exclusive_login_toggled",
    ),
}

# Deutschsprachige Titel/Texte je Notification-`type` — zentral hier statt an jeder
# record_event()-Aufrufstelle dupliziert, da die Zuordnung 1:1 am event_type hängt.
_NOTIFICATION_COPY: dict[str, tuple[str, str]] = {
    "security_password_changed": (
        "Passwort geändert",
        "Das Passwort für dein Konto wurde geändert.",
    ),
    "security_totp_enabled": (
        "Zwei-Faktor-Login aktiviert",
        "Die Zwei-Faktor-Authentifizierung (TOTP) wurde für dein Konto aktiviert.",
    ),
    "security_totp_disabled": (
        "Zwei-Faktor-Login deaktiviert",
        "Die Zwei-Faktor-Authentifizierung (TOTP) wurde für dein Konto deaktiviert.",
    ),
    "security_passkey_registered": (
        "Neuer Passkey registriert",
        "Für dein Konto wurde ein neuer Passkey registriert.",
    ),
    "security_passkey_removed": (
        "Passkey entfernt",
        "Ein Passkey wurde von deinem Konto entfernt.",
    ),
    "security_recovery_code_used": (
        "Recovery-Code verwendet",
        "Für dein Konto wurde ein Recovery-Code zum Login verwendet.",
    ),
    "security_session_terminated": (
        "Sitzung beendet",
        "Eine Sitzung deines Kontos wurde beendet.",
    ),
    "security_passkey_exclusive_login_toggled": (
        "Passkey-exklusiver Login geändert",
        "Der haushaltsweite passkey-exklusive Login wurde umgestellt.",
    ),
    "security_new_login": (
        "Neuer Login erkannt",
        "Dein Konto wurde von einem bisher unbekannten Gerät oder Standort aus angemeldet.",
    ),
}


async def _detect_new_login(
    db: AsyncSession, user_id: uuid.UUID, request: Request | None
) -> bool:
    """
    Neu-Login-Erkennung (Q7): aktuelle IP *oder* aktueller User-Agent nicht in der Historie
    der letzten ~50 Login-Abschluss-Events dieses Users enthalten. Kein Alarm beim
    allerersten jemals erfassten Login dieses Users (keine Baseline zum Vergleich) — genau
    dieser Fall liegt vor, wenn die Historie-Query keine Zeilen liefert.
    """
    if request is None:
        return False

    history = await db.execute(
        select(AuditLog.ip, AuditLog.user_agent)
        .where(AuditLog.user_id == user_id, AuditLog.event_type.in_(_LOGIN_SUCCESS_EVENT_TYPES))
        .order_by(AuditLog.created_at.desc())
        .limit(50)
    )
    rows = history.all()
    if not rows:
        return False

    known_ips = {ip for ip, _user_agent in rows if ip is not None}
    known_user_agents = {user_agent for _ip, user_agent in rows if user_agent is not None}

    current_ip = get_client_ip(request)
    current_user_agent = get_user_agent(request)
    return current_ip not in known_ips or current_user_agent not in known_user_agents


async def _maybe_create_security_notifications(
    db: AsyncSession, entry: AuditLog, is_new_login: bool
) -> None:
    """
    Läuft NACH `db.add(entry)` UND nach einem expliziten Flush (siehe Aufrufstelle in
    `record_event()`) — `default=uuid.uuid4` auf `AuditLog.id` ist ein SQLAlchemy-seitiger
    Flush-Time-Default, `entry.id` ist also erst NACH einem Flush populiert, nicht schon
    direkt nach `db.add()` (Security-Review 2026-07-22 hat das als echten Bug gefunden: ohne
    den Flush wäre `entry.id` hier `None` gewesen, wodurch `dedup_key` für den ersten
    Security-Hinweis eines Users `"audit:None:<user_id>"` gelautet und jede folgende
    Security-Notification desselben Users über den Unique-Index still verworfen hätte).
    Jeder hier erzeugte `create_notification(..., commit=False)`-Aufruf teilt sich die
    Transaktion und den Commit von `record_event()` — ein Rollback des Audit-Eintrags lässt
    nie eine Notification ohne zugehöriges Audit-Event zurück.
    """
    if entry.user_id is None:
        return

    # (Empfänger-user_id, category, type) je zu erstellender Notification.
    targets: list[tuple[uuid.UUID, str, str]] = []

    allowlisted = _DIRECT_NOTIFY_ALLOWLIST.get(entry.event_type)
    if allowlisted is not None:
        category, type_ = allowlisted
        if entry.event_type == "passkey_exclusive_login_toggled":
            # Haushaltsweite Sicherheitsrichtlinien-Änderung (Q6) — jedes Mitglied
            # benachrichtigen, nicht nur den auslösenden Admin.
            members = await db.execute(
                select(User.id).where(User.household_id == entry.household_id)
            )
            targets.extend((member_id, category, type_) for (member_id,) in members.all())
        else:
            targets.append((entry.user_id, category, type_))

    if is_new_login:
        targets.append((entry.user_id, "sicherheit", "security_new_login"))

    for recipient_user_id, category, type_ in targets:
        title, body = _NOTIFICATION_COPY[type_]
        await create_notification(
            db,
            user_id=recipient_user_id,
            household_id=entry.household_id,
            category=category,
            type=type_,
            title=title,
            body=body,
            dedup_key=f"audit:{entry.id}:{recipient_user_id}",
            commit=False,
        )


async def record_event(
    db: AsyncSession,
    *,
    household_id: uuid.UUID,
    event_type: str,
    user_id: uuid.UUID | None = None,
    request: Request | None = None,
    attempted_username: str | None = None,
    metadata: dict | None = None,
    commit: bool = True,
) -> None:
    """
    `request=None` für Aufrufe ohne HTTP-Request-Kontext (z.B. ein künftiger Batch-/Cron-Job)
    — `ip`/`user_agent` bleiben dann NULL.

    `commit=True` ist bewusst der Default: der Login-Fehlschlag-Pfad in app/api/auth.py
    wirft die HTTPException direkt, ohne vorher db.commit() aufzurufen. Würde record_event()
    dort ohne eigenen Commit aufgerufen, ginge der Audit-Eintrag für genau den
    sicherheitsrelevantesten Fall (fehlgeschlagener Login) beim Request-Ende per Rollback
    stillschweigend verloren. `commit=False` ist nur für Aufrufer gedacht, die den Eintrag
    bewusst in eine bereits laufende Transaktion einbetten und selbst committen wollen.

    `attempted_username` wird vor dem Speichern gegen die haushaltsweite
    `household_security_settings.log_attempted_username`-Einstellung geprüft (Default true
    für Haushalte ohne eigene Zeile, lazy erstellt bei erstem Zugriff) — steht sie auf
    false, wird das Feld hier stillschweigend auf None gesetzt. Der Lookup läuft nur, wenn
    tatsächlich ein `attempted_username` übergeben wurde, um die deutlich häufigeren
    Events ohne dieses Feld nicht mit einem zusätzlichen Query zu belasten.

    Benachrichtigungssystem-Hook (v0.25, Konzept §4.3 "eine Naht, kein zweiter
    Erkennungspfad"): VOR dem Insert wird bei einem der drei Login-Abschluss-Events
    (`_LOGIN_SUCCESS_EVENT_TYPES`) geprüft, ob IP/User-Agent gegenüber der jüngeren
    Login-Historie dieses Users neu sind ("Neuer Login", Q7). NACH `db.add(entry)` UND einem
    expliziten `db.flush()` (erzwingt `entry.id`, sonst `None` — siehe
    `_maybe_create_security_notifications`-Docstring) legt `_maybe_create_security_
    notifications()` für eine kuratierte Teilmenge sicherheitsrelevanter Events (siehe
    `_DIRECT_NOTIFY_ALLOWLIST`) sowie für einen erkannten Neu-Login jeweils eine
    `Notification` an — mit `commit=False`, damit sie sich diese Funktionseigene
    Commit-/Flush-Logik unten teilen, statt eine zweite, unabhängige Transaktion zu öffnen.
    """
    if attempted_username is not None:
        security_settings = await get_or_create_security_settings(db, household_id)
        if not security_settings.log_attempted_username:
            attempted_username = None

    is_new_login = False
    if event_type in _LOGIN_SUCCESS_EVENT_TYPES and user_id is not None:
        is_new_login = await _detect_new_login(db, user_id, request)

    entry = AuditLog(
        household_id=household_id,
        event_type=event_type,
        user_id=user_id,
        attempted_username=attempted_username,
        event_metadata=metadata,
        ip=get_client_ip(request) if request is not None else None,
        user_agent=get_user_agent(request) if request is not None else None,
    )
    db.add(entry)
    # Flush erzwingt die Vergabe von entry.id (Flush-Time-Default, siehe
    # _maybe_create_security_notifications-Docstring) — ohne diesen Flush wäre entry.id
    # beim Bilden von dedup_key unten noch None.
    await db.flush()

    await _maybe_create_security_notifications(db, entry, is_new_login)

    if commit:
        await db.commit()
    else:
        await db.flush()
