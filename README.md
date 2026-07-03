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

```bash
cp .env.example .env   # Werte anpassen (v.a. POSTGRES_PASSWORD, SESSION_SECRET)

docker network create remote   # falls noch nicht vorhanden (Pangolin-Netzwerk)
docker compose up -d --build

# Migrationen ausführen
docker compose exec backend alembic upgrade head
```

Frontend: http://localhost:3000 · Backend: http://localhost:8000/health

### Ohne Docker (Entwicklung)

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

Gültige Scopes: `auth · pim · audit · monitoring · logs · services · dashboard · hub · spoke · api · db · ui · installer · docker · ci · deps · release · readme · license · security`

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
