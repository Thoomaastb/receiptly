"""
Prüft periodisch (Aufruf durch scheduler.py, siehe Schritt 2) gegen die öffentliche
GitHub-Releases-API, ob ein neues Release verfügbar ist, und cached das Ergebnis in
Redis für den Sidebar-Footer-Hinweis (Frontend, siehe Schritt 4).
"""

import logging

import httpx
import redis.asyncio as redis
from sqlalchemy import select

from app.config import get_settings
from app.database import AsyncSessionLocal
from app.models.update_check_settings import UpdateCheckSettings

logger = logging.getLogger(__name__)
settings = get_settings()
_redis = redis.from_url(settings.redis_url, decode_responses=True)

_GITHUB_RELEASES_URL = "https://api.github.com/repos/Thoomaastb/receiptly/releases/latest"
_CACHE_KEY = "update:latest_release"
# TTL als Selbstheilungs-Netz, proportional zum 15-Minuten-Takt (siehe scheduler.py):
# läuft der Job dauerhaft aus (Crash, Downtime), verschwindet der Hinweis nach 2h
# von selbst (~8 verpasste Zyklen Toleranz) statt einen veralteten Stand unbegrenzt
# weiter zu zeigen.
_CACHE_TTL_SECONDS = 2 * 60 * 60


async def _is_enabled() -> bool:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(UpdateCheckSettings).where(UpdateCheckSettings.id == 1))
        row = result.scalar_one_or_none()
        return row.enabled if row is not None else True  # Default an, falls noch nie initialisiert


async def check_for_update() -> None:
    """
    Fragt die öffentliche, anonyme GitHub-Releases-API ab (kein Auth-Token nötig,
    Rate-Limit 60/h anonym — bei 15-Minuten-Takt (4 Calls/h) weit unkritisch) und
    cached das Ergebnis in Redis. Einziger automatischer externer Netzwerk-Call im
    Projekt — bewusst akzeptierte Ausnahme vom sonstigen "kein Call ohne
    Nutzeraktion"-Stil, da rein informativ und ohne jeden Datenabfluss (nur
    ausgehend, keine receiptly-Daten im Request). Respektiert den Admin-Schalter
    aus UpdateCheckSettings — deaktiviert = kein Call, kein Cache-Update.
    """
    if not await _is_enabled():
        return
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(
                _GITHUB_RELEASES_URL, headers={"Accept": "application/vnd.github+json"}
            )
            response.raise_for_status()
            data = response.json()
        tag = data.get("tag_name")
        url = data.get("html_url")
        if isinstance(tag, str) and tag:
            await _redis.set(_CACHE_KEY, f"{tag}|{url or ''}", ex=_CACHE_TTL_SECONDS)
    except (httpx.HTTPError, ValueError) as exc:
        # Nie den Scheduler-Job sterben lassen — GitHub down/Rate-Limit ist kein
        # App-Fehler, alter Cache-Wert bleibt bis TTL-Ablauf gültig.
        logger.info("Update-Check fehlgeschlagen (nicht kritisch): %s", exc)


async def get_cached_update_info() -> tuple[str, str] | None:
    """Liefert (tag, release_url) aus dem Cache, oder None wenn noch nie erfolgreich geprüft."""
    raw = await _redis.get(_CACHE_KEY)
    if not raw:
        return None
    tag, _, url = raw.partition("|")
    return (tag, url) if tag else None


async def is_update_check_enabled() -> bool:
    """Für den health-Endpoint (Schritt 3) — separat exportiert, damit dort nicht
    nochmal die DB-Session-Logik dupliziert werden muss."""
    return await _is_enabled()
