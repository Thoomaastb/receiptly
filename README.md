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

Noch nicht final festgelegt (Pre-`v1.0.0`).
