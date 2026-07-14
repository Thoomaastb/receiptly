## [0.21.0](https://github.com/Thoomaastb/receiptly/compare/v0.20.0...v0.21.0) (2026-07-14)

### Features

* **ui:** laufende App-Version im Benutzermenü anzeigen, aus Release-Tag via Docker-Build-Arg befüllt ([4deba91](https://github.com/Thoomaastb/receiptly/commit/4deba91da5e94f474e9f055698b9cbd7f99667a3))

### Bug Fixes

* **receipts:** PDF-Upload brach im OCR-Schritt ab, da TesseractJS nur Bilder verarbeiten kann ([2107c85](https://github.com/Thoomaastb/receiptly/commit/2107c858abe2a29fe096830c79e4cf348a318deb))

## [0.20.0](https://github.com/Thoomaastb/receiptly/compare/v0.19.1...v0.20.0) (2026-07-10)

### Features

* **receipts:** Belegliste-Feinschliff - Sortierung nach Datum/Betrag, Lazy-Load-Pagination, Topbar-Suche verlinkt ([a3e0e60](https://github.com/Thoomaastb/receiptly/commit/a3e0e60248f53759dec696fcee567d71120c1263))

## [0.19.1](https://github.com/Thoomaastb/receiptly/compare/v0.19.0...v0.19.1) (2026-07-10)

### Bug Fixes

* **receipts:** Artikel-Menge fließt jetzt in die Gesamtsumme ein, neues Feldpaar Anzahl/Menge-pro-Einheit für Mengen-Tracking (z.B. 6x1,5l = 9l) ([4c0f210](https://github.com/Thoomaastb/receiptly/commit/4c0f2105d41ec3f59338ac9d66bfc25a0d71cd34))

## [0.19.0](https://github.com/Thoomaastb/receiptly/compare/v0.18.0...v0.19.0) (2026-07-10)

### Features

* **receipts:** Beleg-Lifecycle - Löschen, echte Datei-Vorschau/-Download, aufklappbarer Erkannter-Text-Bereich ([14318d7](https://github.com/Thoomaastb/receiptly/commit/14318d75891c6e4acd6774ab94fdb141c39867eb))

### Bug Fixes

* **docker:** storage-Volumes waren root-owned, non-root Backend-User konnte nie hineinschreiben — jeder Upload crashte ([56e603f](https://github.com/Thoomaastb/receiptly/commit/56e603f5485da8ba6be42042fd9ee7aa7e89c898))

## [0.18.0](https://github.com/Thoomaastb/receiptly/compare/v0.17.3...v0.18.0) (2026-07-10)

### Features

* **receipts:** Suche-&-Filter-Screen mit Volltext-Suche, Typ-/Kategorie-Chips und Zeilen-Ergebnisliste ([c8fe6ce](https://github.com/Thoomaastb/receiptly/commit/c8fe6ce4d38fdb3c2fbb4cfd6ccacdf2a5872637))

### Bug Fixes

* **dev:** vite dev proxy stripped /api prefix, brach jeden API-Call unter npm run dev ([512a716](https://github.com/Thoomaastb/receiptly/commit/512a716040b5b049d5befbc172d84424c9b2f691))

## [0.17.3](https://github.com/Thoomaastb/receiptly/compare/v0.17.2...v0.17.3) (2026-07-07)

### Bug Fixes

* **ui:** Profile submenu and added functionalities ([f54f922](https://github.com/Thoomaastb/receiptly/commit/f54f922d3d98b40264eaa2c548b9a38f72f7972a))

## [0.17.2](https://github.com/Thoomaastb/receiptly/compare/v0.17.1...v0.17.2) (2026-07-07)

### Bug Fixes

* **price:** sum can be correctly extracted. articles will get a notification badge to accomodate the missing sum until it's met 1:1 ([93aaa16](https://github.com/Thoomaastb/receiptly/commit/93aaa160dbd65ebe09f7a9d63858f2f5aacaef80))

## [0.17.1](https://github.com/Thoomaastb/receiptly/compare/v0.17.0...v0.17.1) (2026-07-07)

### Bug Fixes

* **pricing:** sum and articles are not connected. fixed by summing the articles by quantities automatically ([d010057](https://github.com/Thoomaastb/receiptly/commit/d010057aae29181e4e379eea22da956a8471ea42))

## [0.17.0](https://github.com/Thoomaastb/receiptly/compare/v0.16.1...v0.17.0) (2026-07-07)

### Features

* **api:** edit function + edit fields added ([5d0271a](https://github.com/Thoomaastb/receiptly/commit/5d0271aa351ed46f8b87406f67531d7607b00b76))

## [0.16.1](https://github.com/Thoomaastb/receiptly/compare/v0.16.0...v0.16.1) (2026-07-07)

### Bug Fixes

* **ui:** dark mode elements were as media queries were deleted ([c74d007](https://github.com/Thoomaastb/receiptly/commit/c74d007080ce6760faf64519c4d70361f2f5e0c1))

## [0.16.0](https://github.com/Thoomaastb/receiptly/compare/v0.15.9...v0.16.0) (2026-07-07)

### Features

* **auth:** login and register capabilities plus small first setup wizard at first startup ([8c76b4d](https://github.com/Thoomaastb/receiptly/commit/8c76b4d8c87a60c7210327e5928b611745370f0d))

## [0.15.9](https://github.com/Thoomaastb/receiptly/compare/v0.15.8...v0.15.9) (2026-07-07)

### Bug Fixes

* **services:** fixed 404 in buckets ([ffe35f2](https://github.com/Thoomaastb/receiptly/commit/ffe35f218e3ed25c8dbc44618293d2f2b8eaca04))

## [0.15.8](https://github.com/Thoomaastb/receiptly/compare/v0.15.7...v0.15.8) (2026-07-07)

### Bug Fixes

* **ui:** cleaned out the design ([d226b49](https://github.com/Thoomaastb/receiptly/commit/d226b49d8f431b9d150b02d6d7417c4e0e130495))

## [0.15.7](https://github.com/Thoomaastb/receiptly/compare/v0.15.6...v0.15.7) (2026-07-07)

### Bug Fixes

* **ui:** small design changes to represent the features ([4c92e77](https://github.com/Thoomaastb/receiptly/commit/4c92e775786f388592471c7640264c14eabf634f))

## [0.15.6](https://github.com/Thoomaastb/receiptly/compare/v0.15.5...v0.15.6) (2026-07-07)

### Bug Fixes

* **ui:** deleted animation because of unexpected behavior ([c7a27f3](https://github.com/Thoomaastb/receiptly/commit/c7a27f322b55125fae002a25398f5cc4e4af7559))

## [0.15.5](https://github.com/Thoomaastb/receiptly/compare/v0.15.4...v0.15.5) (2026-07-07)

### Bug Fixes

* **ui:** make outer layout a flex column so sidebar fills viewport height, sequence page transitions ([9a586cc](https://github.com/Thoomaastb/receiptly/commit/9a586cc4edf0c85b4c16e38c3aa20144490a0a92))

## [0.15.4](https://github.com/Thoomaastb/receiptly/compare/v0.15.3...v0.15.4) (2026-07-07)

### Bug Fixes

* **docker:** prevent browser caching of index.html so deploys are visible immediately ([13774f7](https://github.com/Thoomaastb/receiptly/commit/13774f77c36dedd5c2eb3ab1b1a5b45f55544dba))

## [0.15.3](https://github.com/Thoomaastb/receiptly/compare/v0.15.2...v0.15.3) (2026-07-07)

### Bug Fixes

* **docker:** correct GHCR fallback owner placeholder from thomas to thoomaastb ([c981607](https://github.com/Thoomaastb/receiptly/commit/c981607754fb5f5fd0417fac02e3d3d95eb98ea9))

## [0.15.2](https://github.com/Thoomaastb/receiptly/compare/v0.15.1...v0.15.2) (2026-07-07)

### Bug Fixes

* **ui:** replace receipt detail modal with content-switch view, seed demo receipt for testing ([aa39e86](https://github.com/Thoomaastb/receiptly/commit/aa39e8657035a3679b752e7b9bc43b85551d178f))

## [0.15.1](https://github.com/Thoomaastb/receiptly/compare/v0.15.0...v0.15.1) (2026-07-07)

### Bug Fixes

* **ui:** replace FLIP modal animation with spec-exact scale-fade, correct transition timings ([2f958ed](https://github.com/Thoomaastb/receiptly/commit/2f958ed684066fc54391b870f12b9a1c6209d07e))

## [0.15.0](https://github.com/Thoomaastb/receiptly/compare/v0.14.0...v0.15.0) (2026-07-07)

### Features

* **ui:** scaffold Capacitor integration with native camera capture for scan mode ([99c962e](https://github.com/Thoomaastb/receiptly/commit/99c962e9cea49d425c436875f9df49bb212c4915))

## [0.14.0](https://github.com/Thoomaastb/receiptly/compare/v0.13.3...v0.14.0) (2026-07-07)

### Features

* **buckets:** add personal bucket creation, visibility toggle, and bucket-filtered receipt view ([9947df7](https://github.com/Thoomaastb/receiptly/commit/9947df7a440be2c2b00acfa5d2722631fa97cebb))

## [0.13.3](https://github.com/Thoomaastb/receiptly/compare/v0.13.2...v0.13.3) (2026-07-04)

### Bug Fixes

* **services:** self-host tesseract OCR assets and fix camera capture accept attribute ([2be4ef5](https://github.com/Thoomaastb/receiptly/commit/2be4ef58c8e729da340c4517304480a435d9d8fc))

## [0.13.2](https://github.com/Thoomaastb/receiptly/compare/v0.13.1...v0.13.2) (2026-07-04)

### Bug Fixes

* **ui:** simplify page transition to pure fade, add missing webkit backdrop-filter prefix ([c4b3c00](https://github.com/Thoomaastb/receiptly/commit/c4b3c00a4e00125e94caf70c7e5fb3cd5e19ac99))

## [0.13.1](https://github.com/Thoomaastb/receiptly/compare/v0.13.0...v0.13.1) (2026-07-04)

### Bug Fixes

* **ui:** stack outgoing and incoming page content via CSS grid to prevent layout jump during transition ([27721f4](https://github.com/Thoomaastb/receiptly/commit/27721f4df2a1df32a1f69821e6397268685afe14))

## [0.13.0](https://github.com/Thoomaastb/receiptly/compare/v0.12.0...v0.13.0) (2026-07-04)

### Features

* **ui:** implement hifi redesign for app shell and home screen with self-hosted fonts ([a7f6d76](https://github.com/Thoomaastb/receiptly/commit/a7f6d767a0a558c5a439919bbd90040c2f57d264))

## [0.12.0](https://github.com/Thoomaastb/receiptly/compare/v0.11.0...v0.12.0) (2026-07-04)

### Features

* **ui:** replace native select elements with custom accessible dropdown component ([ba8c691](https://github.com/Thoomaastb/receiptly/commit/ba8c691f376c4b69e673f57f59b261f94382337a))

## [0.11.0](https://github.com/Thoomaastb/receiptly/compare/v0.10.0...v0.11.0) (2026-07-04)

### Features

* **ui:** add subtle crossfade transition on route changes ([0dd1098](https://github.com/Thoomaastb/receiptly/commit/0dd1098717577b747d70f7a4835942c824316c96))

## [0.10.0](https://github.com/Thoomaastb/receiptly/compare/v0.9.0...v0.10.0) (2026-07-04)

### Features

* **settings:** add admin-only AI provider selection with encrypted API key storage ([3faf8dc](https://github.com/Thoomaastb/receiptly/commit/3faf8dc775beaa6bf893f4497457a59ce57a0ec7))

## [0.9.0](https://github.com/Thoomaastb/receiptly/compare/v0.8.0...v0.9.0) (2026-07-04)

### Features

* **ui:** scan button opens device camera directly instead of waiting on mobile app ([1bea1b1](https://github.com/Thoomaastb/receiptly/commit/1bea1b11892437007132d4219848ce940003533c))

## [0.8.0](https://github.com/Thoomaastb/receiptly/compare/v0.7.0...v0.8.0) (2026-07-04)

### Features

* **ui:** open upload as on-the-fly modal instead of navigating to a new page ([6e60dbf](https://github.com/Thoomaastb/receiptly/commit/6e60dbfe910fc0348684012db4fc8500c11f3cb4))

## [0.7.0](https://github.com/Thoomaastb/receiptly/compare/v0.6.0...v0.7.0) (2026-07-04)

### Features

* **ui:** version fix ([467ea4c](https://github.com/Thoomaastb/receiptly/commit/467ea4ca8aa0ec6fb5a224798c1318883ceef973))

## [0.6.0](https://github.com/Thoomaastb/receiptly/compare/v0.5.4...v0.6.0) (2026-07-04)

### Features

* **ui:** fix broken nav icons, add logo mark, replace stale placeholder with live recent receipts ([b9a7369](https://github.com/Thoomaastb/receiptly/commit/b9a73692b3f00b89ea89b5d100167041b6b898dd))

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
