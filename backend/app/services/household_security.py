"""
Lädt/erstellt die haushaltsweite Sicherheitsrichtlinie (household_security_settings).
Lazy-Create-Pattern wie bei AISettings (app/api/settings.py `_get_or_create`) — Haushalte
ohne eigene Zeile bekommen beim ersten Zugriff eine mit den Spalten-Defaults (TOTP-Pflicht
aus, 90 Tage Retention, Fehlversuch-Username-Logging an).

Zentral hier statt an jeder Aufrufstelle dupliziert, weil drei unabhängige Stellen
denselben Datensatz brauchen: app/api/auth.py (TOTP-Pflicht-Check beim Login),
app/api/security_settings.py (Admin-Verwaltung) und app/services/audit.py
(log_attempted_username). `_get_or_create` flusht nur, committet aber nicht — die
jeweiligen Aufrufer entscheiden selbst, wann committet wird (siehe deren eigene Docstrings).
"""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.household_security_settings import HouseholdSecuritySettings
from app.models.user import User
from app.models.webauthn_credential import WebauthnCredential


async def get_or_create_security_settings(
    db: AsyncSession, household_id: uuid.UUID
) -> HouseholdSecuritySettings:
    result = await db.execute(
        select(HouseholdSecuritySettings).where(
            HouseholdSecuritySettings.household_id == household_id
        )
    )
    settings = result.scalar_one_or_none()
    if settings is None:
        settings = HouseholdSecuritySettings(household_id=household_id)
        db.add(settings)
        await db.flush()
    return settings


async def lock_household_security(db: AsyncSession, household_id: uuid.UUID) -> None:
    """
    Serialisiert die drei zusammengehörigen Security-Hardening-Operationen auf einen
    Haushalt (Aktivierungs-PUT für passkey_exclusive_login, Invite-Guard, Löschprüfung
    des letzten Passkeys) gegeneinander — siehe Security-Review Phase 4 (M1/M2). Ohne
    diesen Lock liest ein zweiter, parallel laufender Request unter READ COMMITTED
    denselben Vorher-Zustand, bevor der erste committet hat (TOCTOU): zwei parallele
    Löschungen der letzten zwei Passkeys sehen beide noch "2 Stück" und lassen beide
    durch; ein Invite kurz vor dem Aktivierungs-Commit sieht den Schalter noch als aus.

    Postgres-Advisory-Transaction-Lock statt `SELECT ... FOR UPDATE` auf
    `household_security_settings`, weil diese Zeile für einen Haushalt noch gar nicht
    existieren muss (Lazy-Create in get_or_create_security_settings) — FOR UPDATE auf
    eine nicht existierende Zeile sperrt nichts. Der Advisory-Lock hängt nur am gehashten
    household_id-Wert und greift deshalb unabhängig davon, ob die Zeile schon existiert.

    Muss als Erstes in jeder der drei Operationen erworben werden (vor jeder Zählung/
    Prüfung des jeweiligen Aufrufers) — sonst serialisiert er nur kosmetisch am Ende.
    Die xact-Variante gibt den Lock automatisch beim Commit/Rollback der Transaktion
    frei, kein manuelles Unlock nötig.
    """
    await db.execute(select(func.pg_advisory_xact_lock(func.hashtext(str(household_id)))))


async def get_passkey_exclusive_gate_status(
    db: AsyncSession, household_id: uuid.UUID
) -> tuple[list[User], int]:
    """
    Precondition-Gate für den Passkey-Exklusiv-Schalter (Security-Hardening Phase 4, siehe
    concepts/security-hardening.md Abschnitt 4.1): liefert alle Haushaltsmitglieder OHNE
    mindestens einen WebauthnCredential-Eintrag sowie die Gesamtzahl der Mitglieder.
    Ausdrücklich ohne Rollenfilter — der Schalter blockiert den Passwort-Login für ALLE
    Haushaltsmitglieder inkl. Admin (der dann per Passkey + TOTP einloggt), also braucht
    auch der Admin selbst einen Passkey, damit die Aktivierung nicht ihn selbst aussperrt.

    Zentral hier statt dupliziert, weil zwei Stellen dieselbe Prüfung brauchen:
    app/api/security_settings.py (Live-Status-Endpoint fürs Frontend-Gate-Feedback UND
    die serverseitige Durchsetzung beim PUT) — beide müssen exakt dieselbe Definition von
    "hat einen Passkey" verwenden, sonst könnte der Live-Status grünes Licht geben, das
    PUT aber trotzdem ablehnen (oder umgekehrt).

    Schließt Platzhalter-User (Konto-Löschung/DSGVO, Migration 0022) aus beiden Zählungen
    aus — ein Tombstone hat nie einen Passkey und würde `eligible` sonst dauerhaft
    verhindern, sobald ein Haushalt einmal eine Konto-Löschung durchlaufen hat.
    """
    total_result = await db.execute(
        select(func.count())
        .select_from(User)
        .where(User.household_id == household_id, User.is_placeholder.is_(False))
    )
    total_members = total_result.scalar_one()

    has_credential = (
        select(WebauthnCredential.id)
        .where(WebauthnCredential.user_id == User.id)
        .correlate(User)
        .exists()
    )
    missing_result = await db.execute(
        select(User).where(
            User.household_id == household_id,
            User.is_placeholder.is_(False),
            ~has_credential,
        )
    )
    missing_members = list(missing_result.scalars().all())

    return missing_members, total_members
