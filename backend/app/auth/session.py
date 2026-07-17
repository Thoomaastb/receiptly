import json
import secrets
import uuid
from datetime import UTC, datetime

import redis.asyncio as redis
from fastapi import Request, Response
from itsdangerous import BadSignature, URLSafeTimedSerializer

from app.auth.request_meta import get_client_ip, get_user_agent
from app.config import get_settings

settings = get_settings()
_redis = redis.from_url(settings.redis_url, decode_responses=True)
_serializer = URLSafeTimedSerializer(settings.session_secret, salt="receiptly-session")

_SESSION_KEY_PREFIX = "session:"
_USER_INDEX_PREFIX = "sessions:by-user:"
_TOUCH_MIN_INTERVAL_SECONDS = 60


def _session_key(raw_token: str) -> str:
    return f"{_SESSION_KEY_PREFIX}{raw_token}"


def _user_index_key(user_id: uuid.UUID | str) -> str:
    return f"{_USER_INDEX_PREFIX}{user_id}"


async def create_session(user_id: uuid.UUID, response: Response, request: Request) -> str:
    """
    Legt eine serverseitige Session in Redis an, setzt ein signiertes HTTP-Only-Cookie und
    trägt den rohen Token in den Rückwärts-Index `sessions:by-user:{user_id}` ein.

    `session_id` ist eine eigene, vom rohen Bearer-Token getrennte UUID, die einmalig bei
    Erstellung generiert wird. Hartes Security-Invariant: der rohe Token darf niemals über
    eine API-Antwort nach außen gehen — nur `session_id` verlässt den Server (siehe
    list_user_sessions/terminate_session).
    """
    raw_token = secrets.token_urlsafe(32)
    signed_token = _serializer.dumps(raw_token)
    now = datetime.now(UTC).isoformat()

    session_data = {
        "user_id": str(user_id),
        "session_id": str(uuid.uuid4()),
        "user_agent": get_user_agent(request),
        "ip": get_client_ip(request),
        "created_at": now,
        "last_seen_at": now,
    }

    await _redis.setex(
        _session_key(raw_token),
        settings.session_max_age_seconds,
        json.dumps(session_data),
    )
    await _redis.sadd(_user_index_key(user_id), raw_token)
    # Refresht die TTL des gesamten Sets bei jeder neuen Session — kein Sweep/Cron nötig,
    # das Set verfällt komplett, falls der User eine volle Session-Lebensdauer lang inaktiv
    # bleibt. Einzelne verwaiste Members werden lazy in list_user_sessions() per SREM entfernt.
    await _redis.expire(_user_index_key(user_id), settings.session_max_age_seconds)

    response.set_cookie(
        key=settings.session_cookie_name,
        value=signed_token,
        max_age=settings.session_max_age_seconds,
        httponly=True,
        secure=settings.app_env != "development",
        samesite="lax",
    )
    return raw_token


async def unsign_session_token(
    signed_token: str | None, *, enforce_max_age: bool = True
) -> str | None:
    """
    Löst den rohen Token aus dem signierten Cookie-Wert. Für Endpoints, die den rohen
    Token selbst brauchen (change-password, list/terminate sessions), statt zweimal zu
    unsignen.
    """
    if not signed_token:
        return None
    try:
        if enforce_max_age:
            return _serializer.loads(signed_token, max_age=settings.session_max_age_seconds)
        return _serializer.loads(signed_token)
    except BadSignature:
        return None


async def get_user_id_by_raw_token(raw_token: str) -> uuid.UUID | None:
    """Lädt die user_id direkt anhand des rohen Tokens — für Aufrufer, die ihn bereits unsigned haben."""
    data = await _redis.get(_session_key(raw_token))
    if not data:
        return None
    return uuid.UUID(json.loads(data)["user_id"])


async def get_session_user_id(signed_token: str | None) -> uuid.UUID | None:
    raw_token = await unsign_session_token(signed_token)
    if raw_token is None:
        return None
    return await get_user_id_by_raw_token(raw_token)


async def touch_session(raw_token: str, ip: str, user_agent: str) -> None:
    """
    Aktualisiert last_seen_at/ip/user_agent — aber throttled: schreibt nur, wenn der
    vorherige last_seen_at-Wert älter als ~60s ist, um nicht bei jedem authentifizierten
    Request in Redis zu schreiben. Die TTL des Session-Keys bleibt beim ursprünglichen
    Restwert (kein Sliding-Window — die Session läuft an ihrem festen Max-Age ab).
    """
    key = _session_key(raw_token)
    data = await _redis.get(key)
    if not data:
        return

    session_data = json.loads(data)
    now = datetime.now(UTC)

    # Rollout-Übergang: Sessions aus der Zeit vor diesem Feature kennen last_seen_at noch
    # nicht — statt jedes Mal zu scheitern, einmalig auf das neue Schema anheben.
    last_seen_raw = session_data.get("last_seen_at")
    if last_seen_raw is not None:
        last_seen_at = datetime.fromisoformat(last_seen_raw)
        if (now - last_seen_at).total_seconds() < _TOUCH_MIN_INTERVAL_SECONDS:
            return

    ttl = await _redis.ttl(key)
    if ttl <= 0:
        return

    session_data.setdefault("session_id", str(uuid.uuid4()))
    session_data.setdefault("created_at", now.isoformat())
    session_data["last_seen_at"] = now.isoformat()
    session_data["ip"] = ip
    session_data["user_agent"] = user_agent
    await _redis.setex(key, ttl, json.dumps(session_data))


