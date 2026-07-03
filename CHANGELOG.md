# Changelog

Alle nennenswerten Änderungen an receiptly werden hier dokumentiert.
Format angelehnt an [Keep a Changelog](https://keepachangelog.com/de/1.0.0/),
Versionierung nach Semantic Release (siehe README → Versionierung).

## [Unreleased] - Scan & Upload (→ 0.2.0 bei feat-Commit)

Inhaltlich identisch zum ursprünglich als "v0.1.0-alpha.2" geplanten Paket — nur mit der
neuen flachen Versionsnummer (siehe .releaserc.json-Fix).

### Hinzugefügt
- Backend: File Storage Service (`storage/originals/<household_id>/`), SHA-256 content_hash
- Backend: `POST /receipts/upload` — Multipart-Upload, Bucket-Schreibrecht-Prüfung
  (Owner immer, sonst nur mit explizitem `edit`-Grant; private Buckets ohne Freigabe = 404)
- Migration 0002: `receipt_date`/`total_amount` nullable (beim Upload vor OCR/KI noch unbekannt)
- Frontend: `OCRProvider`-Interface, `TesseractProvider` (WASM-Fallback), `NativeOCRProvider`-Stub
- Frontend: Upload-Seite mit Fortschrittsanzeige (OCR-Phase + Upload-Phase getrennt)

### Bekannte Lücken (bewusst offen für dieses Paket)
- `bucket_id` beim Upload ist noch ein Platzhalter — echter Bucket-Switcher fehlt,
  bis das Buckets-Paket kommt. Upload schlägt ohne echte `bucket_id` aktuell fehl.

## [0.1.0-alpha.1] - 2026-07-03

Konsolidierte Baseline. Ersetzt alle vorherigen Zwischenstände vollständig —
dies ist der verbindliche Repo-Zustand nach dem Reset.

### Hinzugefügt
- Projekt-Skeleton: SvelteKit-Frontend + FastAPI-Backend + PostgreSQL 16 + Redis
- Docker-Setup (rootless), Netzwerke `intern-receiptly` (internal) + `remote` (Pangolin),
  Ports 8000 (Backend) / 3000 (Frontend) für lokalen Zugriff
- Auth-Grundgerüst: Argon2id-Passwort-Hashing, HTTP-Only-Session-Cookies, RBAC (Admin/User)
- Datenbank-Basisschema (Alembic-Migration 0001): `households`, `users`, `buckets`,
  `bucket_access`, `merchants`, `products`, `receipts`, `items`
- Household-Bucket wird beim Anlegen eines Haushalts automatisch erzeugt (`is_default`, nicht löschbar)
- CSS-Tokens/Variablen-Basis (Light/Dark über `prefers-color-scheme`)
- `.github/workflows/release.yml` — Semantic Release über PAT (`RELEASE_TOKEN`), damit
  Folge-Workflows (Docker-Build) korrekt vom Tag-Push ausgelöst werden
- `.github/workflows/docker.yml` — Matrix-Build Backend+Frontend, multi-arch (amd64/arm64),
  getriggert von Version-Tags (`v*.*.*`)
- `.github/dependabot.yml` — `pip` (backend/), `npm` (frontend/), `github-actions` (/)
- `.releaserc.json` — Alpha-Prerelease-Kanal (`prerelease: "alpha"` auf `main`),
  `VERSION`-Datei als Git-Asset

### Offen
- Lizenz (proprietär vs. AGPL) — siehe Notion, offene Entscheidung
- Thumbnail-Strategie — siehe Notion, offene Entscheidung

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
