import json
import secrets
import uuid

import redis.asyncio as redis
from fastapi import Response
from itsdangerous import BadSignature, URLSafeTimedSerializer

from app.config import get_settings

settings = get_settings()
_redis = redis.from_url(settings.redis_url, decode_responses=True)
_serializer = URLSafeTimedSerializer(settings.session_secret, salt="receiptly-session")

_SESSION_KEY_PREFIX = "session:"


async def create_session(user_id: uuid.UUID, response: Response) -> str:
    """Legt eine serverseitige Session in Redis an und setzt ein signiertes, HTTP-Only Cookie."""
    raw_token = secrets.token_urlsafe(32)
    signed_token = _serializer.dumps(raw_token)

    await _redis.setex(
        f"{_SESSION_KEY_PREFIX}{raw_token}",
        settings.session_max_age_seconds,
        json.dumps({"user_id": str(user_id)}),
    )

    response.set_cookie(
        key=settings.session_cookie_name,
        value=signed_token,
        max_age=settings.session_max_age_seconds,
        httponly=True,
        secure=settings.app_env != "development",
        samesite="lax",
    )
    return raw_token


async def get_session_user_id(signed_token: str | None) -> uuid.UUID | None:
    if not signed_token:
        return None
    try:
        raw_token = _serializer.loads(signed_token, max_age=settings.session_max_age_seconds)
    except BadSignature:
        return None

    data = await _redis.get(f"{_SESSION_KEY_PREFIX}{raw_token}")
    if not data:
        return None
    return uuid.UUID(json.loads(data)["user_id"])


async def destroy_session(signed_token: str | None, response: Response) -> None:
    if signed_token:
        try:
            raw_token = _serializer.loads(signed_token)
            await _redis.delete(f"{_SESSION_KEY_PREFIX}{raw_token}")
        except BadSignature:
            pass
    response.delete_cookie(settings.session_cookie_name)
