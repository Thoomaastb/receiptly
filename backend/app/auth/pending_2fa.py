"""
Pre-Auth-Zwischenzustand für den zweistufigen TOTP-Login (Security-Hardening Phase 2).
Gebaut nach demselben Muster wie app/auth/session.py (Redis + `URLSafeTimedSerializer`),
aber bewusst getrennt: eigener Cookie-Name, eigener Redis-Key-Prefix, deutlich kürzere TTL
und KEIN Rückwärts-Index (ein User hat immer höchstens einen aktiven Pre-Auth-Versuch,
ein Sweep über alle offenen Versuche ist nicht nötig).

Dasselbe harte Invariant wie bei der echten Session gilt hier ebenso: der rohe Token
verlässt niemals eine API-Antwort, nur das HttpOnly-Cookie transportiert ihn. Der
Pre-Auth-State gewährt zwar noch keinen App-Zugriff (erster Faktor ok, zweiter offen),
wäre aber trotzdem ein wertvolles Ziel für Cookie-Diebstahl während einer laufenden
Login-Ceremony.
"""

import json
import secrets
import uuid

import redis.asyncio as redis
from fastapi import Request, Response
from itsdangerous import BadSignature, URLSafeTimedSerializer

from app.config import get_settings

settings = get_settings()
_redis = redis.from_url(settings.redis_url, decode_responses=True)
_serializer = URLSafeTimedSerializer(settings.session_secret, salt="receiptly-pending-2fa")

_KEY_PREFIX = "pending-2fa:"
PENDING_2FA_COOKIE_NAME = "receiptly_pending_2fa"
_TTL_SECONDS = 300  # 5 Minuten
_MAX_FAILED_ATTEMPTS = 5

# register_failed_attempt() las den Zähler früher per GET, erhöhte ihn in Python und
# schrieb per SETEX zurück — bei parallelen Requests gegen denselben Pending-Token ein
# klassisches Lost-Update (beide lesen z.B. failed_attempts=3, beide schreiben 4 zurück,
# ein Fehlversuch geht verloren). Ein Lua-Script läuft in Redis atomar/unteilbar (Redis
# ist während der Skript-Ausführung single-threaded blockiert) und übernimmt deshalb
# GET+Erhöhen+TTL-Erhalt+SETEX bzw. DELETE als einen einzigen, nicht unterbrechbaren
# Schritt — analog zum atomaren INCR-Muster in app/auth/rate_limit.py, hier aber mit
# zusätzlicher Logik (JSON-Payload, TTL-Erhalt, bedingtes Löschen), die ein einzelner
# Redis-Befehl nicht abbilden kann.
_REGISTER_FAILED_ATTEMPT_SCRIPT = """
local data = redis.call('GET', KEYS[1])
if not data then
    return -1
end

local payload = cjson.decode(data)
payload['failed_attempts'] = payload['failed_attempts'] + 1

if payload['failed_attempts'] >= tonumber(ARGV[1]) then
    redis.call('DEL', KEYS[1])
    return 1
end

local ttl = redis.call('TTL', KEYS[1])
if ttl <= 0 then
    ttl = tonumber(ARGV[2])
end
redis.call('SETEX', KEYS[1], ttl, cjson.encode(payload))
return 0
"""
# register_script() cached client-seitig und ruft bei Aufruf intern EVALSHA auf (Fallback
# auf EVAL bei NOSCRIPT) — kein manuelles SHA-Handling nötig.
_register_failed_attempt_script = _redis.register_script(_REGISTER_FAILED_ATTEMPT_SCRIPT)


def _key(raw_token: str) -> str:
    return f"{_KEY_PREFIX}{raw_token}"


async def create_pending_2fa(user_id: uuid.UUID, response: Response, request: Request) -> None:
    """
    Legt den Pre-Auth-State nach erfolgreicher Passwortprüfung an — VOR jeder vollen
    Session. Kein Response-Body-Token (siehe Modul-Docstring), nur das Cookie trägt ihn.
    `request` wird aktuell nicht zur Herleitung des Keys gebraucht, bleibt aber im
    Funktionssignatur-Muster von `session.create_session()` für Konsistenz/spätere
    Metadaten (z.B. IP-Bindung) erhalten.
    """
    raw_token = secrets.token_urlsafe(32)
    signed_token = _serializer.dumps(raw_token)

    await _redis.setex(
        _key(raw_token),
        _TTL_SECONDS,
        json.dumps({"user_id": str(user_id), "failed_attempts": 0}),
    )

    response.set_cookie(
        key=PENDING_2FA_COOKIE_NAME,
        value=signed_token,
        max_age=_TTL_SECONDS,
        httponly=True,
        secure=settings.app_env != "development",
        samesite="lax",
    )


def _unsign(signed_token: str | None) -> str | None:
    if not signed_token:
        return None
    try:
        return _serializer.loads(signed_token, max_age=_TTL_SECONDS)
    except BadSignature:
        return None


async def get_pending_user_id(signed_token: str | None) -> uuid.UUID | None:
    """Löst den Pre-Auth-State auf. None, wenn Cookie fehlt/ungültig/abgelaufen oder in Redis verfallen."""
    raw_token = _unsign(signed_token)
    if raw_token is None:
        return None
    data = await _redis.get(_key(raw_token))
    if not data:
        return None
    return uuid.UUID(json.loads(data)["user_id"])


async def register_failed_attempt(signed_token: str | None) -> bool:
    """
    Erhöht den Fehlversuchszähler für den aktuellen Pending-Token und gibt True zurück,
    wenn dadurch das Limit erreicht und der State bereits verworfen wurde (zurück auf den
    ersten Faktor). Bewusst NICHT zeitfensterbasiert wie app/auth/rate_limit.py, sondern
    strikt an diesen einen Pending-Token gebunden — ein neuer Login-Versuch über
    /auth/login erzeugt einen frischen Token mit Zähler 0 (und durchläuft dabei wieder
    dessen eigene IP-/Username-Rate-Limits).

    Läuft komplett als atomares Lua-Script in Redis (siehe _REGISTER_FAILED_ATTEMPT_SCRIPT
    oben) statt als GET-in-Python-erhöhen-SETEX-Sequenz — verhindert einen Lost-Update bei
    parallelen Requests gegen denselben Pending-Token (z.B. zwei fast gleichzeitige falsche
    Codes).
    """
    raw_token = _unsign(signed_token)
    if raw_token is None:
        return False

    result = await _register_failed_attempt_script(
        keys=[_key(raw_token)], args=[_MAX_FAILED_ATTEMPTS, _TTL_SECONDS]
    )
    if result == -1:
        return False
    return result == 1


async def destroy_pending_2fa(signed_token: str | None, response: Response) -> None:
    """Löscht den Pre-Auth-State (Redis + Cookie) — nach erfolgreichem zweiten Faktor oder Abbruch."""
    raw_token = _unsign(signed_token)
    if raw_token:
        await _redis.delete(_key(raw_token))
    response.delete_cookie(PENDING_2FA_COOKIE_NAME)
