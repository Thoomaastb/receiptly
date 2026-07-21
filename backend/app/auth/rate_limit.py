"""
Redis-INCR+EXPIRE-Zähler für sicherheitskritische Auth-Endpoints (Login, Passwort-Reset,
Passwortänderung). Kein dauerhaftes Sperren, nur TTL-Backoff — bei Überschreitung 429 mit
`Retry-After` (verbleibende TTL in Sekunden).

Zwei Aufrufmuster, weil FastAPI-`Depends()` vor dem Parsen des Request-Bodys läuft:
- `rate_limit(...)` liefert eine `Depends()`-fähige async Funktion für Limits, die sich
  rein aus Request-Metadaten ableiten lassen (Default-Key: Client-IP über
  `request_meta.get_client_ip()`) — z.B. "20 Versuche/15min pro IP".
- `check_rate_limit(...)` ist dieselbe Zähl-/Block-Logik als direkt aufrufbare Funktion,
  für Limits, die zusätzlich Body-Daten brauchen (z.B. Username aus dem Login-Payload) —
  die Route ruft sie selbst nach dem Body-Parse auf. `rate_limit()` ist nur ein dünner
  `Depends()`-Wrapper um dieselbe Funktion.

Bewusst KEIN Audit-Logging (`record_event`) direkt in diesem Modul: `audit_log.household_id`
ist NOT NULL, ein rein IP-basierter Limit-Check läuft aber strukturell oft, bevor überhaupt
ein User/Haushalt bekannt ist (z.B. das IP-only-Login-Limit unten, vor dem Body-Parse) —
exakt dasselbe Problem wie bei einem fehlgeschlagenen Login mit unbekanntem Username (siehe
app/api/auth.py). Statt das hier zu erzwingen (Dependency bräuchte eine DB-Session UND einen
Fallback für "kein Haushalt bekannt"), loggen die aufrufenden Endpoints selbst, wenn und
soweit sie zum Zeitpunkt eines 429 bereits einen Haushalt kennen. Hält dieses Modul zudem
frei von einer DB-Abhängigkeit — ein reiner, wiederverwendbarer Redis-Baustein.
"""

from typing import Callable

import redis.asyncio as redis
from fastapi import HTTPException, Request, status

from app.auth.request_meta import get_client_ip
from app.config import get_settings

settings = get_settings()
_redis = redis.from_url(settings.redis_url, decode_responses=True)

_KEY_PREFIX = "ratelimit:"


async def check_rate_limit(bucket: str, key: str, limit: int, window_seconds: int) -> None:
    """
    Erhöht den Zähler für `bucket:key` atomar per INCR, setzt beim ersten Treffer im
    Fenster die TTL. Wirft `HTTPException(429)` mit `Retry-After` bei Überschreitung — die
    TTL läuft unverändert weiter (kein Reset des Fensters durch weitere Versuche).
    """
    redis_key = f"{_KEY_PREFIX}{bucket}:{key}"
    count = await _redis.incr(redis_key)
    if count == 1:
        await _redis.expire(redis_key, window_seconds)

    if count > limit:
        ttl = await _redis.ttl(redis_key)
        retry_after = ttl if ttl > 0 else window_seconds
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Zu viele Versuche — bitte später erneut versuchen.",
            headers={"Retry-After": str(retry_after)},
        )


def rate_limit(
    bucket: str,
    limit: int,
    window_seconds: int,
    key_func: Callable[[Request], str] | None = None,
) -> Callable:
    """
    `Depends()`-Factory für Limits, die ausschließlich aus Request-Metadaten ableitbar sind.
    Default-Key ist die Client-IP; `key_func` erlaubt einen anderen reinen Request-Key
    (für Body-abhängige Keys wie Username/E-Mail siehe `check_rate_limit()` direkt).
    """
    resolve_key = key_func or get_client_ip

    async def dependency(request: Request) -> None:
        await check_rate_limit(bucket, resolve_key(request), limit, window_seconds)

    return dependency
