import secrets
import uuid

import redis.asyncio as redis

from app.config import get_settings

settings = get_settings()
_redis = redis.from_url(settings.redis_url, decode_responses=True)

_RESET_KEY_PREFIX = "pwreset:"
_RESET_USER_INDEX_PREFIX = "pwreset:user:"
_RESET_TTL_SECONDS = 1800  # 30 Minuten


async def create_reset_token(user_id: uuid.UUID) -> str:
    """
    Legt einen Einmal-Token für den Passwort-Reset in Redis an. Ein für denselben User
    ggf. noch gültiger, vorheriger Token wird dabei invalidiert (Nachschlag über den
    pwreset:user:-Index) — verhindert mehrere gleichzeitig gültige Reset-Links.
    """
    old_token = await _redis.get(f"{_RESET_USER_INDEX_PREFIX}{user_id}")
    if old_token:
        await _redis.delete(f"{_RESET_KEY_PREFIX}{old_token}")

    token = secrets.token_urlsafe(32)
    await _redis.setex(f"{_RESET_KEY_PREFIX}{token}", _RESET_TTL_SECONDS, str(user_id))
    await _redis.setex(f"{_RESET_USER_INDEX_PREFIX}{user_id}", _RESET_TTL_SECONDS, token)
    return token


async def consume_reset_token(token: str) -> uuid.UUID | None:
    """Löst einen Reset-Token einmalig ein und löscht ihn danach (inkl. User-Index)."""
    user_id_raw = await _redis.get(f"{_RESET_KEY_PREFIX}{token}")
    if not user_id_raw:
        return None

    await _redis.delete(f"{_RESET_KEY_PREFIX}{token}")
    await _redis.delete(f"{_RESET_USER_INDEX_PREFIX}{user_id_raw}")
    return uuid.UUID(user_id_raw)
