"""
Extrahiert Client-IP und User-Agent aus einem FastAPI-`Request`.

Bewusst als eigenständiges, von `session.py` unabhängiges Modul ohne Abhängigkeiten auf
Session-Storage-Interna gehalten: `concepts/security-hardening.md` plant, exakt diesen
Baustein für Rate-Limiting (v0.24) wiederzuverwenden.

Wichtig: In diesem Paket (Sitzungsverwaltung, v0.23.x) dient die IP ausschließlich der
Anzeige in der Sessions-Liste — sie fließt in keine Auth- oder Rate-Limit-Entscheidung
ein. Das Vertrauen in `X-Forwarded-For` setzt die dokumentierte Pangolin→nginx-
Zweisprung-Topologie voraus (Reverse-Proxy-Kette mit genau zwei Hops vor der App); das ist
aus diesem Repo allein nicht verifizierbar und wird als akzeptiertes Risiko behandelt. Wer
diesen Header für sicherheitsrelevante Entscheidungen (z.B. Rate-Limiting) wiederverwendet,
muss die Proxy-Topologie am Zielort erneut prüfen.
"""

from fastapi import Request

_USER_AGENT_MAX_LENGTH = 300


def get_client_ip(request: Request) -> str:
    """
    Erster Eintrag aus `X-Forwarded-For`, sonst `X-Real-IP`, sonst `request.client.host`
    (Fallback für lokale Entwicklung ohne vorgeschalteten Proxy).
    """
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()

    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()

    if request.client:
        return request.client.host

    return "unknown"


def get_user_agent(request: Request) -> str:
    """Roher `User-Agent`-Header, auf eine sinnvolle Maximallänge gekappt (untrusted input)."""
    user_agent = request.headers.get("user-agent", "")
    return user_agent[:_USER_AGENT_MAX_LENGTH]