async def list_user_sessions(user_id: uuid.UUID, current_raw_token: str | None) -> list[dict]:
    """
    Liest alle Sessions eines Users über den Rückwärts-Index. Tote Tokens (Session-Key
    bereits abgelaufen) werden dabei lazy per SREM aus dem Index entfernt — kein separater
    Sweep-Job nötig. Gibt niemals den rohen Token zurück, nur `session_id`.

    Sessions ohne `session_id` (Rollout-Übergang: vor diesem Feature erzeugte Sessions
    kennen das Feld noch nicht, TTL bis zu 14 Tage) werden übersprungen statt einen Fehler
    zu werfen — sie bleiben für Auth-Zwecke gültig, tauchen aber erst nach Neu-Login in
    dieser Liste auf.
    """
    index_key = _user_index_key(user_id)
    tokens = list(await _redis.smembers(index_key))
    if not tokens:
        return []

    values = await _redis.mget([_session_key(token) for token in tokens])

    stale_tokens: list[str] = []
    sessions: list[dict] = []
    for token, value in zip(tokens, values, strict=True):
        if value is None:
            stale_tokens.append(token)
            continue
        data = json.loads(value)
        session_id = data.get("session_id")
        if session_id is None:
            continue
        sessions.append(
            {
                "session_id": uuid.UUID(session_id),
                "user_agent": data.get("user_agent", ""),
                "ip": data.get("ip", ""),
                "created_at": data.get("created_at"),
                "last_seen_at": data.get("last_seen_at"),
                "is_current": token == current_raw_token,
            }
        )

    if stale_tokens:
        await _redis.srem(index_key, *stale_tokens)

    return sessions


async def terminate_session(
    user_id: uuid.UUID, session_id: uuid.UUID, current_raw_token: str | None
) -> bool:
    """
    Beendet eine einzelne Session des Users, gesucht ausschließlich innerhalb des eigenen
    Rückwärts-Index (nie über User-Grenzen hinweg). Verweigert das Beenden der aktuellen
    Session (Defense in Depth, zusätzlich zum UI-seitigen Verstecken des Buttons).
    Gibt False zurück, wenn die Session nicht gefunden wurde oder es die aktuelle ist.
    """
    index_key = _user_index_key(user_id)
    tokens = list(await _redis.smembers(index_key))
    if not tokens:
        return False

    values = await _redis.mget([_session_key(token) for token in tokens])

    stale_tokens: list[str] = []
    target_token: str | None = None
    for token, value in zip(tokens, values, strict=True):
        if value is None:
            stale_tokens.append(token)
            continue
        data = json.loads(value)
        if data.get("session_id") == str(session_id):
            target_token = token

    if stale_tokens:
        await _redis.srem(index_key, *stale_tokens)

    if target_token is None:
        return False

    if target_token == current_raw_token:
        return False

    await _redis.delete(_session_key(target_token))
    await _redis.srem(index_key, target_token)
    return True


async def invalidate_other_sessions(user_id: uuid.UUID, keep_raw_token: str | None) -> None:
    """
    Invalidiert alle Sessions eines Users bis auf `keep_raw_token` (falls angegeben).
    `keep_raw_token=None` invalidiert ausnahmslos alle Sessions — genutzt vom Passwort-
    Reset-Confirm-Flow, wo es keine aktive Session gibt, die erhalten bleiben müsste.
    """
    index_key = _user_index_key(user_id)
    tokens = await _redis.smembers(index_key)
    if not tokens:
        return

    to_delete = [token for token in tokens if token != keep_raw_token]
    if not to_delete:
        return

    await _redis.delete(*[_session_key(token) for token in to_delete])
    await _redis.srem(index_key, *to_delete)


async def destroy_session(signed_token: str | None, response: Response) -> None:
    """Logout: löscht den Session-Key und entfernt den Token aus dem Rückwärts-Index des Users."""
    raw_token = await unsign_session_token(signed_token, enforce_max_age=False)
    if raw_token:
        data = await _redis.get(_session_key(raw_token))
        await _redis.delete(_session_key(raw_token))
        if data:
            user_id = json.loads(data)["user_id"]
            await _redis.srem(_user_index_key(user_id), raw_token)
    response.delete_cookie(settings.session_cookie_name)
