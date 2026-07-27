"""
FastAPI-`lifespan`-Context-Manager für die täglichen Benachrichtigungs-/Wartungs-Jobs
(Garantie-Ablauf-Scan, Notification-Retention, Konto-Löschung-Teardown) sowie den
höherfrequenten Update-Check-Job — bewusst aus `main.py` ausgelagert, damit dessen
bisherige flache Router-Registrierungs-Struktur unangetastet bleibt.

Kein Redis-Lock (bestätigtes Single-Process-Deployment, siehe `docker-compose.yml`: kein
`--workers`, kein Replica-Scaling) — `misfire_grace_time`/`coalesce` von APScheduler selbst
reichen: ein verpasster Lauf (Container-Neustart während des Cron-Fensters) wird innerhalb
der Gnadenfrist nachgeholt, mehrere verpasste Läufe werden zu einem zusammengefasst statt
nachträglich mehrfach zu feuern.
"""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from fastapi import FastAPI

from app.config import get_settings
from app.scripts.account_deletion_teardown import run_scheduled_deletions
from app.scripts.cleanup_notifications import cleanup_notifications
from app.scripts.warranty_notifications import scan_warranty_expirations
from app.services.update_check import check_for_update

settings = get_settings()


def _update_check_interval_minutes() -> int:
    # Vor v1.0.0 engmaschiger (Projekt in aktiver Entwicklung, Releases mehrmals
    # täglich), danach stündlich genügt — Major-Version 0 als Schwellenwert, kein
    # manueller Umstellungs-Handgriff bei v1.0.0 nötig.
    major = int(settings.app_version.split(".")[0]) if settings.app_version[:1].isdigit() else 0
    return 15 if major < 1 else 60


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
    # IntervalTrigger statt CronTrigger (anders als die drei Jobs oben) — Nutzer wollte
    # explizit eine höhere, versionsabhängige Frequenz statt eines festen Tageszeitpunkts.
    scheduler.add_job(
        check_for_update,
        IntervalTrigger(minutes=_update_check_interval_minutes()),
        id="update_check",
        misfire_grace_time=300,  # kleiner als bei den Tages-Jobs (3600s), passend zum kurzen Intervall
        coalesce=True,
    )
    scheduler.start()
    # Einmaliger Sofort-Lauf beim Start, zusätzlich zum Intervall-Job oben: IntervalTrigger
    # feuert sonst erst nach dem vollen ersten Intervall (bis zu 15 Min nach Deploy), bevor
    # der Sidebar-Footer-Hinweis initial befüllt wird. Fire-and-forget, da check_for_update()
    # bereits intern jede Exception abfängt (siehe app/services/update_check.py) und nie den
    # Task oder die App zum Absturz bringt.
    asyncio.create_task(check_for_update())
    yield
    scheduler.shutdown(wait=False)
