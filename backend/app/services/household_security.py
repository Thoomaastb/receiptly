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

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.household_security_settings import HouseholdSecuritySettings


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
