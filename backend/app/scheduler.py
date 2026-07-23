"""
FastAPI-`lifespan`-Context-Manager für die beiden täglichen Benachrichtigungs-Jobs
(Garantie-Ablauf-Scan, Notification-Retention) — bewusst aus `main.py` ausgelagert, damit
dessen bisherige flache Router-Registrierungs-Struktur unangetastet bleibt.

Kein Redis-Lock (bestätigtes Single-Process-Deployment, siehe `docker-compose.yml`: kein
`--workers`, kein Replica-Scaling) — `misfire_grace_time`/`coalesce` von APScheduler selbst
reichen: ein verpasster Lauf (Container-Neustart während des Cron-Fensters) wird innerhalb
der Gnadenfrist nachgeholt, mehrere verpasste Läufe werden zu einem zusammengefasst statt
nachträglich mehrfach zu feuern.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI

from app.scripts.account_deletion_teardown import run_scheduled_deletions
from app.scripts.cleanup_notifications import cleanup_notifications
from app.scripts.warranty_notifications import scan_warranty_expirations


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        scan_warranty_expirations,
        CronTrigger(hour=3, minute=0),
        id="warranty_scan",
        misfire_grace_time=3600,
        coalesce=True,
    )
    scheduler.add_job(
        cleanup_notifications,
        CronTrigger(hour=3, minute=30),
        id="notification_cleanup",
        misfire_grace_time=3600,
        coalesce=True,
    )
    # Stufe B der Konto-Löschung (DSGVO, siehe app/scripts/account_deletion_teardown.py) —
    # irreversibler Teardown fälliger 14-Tage-Karenzzeit-Konten. Bewusst nach den beiden
    # bestehenden 03:00/03:30-Jobs, eigenes Zeitfenster.
    scheduler.add_job(
        run_scheduled_deletions,
        CronTrigger(hour=4, minute=0),
        id="account_deletion_teardown",
        misfire_grace_time=3600,
        coalesce=True,
    )
    scheduler.start()
    yield
    scheduler.shutdown(wait=False)
