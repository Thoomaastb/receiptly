# receiptly

Selbst gehostetes, privacy-first DMS für Kassenbons, Rechnungen und Garantiebelege.
Das Originalbild verlässt das Gerät nie — nur der extrahierte Text geht an den Server.

Vollständiges Konzept, Architektur, Datenmodell und Backlog: siehe Notion (Page "receiptly").

## Stack

| Schicht | Technologie |
|---|---|
| Frontend | SvelteKit + TypeScript + Tailwind CSS |
| Backend | FastAPI + SQLAlchemy 2.0 + asyncpg |
| Datenbank | PostgreSQL 16 |
| Cache/Queue | Redis |
| Infrastruktur | Docker (rootless) + Nginx + Pangolin/Newt |

## Lokales Setup

**Als vorgebautes Package (kein Checkout nötig)** — nur `docker-compose.yml` + `.env` besorgen:

```bash
cp .env.example .env   # Werte anpassen (v.a. POSTGRES_PASSWORD, SESSION_SECRET)

docker network create internal # vorübergehend bis v1.0.0, siehe docker-compose.yml
docker network create remote   # falls noch nicht vorhanden (Pangolin-Netzwerk)
docker compose pull
docker compose up -d

# Migrationen ausführen
docker compose exec app alembic upgrade head
```

Zugriff läuft ausschließlich über Pangolin/Newt via `remote` — Host-Ports sind daher
standardmäßig auskommentiert (nicht entfernt) in `docker-compose.yml`. Für lokales
Testen ohne Pangolin einfach die `#` vor der `ports:`-Zeile bei `app` entfernen.

App (Frontend + API im selben Container): http://localhost:8000 · API-Health: http://localhost:8000/api/health

**Lokal selbst bauen** (z.B. eigene Änderungen): `docker compose up -d --build` statt `pull`.

### Entwicklung mit Hot-Reload

```bash
# Backend mit --reload im Container
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build

# Frontend separat mit Vite-HMR (nicht in Docker, sonst nur langsamer)
cd frontend
npm install
npm run dev   # Vite-Proxy leitet /api an den App-Container weiter

alembic upgrade head   # einmalig, falls Schema noch nicht migriert
```

### Ganz ohne Docker

```bash
# Backend
cd backend
pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload

# Frontend
cd frontend
npm install
npm run dev
```

## Versionierung — Semantic Release (verbindlich)

Schema: `v.MAJOR.MINOR.PATCH`

```
feat(scope): description   → MINOR
fix(scope): description    → PATCH
feat!: description         → MAJOR — reserviert für das stabile v1.0.0-Release
chore/docs/ci/test         → kein Release
```

Gültige Scopes: `auth · receipts · buckets · pricing · documents · audit · monitoring · logs · services · dashboard · api · db · ui · docker · ci · deps · release · readme · license · security`

Commitlint (`commitlint.config.js`) erzwingt Typ und Scope. `.releaserc.json` steuert
`semantic-release`. Vor `v1.0.0` ist nichts stabil released — Reihenfolge der Minor-Versionen
kann sich noch ändern (siehe Backlog in Notion).

## Auslieferung im Dev-Chat

Pro Version wird ein ZIP-Archiv mit **nur den neuen/geänderten Dateien** geliefert, nicht der
komplette Baum. Ausnahme: die allererste Version (dieses Skeleton), da hier alles neu ist.
Kleine, punktuelle Änderungen (einzelne Zeilen, Konfig-Werte) werden stattdessen als
Suchen/Ersetzen-Anweisung im Chat geliefert — ohne neues Archiv.

## Aktueller Stand

`v0.1.0-alpha.1` — Fundament: Projekt-Skeleton, Docker-Setup, Auth-Grundgerüst, Basis-Datenschema,
CSS-Tokens. Siehe `CHANGELOG.md` für Details, Notion-Backlog für die weiteren Etappen bis `v1.0.0`.
