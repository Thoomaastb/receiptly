"""
Erste DB-gestützte Test-Infrastruktur im Projekt (bisher nur reine Funktionstests ohne
DB/Async, siehe test_pii_redaction.py/test_ollama_ssrf_guard.py). Läuft NICHT gegen eine
gemockte DB, sondern gegen eine echte Postgres-/Redis-Instanz (Security-Hardening Phase 3
verlangt u.a. echte WebAuthn-Credential-Roundtrips inkl. BYTEA-Spalte) — DATABASE_URL/
REDIS_URL kommen wie im laufenden Container aus der Umgebung (app/config.py), hier bewusst
nichts überschrieben oder gemockt.

`client`/`db` sind bewusst NICHT autouse — sie werden nur instanziiert, wenn ein Test sie
explizit anfordert, und bleiben damit ohne jeden Effekt auf die bestehenden reinen
Funktionstests (test_pii_redaction.py/test_ollama_ssrf_guard.py), die weder DB noch
Async-Fixtures brauchen. Die Tabellen-Bereinigung zwischen Tests (_clean_tables) liegt
bewusst NICHT hier, sondern lokal in test_webauthn.py — als repo-weites autouse-Fixture
hier würde sie auch für diese unbeteiligten Tests laufen.

`client` nutzt httpx.ASGITransport (In-Process, kein echter Netzwerk-Roundtrip) — Cookies
werden vom AsyncClient automatisch über mehrere Requests hinweg mitgeführt, genau wie ein
Browser es täte.
"""

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.main import app


@pytest_asyncio.fixture
async def db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
