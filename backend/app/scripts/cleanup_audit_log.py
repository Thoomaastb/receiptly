"""
Löscht `audit_log`-Zeilen älter als die pro-Haushalt konfigurierte Retention
(`household_security_settings.audit_retention_days`, Default 90 Tage für Haushalte ohne
eigene Zeile — siehe app/services/household_security.py).

`audit_log` ist per DB-Trigger gegen DELETE gesperrt (Migration 0012,
`audit_log_immutable_trigger`) — dieses Skript setzt `SET LOCAL audit.allow_delete =
'true'` innerhalb derselben Transaktion, sonst schlägt der DELETE am eigenen Trigger fehl.
`SET LOCAL` gilt nur bis zum Ende der Transaktion, deshalb müssen Lesen (Retention-Werte)
und Schreiben (DELETE) hier in EINER `db.begin()`-Transaktion laufen.

Reines Python-Skript, bewusst OHNE eingebauten Scheduler/Cron — die Terminierung (Cron im
Host vs. In-Process-Scheduler im Container) ist eine separate Docker/Infra-Frage, siehe
Security-Hardening-Plan ("devops-Agent nur nach expliziter Rückfrage beim Nutzer").

Aufruf (innerhalb des Backend-Containers): `python -m app.scripts.cleanup_audit_log`
"""

import asyncio
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select, text

from app.database import AsyncSessionLocal
from app.models.audit_log import AuditLog
from app.models.household import Household
from app.models.household_security_settings import HouseholdSecuritySettings

logger = logging.getLogger(__name__)

_DEFAULT_RETENTION_DAYS = 90


async def cleanup_audit_log() -> int:
    """Löscht abgelaufene audit_log-Zeilen je Haushalt, gibt die Gesamtzahl gelöschter Zeilen zurück."""
    deleted_total = 0

    async with AsyncSessionLocal() as db, db.begin():
        household_ids = (await db.execute(select(Household.id))).scalars().all()
        configured_retention = dict(
            (
                await db.execute(
                    select(
                        HouseholdSecuritySettings.household_id,
                        HouseholdSecuritySettings.audit_retention_days,
                    )
                )
            ).all()
        )

        # SET LOCAL gilt nur innerhalb dieser Transaktion — muss vor dem ersten DELETE
        # gesetzt werden, sonst greift der Immutability-Trigger (siehe Modul-Docstring).
        await db.execute(text("SET LOCAL audit.allow_delete = 'true'"))

        for household_id in household_ids:
            retention_days = configured_retention.get(household_id, _DEFAULT_RETENTION_DAYS)
            cutoff = datetime.now(UTC) - timedelta(days=retention_days)
            result = await db.execute(
                delete(AuditLog).where(
                    AuditLog.household_id == household_id,
                    AuditLog.created_at < cutoff,
                )
            )
            deleted_total += result.rowcount or 0

    logger.info("Audit-Log-Bereinigung abgeschlossen: %s Zeile(n) gelöscht", deleted_total)
    return deleted_total


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(cleanup_audit_log())
