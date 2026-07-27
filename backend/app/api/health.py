from fastapi import APIRouter

from app.config import get_settings
from app.services.update_check import get_cached_update_info, is_update_check_enabled

router = APIRouter(tags=["health"])
settings = get_settings()


def _is_newer(latest_tag: str, current_version: str) -> bool:
    """Einfacher Semver-Tupel-Vergleich, kein Dependency nötig. Tags wie 'v0.45.0',
    settings.app_version wie '0.45.0' — führendes 'v' strippen. Unparsbare Strings
    fallen robust auf (0, 0, 0) statt zu crashen."""

    def _parse(v: str) -> tuple[int, ...]:
        v = v.lstrip("v")
        parts = v.split(".")[:3]
        try:
            return tuple(int(p) for p in parts)
        except ValueError:
            return (0, 0, 0)

    return _parse(latest_tag) > _parse(current_version)


@router.get("/health")
async def health() -> dict:
    payload: dict = {"status": "ok", "version": settings.app_version}
    # Schalter hier nochmal separat prüfen (zusätzlich zur Prüfung in
    # check_for_update()), damit ein gerade deaktivierter Schalter sofort wirkt,
    # statt bis zum Ablauf des bis zu 2h alten Redis-Caches sichtbar zu bleiben.
    if await is_update_check_enabled():
        cached = await get_cached_update_info()
        if cached:
            latest_tag, release_url = cached
            payload["latest_version"] = latest_tag
            payload["release_url"] = release_url
            payload["update_available"] = _is_newer(latest_tag, settings.app_version)
    return payload
