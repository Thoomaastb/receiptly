"""
Kurzlebige Zwischenspeicherung für WebAuthn-Challenges (Registrierung + Login),
Security-Hardening Phase 3 (siehe concepts/security-hardening.md Abschnitt 4.3). Gebaut
nach demselben Muster wie app/auth/pending_2fa.py (Redis + kurze TTL), aber bewusst ein
eigenständiges Modul: andere Nutzdaten (rohe Challenge-Bytes statt Login-Zustand), zwei
Verwendungen mit unterschiedlicher Schlüsselherkunft.

Registrierung: der Aufrufer ist bereits per Session authentifiziert (get_current_user),
die Challenge wird deshalb direkt an user.id gebunden — höchstens eine offene
Registrierungs-Challenge pro User gleichzeitig, ein erneuter /register/options-Aufruf
überschreibt eine noch offene vorherige.

Login: hier existiert noch keine Session/kein user.id, den der Client zurückschicken
könnte, ohne selbst wieder ein Auth-Token zu benötigen. Stattdessen bekommt der Client
bei /authenticate/options eine zufällige, nicht erratbare Options-ID im Response-Body
zurück (kein Cookie) und schickt sie bei /authenticate/verify wieder mit — die Options-ID
referenziert nur die zwischengespeicherte Challenge + den vorab per Username aufgelösten
user_id, sie gewährt für sich genommen keinerlei Zugriff.

Beide Varianten lösen die Challenge per GETDEL atomar auf (Einmalgebrauch, kein Replay
derselben Challenge über einen zweiten /verify-Aufruf).
"""

import json
import secrets
import uuid

import redis.asyncio as redis

from app.config import get_settings

settings = get_settings()
_redis = redis.from_url(settings.redis_url, decode_responses=False)

_REG_KEY_PREFIX = "webauthn-reg-challenge:"
_AUTH_KEY_PREFIX = "webauthn-auth-challenge:"
_TTL_SECONDS = 300  # 5 Minuten, wie pending_2fa.py


def _reg_key(user_id: uuid.UUID) -> str:
    return f"{_REG_KEY_PREFIX}{user_id}"


async def store_registration_challenge(user_id: uuid.UUID, challenge: bytes) -> None:
    await _redis.setex(_reg_key(user_id), _TTL_SECONDS, challenge)


async def pop_registration_challenge(user_id: uuid.UUID) -> bytes | None:
    """None, wenn keine (mehr) offene Challenge existiert (nie angelegt, verbraucht oder abgelaufen)."""
    return await _redis.getdel(_reg_key(user_id))


async def store_authentication_challenge(user_id: uuid.UUID, challenge: bytes) -> str:
    """Legt eine neue, zufällige Options-ID an und gibt sie zurück — geht in den Response an den Client."""
    options_id = secrets.token_urlsafe(32)
    payload = json.dumps({"user_id": str(user_id), "challenge": challenge.hex()}).encode("utf-8")
    await _redis.setex(f"{_AUTH_KEY_PREFIX}{options_id}", _TTL_SECONDS, payload)
    return options_id


async def pop_authentication_challenge(options_id: str) -> tuple[uuid.UUID, bytes] | None:
    """None bei unbekannter/abgelaufener/bereits verbrauchter Options-ID."""
    data = await _redis.getdel(f"{_AUTH_KEY_PREFIX}{options_id}")
    if not data:
        return None
    payload = json.loads(data)
    return uuid.UUID(payload["user_id"]), bytes.fromhex(payload["challenge"])
