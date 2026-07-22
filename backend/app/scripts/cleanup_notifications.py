"""
Löscht gelesene `notifications`-Zeilen älter als 90 Tage (Q9, fester Wert für v1 — die im
Konzept offen gelassene Admin-Konfigurierbarkeit ist ein günstiger, aber bewusst nicht in
v1 enthaltener Nachtrag).

Anders als `cleanup_audit_log.py` braucht es hier KEIN `SET LOCAL audit.allow_delete`
— `notifications` ist nicht per DB-Trigger immutable (siehe Migration 0018-Docstring,
`read_at` wird bewusst mutiert), ein einfaches `DELETE` reicht.

Reines Python-Skript, per APScheduler-Job in `app/scheduler.py` täglich um 03:30
angestoßen — manueller Aufruf (innerhalb des Backend-Containers):
`python -m app.scripts.cleanup_notifications`
"""

import asyncio
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete

from app.database import AsyncSessionLocal
from app.models.notification import Notification

logger = logging.getLogger(__name__)

_RETENTION_DAYS = 90


async def cleanup_notifications() -> int:
    """Löscht gelesene Notifications älter als 90 Tage, gibt die Anzahl gelöschter Zeilen zurück."""
    cutoff = datetime.now(UTC) - timedelta(days=_RETENTION_DAYS)

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            delete(Notification).where(
                Notification.read_at.is_not(None),
                Notification.read_at < cutoff,
            )
        )
        await db.commit()
        deleted = result.rowcount or 0

    logger.info("Notification-Bereinigung abgeschlossen: %s Zeile(n) gelöscht", deleted)
    return deleted


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(cleanup_notifications())
