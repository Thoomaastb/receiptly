import re

from fastapi import APIRouter

from app.config import get_settings
from app.services.update_check import (
    get_cached_overall_info,
    get_cached_update_info,
    is_update_check_enabled,
)

router = APIRouter(tags=["health"])
settings = get_settings()


def _parse(v: str) -> tuple[int, ...]:
    """Einfacher Semver-Tupel-Vergleich, kein Dependency nötig. Tags wie 'v0.45.0',
    settings.app_version wie '0.45.0' — führendes 'v' strippen. Pro Versions-Teil werden nur
    die führenden Ziffern ausgewertet (z.B. '6-rc' -> 6), damit ein Pre-Release-Suffix nicht
    den GESAMTEN Vergleich auf (0,0,0) zurückfallen lässt (siehe Bugs-Seite, "Update-Check-
    Banner" 2026-07-30) — ein einzelner nicht-numerischer Teil wird nur selbst zu 0, statt
    das ganze Tupel zu verwerfen. Fehlende Teile werden mit 0 aufgefüllt (z.B. '0.45' ->
    (0,45,0)), damit unterschiedlich lange Versionsstrings nicht durch Python-Tupel-Vergleich
    unerwartet ausfallen."""
    v = v.lstrip("v")
    parts = v.split(".")[:3]
    nums = []
    for part in parts:
        match = re.match(r"\d+", part)
        nums.append(int(match.group()) if match else 0)
    while len(nums) < 3:
        nums.append(0)
    return tuple(nums)


def _is_newer(latest_tag: str, current_version: str) -> bool:
    return _parse(latest_tag) > _parse(current_version)


def _same_version(a: str, b: str) -> bool:
    """Exakter Vergleich (nach 'v'-Präfix-Normalisierung), NICHT nur Basis-Tupel-Gleichheit —
    zwei unterschiedliche Pre-Releases derselben Basisversion (z.B. '0.49.6-rc.1' vs.
    '0.49.6-rc.2') gelten hier bewusst als verschieden, da Fall 1 (kein Hinweis) nur bei
    tatsächlich identischer Version greifen soll."""
    return a.lstrip("v") == b.lstrip("v")


def _is_stable(version: str) -> bool:
    """Stable = keine Pre-Release-/Build-Suffixe (kein '-' oder '+' im Versionsstring)."""
    return "-" not in version and "+" not in version


@router.get("/health")
async def health() -> dict:
    payload: dict = {"status": "ok", "version": settings.app_version}
    # Schalter hier nochmal separat prüfen (zusätzlich zur Prüfung in
    # check_for_update()), damit ein gerade deaktivierter Schalter sofort wirkt,
    # statt bis zum Ablauf des bis zu 2h alten Redis-Caches sichtbar zu bleiben.
    if await is_update_check_enabled():
        stable = await get_cached_update_info()
        overall = await get_cached_overall_info()
        current = settings.app_version

        level = "none"
        target_version = None
        release_url = None

        if overall:
            overall_tag, overall_url, _overall_prerelease = overall
            if _same_version(overall_tag, current):
                level = "none"
            elif _is_stable(current) and stable and _is_newer(stable[0], current):
                level = "prominent"
                target_version, release_url = stable
            elif _is_newer(overall_tag, current):
                level = "muted"
                target_version, release_url = overall_tag, overall_url
        elif _is_stable(current) and stable and _is_newer(stable[0], current):
            # Fallback, falls der Listen-Endpoint (noch) nicht gecacht ist (z.B. direkt nach
            # Deployment, bevor der erste Scheduler-Lauf beide Calls erfolgreich abgeschlossen
            # hat) — mit dem bisherigen, einzelnen Stable-Wert weiterarbeiten.
            level = "prominent"
            target_version, release_url = stable

        if level != "none":
            payload["update_info"] = {
                "level": level,
                "target_version": target_version,
                "release_url": release_url,
            }

    return payload
