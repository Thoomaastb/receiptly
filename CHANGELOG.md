## 1.0.0 (2026-07-03)

### Features

* **services:** initial receiptly project skeleton ([af266ad](https://github.com/Thoomaastb/receiptly/commit/af266ad9dc46e883db01adeb41e7fce32f3b27aa))

# Changelog

Alle nennenswerten Änderungen an receiptly werden hier dokumentiert.
Format angelehnt an [Keep a Changelog](https://keepachangelog.com/de/1.0.0/),
Versionierung nach Semantic Release (siehe README → Versionierung).

## [Unreleased] - Nachlieferung zu 0.1.0-alpha.1

### Behoben
- `docker-compose.yml`: Ports für Backend (8000) und Frontend (3000) fehlten — ohne Pangolin
  war lokal kein Zugriff möglich
- `backend/pyproject.toml`: fehlendes `[build-system]` ließ `pip install -e .` fehlschlagen
- `backend/pyproject.toml`: `email-validator` fehlte für Pydantic `EmailStr` in den Auth-Schemas
- `.releaserc.json`: `VERSION`-Datei war kein Git-Asset — `@semantic-release/git` hätte sie nie
  mitcommittet

### Hinzugefügt
- `.github/workflows/release.yml` — Semantic Release (Node-only, kein Go-Anteil)
- `.github/workflows/docker.yml` — Matrix-Build Backend+Frontend, multi-arch (amd64/arm64),
  getriggert vom semantic-release Git-Tag statt jedem Push auf `main`
- `.github/dependabot.yml` — `pip` (backend/), `npm` (frontend/), `github-actions` (/)

## [0.1.0-alpha.1] - 2026-07-03

### Hinzugefügt
- Projekt-Skeleton: SvelteKit-Frontend + FastAPI-Backend + PostgreSQL 16 + Redis
- Docker-Setup (rootless), Netzwerke `intern-receiptly` (internal) + `remote` (Pangolin)
- Auth-Grundgerüst: Argon2id-Passwort-Hashing, HTTP-Only-Session-Cookies, RBAC (Admin/User)
- Datenbank-Basisschema (Alembic-Migration 0001): `households`, `users`, `buckets`,
  `bucket_access`, `merchants`, `products`, `receipts`, `items`
- Household-Bucket wird beim Anlegen eines Haushalts automatisch erzeugt (`is_default`, nicht löschbar)
- CSS-Tokens/Variablen-Basis (Light/Dark über `prefers-color-scheme`)
- Semantic-Release-Konfiguration inkl. Commit-Scopes

### Offen
- Lizenz (proprietär vs. AGPL) — siehe Notion, offene Entscheidung
- Thumbnail-Strategie — siehe Notion, offene Entscheidung
