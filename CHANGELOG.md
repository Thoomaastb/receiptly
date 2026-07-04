## [0.5.4](https://github.com/Thoomaastb/receiptly/compare/v0.5.3...v0.5.4) (2026-07-04)

### Bug Fixes

* **docker:** comment out unused host ports, fix stale app service reference in README ([8fabbbb](https://github.com/Thoomaastb/receiptly/commit/8fabbbb354e56b030aee80a90d74c1b442124988))

## [0.5.3](https://github.com/Thoomaastb/receiptly/compare/v0.5.2...v0.5.3) (2026-07-04)

### Bug Fixes

* **docker:** manage internal and remote networks externally, temporary until v1.0.0 ([942ee2f](https://github.com/Thoomaastb/receiptly/commit/942ee2f6435e34858867bc90a6a2f69281369411))

## [0.5.2](https://github.com/Thoomaastb/receiptly/compare/v0.5.1...v0.5.2) (2026-07-04)

### Bug Fixes

* **docker:** revert to two containers with nginx-served frontend and API proxy ([7d4dd21](https://github.com/Thoomaastb/receiptly/commit/7d4dd2111c89835a748ce37c9bbea2e4cbe36139))

## [0.5.1](https://github.com/Thoomaastb/receiptly/compare/v0.5.0...v0.5.1) (2026-07-03)

### Bug Fixes

* **ci:** restore persist-credentials false so RELEASE_TOKEN triggers docker.yml on tag push ([640242c](https://github.com/Thoomaastb/receiptly/commit/640242c8e2f1a9a1a97f6cdc757caa9f2fdbf08d))

## [0.5.0](https://github.com/Thoomaastb/receiptly/compare/v0.4.0...v0.5.0) (2026-07-03)

### Features

* **docker:** combine backend and frontend into single deployable container ([ecc0915](https://github.com/Thoomaastb/receiptly/commit/ecc0915c19ca134634ed81344a9bb9d3247a4862))

## [0.4.0](https://github.com/Thoomaastb/receiptly/compare/v0.3.0...v0.4.0) (2026-07-03)

### Features

* **ui:** add masonry receipt feed with bucket grouping and card-to-modal transition ([2aeb3d4](https://github.com/Thoomaastb/receiptly/commit/2aeb3d4373d14f477fbc604c22e3ab1317763848))

## [0.3.0](https://github.com/Thoomaastb/receiptly/compare/v0.2.0...v0.3.0) (2026-07-03)

### Features

* **receipts:** add receipt list/detail endpoints and wire OCR text into upload ([943d0a0](https://github.com/Thoomaastb/receiptly/commit/943d0a0c5d341681e3acc5b058684d4b06524765))

## [0.2.0](https://github.com/Thoomaastb/receiptly/compare/v0.1.1...v0.2.0) (2026-07-03)

### Features

* **buckets:** add read-only bucket listing and wire it into upload flow ([c7c7a5d](https://github.com/Thoomaastb/receiptly/commit/c7c7a5d0aa641347d80f84c4ec782a6c92b37520))

## [0.1.1](https://github.com/Thoomaastb/receiptly/compare/v0.1.0...v0.1.1) (2026-07-03)

### Bug Fixes

* **ci:** restore automatic push-triggered releases ([1f38184](https://github.com/Thoomaastb/receiptly/commit/1f381846912a5e4c047b1d4914cf31bfeb13e722))

## 1.0.0 (2026-07-03)

### Features

* **pim:** add receipt upload flow with client-side OCR and file storage service ([0c1de32](https://github.com/Thoomaastb/receiptly/commit/0c1de329c7d58eb9e23730fdbc7cdca7d68b202c))
* **services:** initial receiptly project skeleton ([af266ad](https://github.com/Thoomaastb/receiptly/commit/af266ad9dc46e883db01adeb41e7fce32f3b27aa))

### Bug Fixes

* **ci:** remove persist-credentials false blocking semantic-release branch resolution ([95a91d1](https://github.com/Thoomaastb/receiptly/commit/95a91d174b5806119cfea821d8d6ab3372d81ab9))
* **ci:** replace non-receiptly commit scopes with real domain scopes ([58bdd96](https://github.com/Thoomaastb/receiptly/commit/58bdd96464338248eaa2b622c4ecd803b06aba67))
* **ci:** switch release workflow to manual trigger during alpha/beta phase ([e33e9e4](https://github.com/Thoomaastb/receiptly/commit/e33e9e4a3f13bfae771175b33eea9040db4b0bf0))
* **release:** configure alpha prerelease channel and use PAT to trigger downstream workflows ([23b9805](https://github.com/Thoomaastb/receiptly/commit/23b9805e643e491a6d27281a9210fdf0f870b5a1))
* **release:** consolidate skeleton with alpha prerelease channel and PAT-based release trigger ([d77cef9](https://github.com/Thoomaastb/receiptly/commit/d77cef94198c3b07b7896365a0786c22778cd2f9))

## 1.0.0 (2026-07-03)

### Features

* **pim:** add receipt upload flow with client-side OCR and file storage service ([0c1de32](https://github.com/Thoomaastb/receiptly/commit/0c1de329c7d58eb9e23730fdbc7cdca7d68b202c))
* **services:** initial receiptly project skeleton ([af266ad](https://github.com/Thoomaastb/receiptly/commit/af266ad9dc46e883db01adeb41e7fce32f3b27aa))

### Bug Fixes

* **ci:** remove persist-credentials false blocking semantic-release branch resolution ([95a91d1](https://github.com/Thoomaastb/receiptly/commit/95a91d174b5806119cfea821d8d6ab3372d81ab9))
* **ci:** replace non-receiptly commit scopes with real domain scopes ([58bdd96](https://github.com/Thoomaastb/receiptly/commit/58bdd96464338248eaa2b622c4ecd803b06aba67))
* **release:** configure alpha prerelease channel and use PAT to trigger downstream workflows ([23b9805](https://github.com/Thoomaastb/receiptly/commit/23b9805e643e491a6d27281a9210fdf0f870b5a1))
* **release:** consolidate skeleton with alpha prerelease channel and PAT-based release trigger ([d77cef9](https://github.com/Thoomaastb/receiptly/commit/d77cef94198c3b07b7896365a0786c22778cd2f9))

# Changelog

Alle nennenswerten Änderungen an receiptly werden hier dokumentiert.
Format angelehnt an [Keep a Changelog](https://keepachangelog.com/de/1.0.0/),
Versionierung nach Semantic Release (siehe README → Versionierung).

## [Unreleased] - Single-Container-Package

### Geändert
- Frontend: `adapter-node` → `adapter-static` (SPA-Modus, `ssr=false`), kein
  eigener Node-Prozess mehr zur Laufzeit nötig
- Backend: alle API-Routen unter `/api/*`-Präfix (vorher `/auth`, `/receipts`,
  `/buckets`, `/health` ohne Präfix) — Voraussetzung für Single-Container
- `docker-compose.yml`: ein `app`-Service (Backend + statisches Frontend im
  selben Prozess) statt getrennter `backend`/`frontend`-Services. Referenziert
  ein vorgebautes GHCR-Image (`image:`), `docker compose pull` funktioniert
  ohne Code-Checkout. `build:` bleibt als lokaler Fallback bestehen.
- `.github/workflows/docker.yml`: baut ein kombiniertes Image statt einer
  Matrix aus zwei Images

### Hinzugefügt
- Root-`Dockerfile` (Multi-Stage: Node baut Frontend statisch → Python-Image
  liefert Backend-API und Frontend-Assets im selben Prozess aus, inkl.
  SPA-Fallback auf `index.html` für Client-seitiges Routing)
- `docker-compose.dev.yml` — Hot-Reload-Override für Backend (`--reload`
  + Volume-Mount); Frontend-Hot-Reload läuft weiterhin über `npm run dev`
- `.dockerignore`

### Entfernt
- `frontend/Dockerfile` (ersetzt durch das kombinierte Root-Dockerfile;
  `adapter-static`-Output ist ohnehin kein eigenständig lauffähiger Server mehr)

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
