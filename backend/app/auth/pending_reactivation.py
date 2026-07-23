"""
Pre-Session-Zwischenzustand für die Reaktivierung eines Kontos während der 14-tägigen
Löschungs-Karenzzeit (siehe concepts/konto-loeschen-datenexport.md 3.4 und
app/services/account_deletion.py::check_reactivation_required) — 1:1 nach dem Muster von
app/auth/pending_2fa.py gebaut (Redis + `URLSafeTimedSerializer`), aber bewusst ein
eigenständiges Modul: eigener Cookie-Name, eigener Redis-Key-Prefix, eigener Salt.

Anders als pending_2fa.py OHNE Fehlversuchs-Zähler: der User hat zu diesem Zeitpunkt
bereits ALLE Login-Faktoren erfolgreich durchlaufen (Passwort/Passkey + ggf. TOTP, siehe
_finalize_first_factor()/login_with_totp() in app/api/auth.py) — dieser Zwischenzustand
ist kein Credential-Rate-Limit-Ziel mehr, sondern nur noch eine reine Ja/Nein-Bestätigung
("willst du dein Konto reaktivieren?"). POST /account/reactivate hat ein eigenes,
zeitfensterbasiertes Rate-Limit (siehe app/api/account.py) als Schutz gegen Missbrauch.
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
_serializer = URLSafeTimedSerializer(settings.session_secret, salt="receiptly-pending-reactivation")

_KEY_PREFIX = "pending-reactivation:"
PENDING_REACTIVATION_COOKIE_NAME = "receiptly_pending_reactivation"
_TTL_SECONDS = 300  # 5 Minuten, wie pending_2fa.py


def _key(raw_token: str) -> str:
    return f"{_KEY_PREFIX}{raw_token}"


async def create_pending_reactivation(
    user_id: uuid.UUID, response: Response, request: Request
) -> None:
    """
    Legt den Pending-Reactivation-State an — nach vollständig erfolgreicher Auth eines
    Kontos in der Karenzzeit, statt einer echten Session. Kein Response-Body-Token (siehe
    Modul-Docstring), nur das Cookie trägt ihn. `request` bleibt ungenutzt im Signatur-
    Muster von create_session()/create_pending_2fa() für Konsistenz.
    """
    raw_token = secrets.token_urlsafe(32)
    signed_token = _serializer.dumps(raw_token)

    await _redis.setex(_key(raw_token), _TTL_SECONDS, json.dumps({"user_id": str(user_id)}))

    response.set_cookie(
        key=PENDING_REACTIVATION_COOKIE_NAME,
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


async def get_pending_reactivation_user_id(signed_token: str | None) -> uuid.UUID | None:
    """None, wenn Cookie fehlt/ungültig/abgelaufen oder in Redis verfallen."""
    raw_token = _unsign(signed_token)
    if raw_token is None:
        return None
    data = await _redis.get(_key(raw_token))
    if not data:
        return None
    return uuid.UUID(json.loads(data)["user_id"])


async def destroy_pending_reactivation(signed_token: str | None, response: Response) -> None:
    """Löscht den Pending-Reactivation-State (Redis + Cookie) — nach Reaktivierung oder Abbruch."""
    raw_token = _unsign(signed_token)
    if raw_token:
        await _redis.delete(_key(raw_token))
    response.delete_cookie(PENDING_REACTIVATION_COOKIE_NAME)
