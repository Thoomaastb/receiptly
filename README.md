# receiptly

**Selbst gehostetes, privacy-first DMS für Kassenbons, Rechnungen und Garantiebelege.**

[![Version](https://img.shields.io/badge/version-0.32.0-blue)](CHANGELOG.md)
[![Docker Build](https://github.com/Thoomaastb/receiptly/actions/workflows/docker.yml/badge.svg)](https://github.com/Thoomaastb/receiptly/actions/workflows/docker.yml)
[![Release](https://github.com/Thoomaastb/receiptly/actions/workflows/release.yml/badge.svg)](https://github.com/Thoomaastb/receiptly/actions/workflows/release.yml)

Das Originalbild eines Belegs verlässt das Gerät nie — nur der extrahierte Text geht an
den Server. Für den optionalen KI-Schritt (Struktur-Extraktion aus dem OCR-Text) gilt
dasselbe Prinzip eine Ebene tiefer: der Rohtext wird vor jedem Versand von
IBAN-/Kartennummern-artigen Mustern bereinigt, unabhängig davon ob der gewählte Provider
lokal (Ollama) oder extern (OpenAI/Anthropic/Google) läuft.

## Warum receiptly?

receiptly ist bewusst kein allgemeines Dokumentenmanagement-System wie paperless-ngx,
sondern ein eng fokussiertes Haushalts-Tool für genau eine Aufgabe: Kassenbons, Rechnungen
und Garantiebelege erfassen, durchsuchbar machen und Familien/WGs gemeinsam verwalten
lassen — mit einem Sicherheitsniveau, das für öffentlich erreichbare Finanzdaten gedacht
ist, nicht nachträglich angeflanscht.

## Features

**Erfassung**
- Foto- oder PDF-Upload, serverseitige OCR (Tesseract) — läuft immer, unabhängig von KI
- Optionale KI-Struktur-Extraktion (Ollama, OpenAI, Anthropic oder Google) mit PII-Redaction
  vor jedem Versand und SSRF-Schutz für selbst gehostete Ollama-Hosts
- Kategorie-spezifische Zusatzfelder (z.B. Kilometerstand bei "Tanken"), erweiterbar ohne
  neue Migration
- Mengen-Tracking für Artikel (z.B. 6×1,5l = 9l), fließt in die Gesamtsumme ein

**Organisation**
- Buckets zur freien Strukturierung, Kategorien mit Händler-Historie als Vorschlag
- Volltextsuche mit Typ-/Kategorie-Filtern, Sortierung nach Datum/Betrag
- Responsives Mosaik-Grid mit Thumbnails auf der Home-Übersicht, konfigurierbarer
  Kompakt-Modus

**Sicherheit**
- Passwort + optional TOTP/2FA und Passkeys/WebAuthn (auch als alleiniger Login-Faktor
  erzwingbar)
- Rate-Limiting gegen Brute-Force auf Login/Reset/2FA-Verifizierung
- Audit-Log für sicherheitsrelevante Ereignisse (Logins, Passwortänderungen,
  Session-Beendigungen)
- Konfigurierbare Sicherheitsrichtlinien pro Haushalt, Sitzungsverwaltung mit
  Fern-Abmeldung
- Self-Service-Passwort-Reset per E-Mail (SMTP im Admin-Bereich konfigurierbar)

**Betrieb**
- Mehrbenutzer-Haushalte statt Einzelaccounts
- Dark Mode
- Ein einziges Docker-Image (Backend + statisch ausgeliefertes Frontend), rootless,
  mehrarch (`ghcr.io`)
- Mobile Wrapper (iOS/Android) über Capacitor auf Basis desselben Web-Builds — keine
  zweite Codebasis

## Stack

| Schicht | Technologie |
|---|---|
| Frontend | SvelteKit + TypeScript + Tailwind CSS |
| Backend | FastAPI + SQLAlchemy 2.0 + asyncpg |
| Datenbank | PostgreSQL 16 |
| Cache/Queue | Redis |
| Infrastruktur | Docker (rootless) + Nginx + Pangolin/Newt |
| Mobile | Capacitor (iOS/Android) auf demselben SvelteKit-Build |

## Schnellstart

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

Zugriff läuft standardmäßig ausschließlich über Pangolin/Newt via `remote` — Host-Ports
sind daher in `docker-compose.yml` auskommentiert (nicht entfernt). Für lokales Testen
ohne Pangolin einfach die `#` vor der `ports:`-Zeile bei `app` entfernen.

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

### Konfiguration

Alle Umgebungsvariablen inkl. Erklärung stehen in `.env.example`. Die wichtigsten
optionalen Bausteine:

- **KI-Struktur-Extraktion** — ohne `OLLAMA_HOST`/`AI_HOST` bleibt es bei reiner OCR ohne
  KI-Aufruf; ist einer der beiden gesetzt, wird der Provider server-weit erzwungen
  (Haushalts-Settings-UI wird read-only), sonst frei pro Haushalt konfigurierbar.
- **E-Mail (Passwort-Reset)** — ohne `SMTP_HOST` bleibt der Versand aus (Antwort bleibt
  bewusst immer erfolgreich, verhindert User-Enumeration).

## Backup & Restore

**Was gesichert werden muss:**

Drei benannte Docker-Volumes (aus `docker-compose.yml`) + die `.env`-Datei:

- `db-data` — PostgreSQL-Datenbankverzeichnis
- `storage-originals` — hochgeladene Originalbilder und PDFs
- `storage-thumbs` — generierte Thumbnails (optional, siehe unten)
- `.env` — Umgebungskonfiguration, **kritisch: `ENCRYPTION_KEY`, `SESSION_SECRET`, `POSTGRES_PASSWORD`, `REDIS_PASSWORD`**

**Warum `.env` zusammen mit der DB sichern:** Der `ENCRYPTION_KEY` (Fernet, siehe `backend/app/services/crypto.py`) verschlüsselt sicherheitskritische Daten in der Postgres-DB:

- TOTP-Secrets für 2FA (`backend/app/models/user.py`)
- KI-Provider-API-Keys (`backend/app/api/settings.py`)
- SMTP-Passwort (`backend/app/api/smtp_settings.py`)

Ein reiner DB-Dump ohne korrespondierenden `ENCRYPTION_KEY` ist wertlos für diese Felder — nach einem Restore mit anderem/fehlendem Key sind TOTP-Secrets dauerhaft nicht entschlüsselbar (sperrt ggf. Admin-Accounts aus, da TOTP für Admins Pflicht ist) und AI-/SMTP-Zugangsdaten müssten neu hinterlegt werden. **Beide müssen immer zusammen gesichert werden.**

**Was optional ist:**

- `storage-thumbs` — kann bei Bedarf weggelassen werden. Thumbnails werden per Lazy-Backfill aus `storage-originals` neu generiert, wenn sie fehlen (`GET /receipts/{id}/thumb`). Datenverlust entsteht dadurch keiner, nur ein einmaliger Performance-Hit beim ersten Zugriff je Beleg nach dem Restore.

**Was NICHT gesichert werden muss:**

- Redis — hat kein Volume in `docker-compose.yml`. Rein Cache/Session-State/Rate-Limit-Counter, laut Architektur bewusst flüchtig. Kein Datenverlust-Risiko bei Neustart.

### Postgres-Dump

Konsistenter Dump im Binary-Format (`.dump`), empfohlen für Restores auf derselben oder neueren PostgreSQL-Version:

```bash
docker compose exec db pg_dump -U receiptly -Fc receiptly > backup.dump
```

`-U receiptly` entspricht `POSTGRES_USER` aus `.env`, `-Fc` erzeugt Custom-Format (kompakt, schneller restore als SQL-Text).

Zur Kontrolle: die Datei sollte ca. einige MB groß sein (abhängig von OCR-Text-Umfang + Upload-Menge). Manuell testen:

```bash
docker compose exec db pg_restore -U receiptly -d receiptly --list backup.dump | head -20
```

### Volume-Backup

Über einen Wegwerf-Container mit `tar`:

```bash
# storage-originals
docker run --rm -v receiptly_storage-originals:/data -v $(pwd):/backup \
  alpine tar czf /backup/storage-originals.tar.gz -C /data .

# storage-thumbs (optional)
docker run --rm -v receiptly_storage-thumbs:/data -v $(pwd):/backup \
  alpine tar czf /backup/storage-thumbs.tar.gz -C /data .
```

Volume-Namen bekommen von Docker Compose automatisch den **Projektnamen** vorangestellt — das ist NICHT `INSTANCE_NAME` (das steuert nur `container_name`), sondern der Verzeichnisname, in dem `docker-compose.yml` liegt, bzw. `COMPOSE_PROJECT_NAME`/`-p`, falls explizit gesetzt. Bei einem Standard-Checkout in einem `receiptly`-Verzeichnis also `receiptly_storage-originals`, `receiptly_storage-thumbs` — bei mehreren Instanzen auf demselben Host (z.B. Test-/Staging-Stack in einem anders benannten Verzeichnis) unterscheidet sich der Präfix entsprechend. Vor dem Backup/Restore immer mit `docker volume ls` gegenchecken, welcher Präfix zur gewünschten Instanz gehört.

### Restore-Ablauf

**1. Volumes wiederherstellen:**

```bash
# originals
docker run --rm -v receiptly_storage-originals:/data -v $(pwd):/backup \
  alpine tar xzf /backup/storage-originals.tar.gz -C /data

# thumbs (falls Backup vorhanden)
docker run --rm -v receiptly_storage-thumbs:/data -v $(pwd):/backup \
  alpine tar xzf /backup/storage-thumbs.tar.gz -C /data
```

**2. `.env`-Datei mit gesicherten Secrets einspielen** (mit demselben `ENCRYPTION_KEY`, `SESSION_SECRET` etc. wie zum Zeitpunkt des Backups).

**3. Nur `db` + `redis` starten (noch NICHT `app`):**

```bash
docker compose up -d db redis
```

Wichtig: `app` darf hier noch nicht laufen — sonst hält die App bereits Verbindungen zur DB, und `DROP DATABASE` im nächsten Schritt schlägt mit "database is being accessed by other users" fehl.

**4. Datenbank-Dump einspielen:**

```bash
# Ggf. bestehende DB löschen (nur bei komplettem Restore empfohlen)
docker compose exec db psql -U receiptly -d postgres -c "DROP DATABASE IF EXISTS receiptly;"
docker compose exec db psql -U receiptly -d postgres -c "CREATE DATABASE receiptly;"

# Dump wiederherstellen
cat backup.dump | docker compose exec -T db pg_restore -U receiptly -d receiptly
```

**5. App starten:**

```bash
docker compose up -d app
```

**6. Ggf. Schema-Migrationen catch-up (falls das Backup älter als die aktuelle App-Version ist):**

```bash
docker compose exec app alembic upgrade head
```

**7. Bestätigung:**

- Login testen — TOTP/Passkeys sollten funktionieren (falls der `ENCRYPTION_KEY` korrekt ist).
- Ein Beleg mit Thumbnail aufrufen — sollte ohne 500-Fehler laden.

## Versionierung & Contributing

Conventional Commits, durchgesetzt via `commitlint.config.js`, gesteuert über
`.releaserc.json` (`semantic-release`). Schema: `v.MAJOR.MINOR.PATCH`.

```
feat(scope): description   → MINOR
fix(scope): description    → PATCH
feat!: description         → MAJOR — reserviert für das stabile v1.0.0-Release
chore/docs/ci/test         → kein Release
```

Gültige Scopes stehen in `commitlint.config.js` — vor dem Commit prüfen statt raten, die
Liste wächst mit dem Projekt.

## Status

`v0.32.0` — Security Hardening (2FA, Passkeys/WebAuthn, Rate-Limiting, Audit-Log)
abgeschlossen. Siehe [CHANGELOG.md](CHANGELOG.md) für die vollständige Versionshistorie.
Vor `v1.0.0` ist nichts stabil — Architektur und Reihenfolge der Minor-Versionen können
sich noch ändern.

Vollständiges Konzept, Architektur, Datenmodell und Backlog: siehe Notion (Page "receiptly").

## Lizenz

[GNU AGPL-3.0](LICENSE) mit einer Zusatzklausel nach §7(b): Wer eine Kopie oder
modifizierte Version betreibt (auch als Netzwerkdienst), muss die
Urheber-Attribution sowohl im Quellcode als auch sichtbar in der Oberfläche der
Anwendung erhalten. Details siehe [LICENSE](LICENSE).
