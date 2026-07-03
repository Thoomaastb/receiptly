# Patch 01 — auf v0.1.0-alpha.1 anwenden

Dieses Archiv enthält NUR neue/geänderte Dateien, keinen kompletten Baum.
Kopiere die Dateien 1:1 in deine lokale receiptly-Kopie (gleiche relative Pfade).

## Neu
- .github/workflows/release.yml
- .github/workflows/docker.yml
- .github/dependabot.yml

## Geändert (ersetzen)
- .releaserc.json       — VERSION jetzt als Git-Asset
- docker-compose.yml    — Ports 8000 (backend) + 3000 (frontend) ergänzt
- backend/pyproject.toml — [build-system] + email-validator ergänzt
- CHANGELOG.md          — Nachlieferung dokumentiert

## Commits (zum manuellen Anwenden in dieser Reihenfolge)
fix(docker): expose backend and frontend ports for local testing
fix(services): add missing build-system and email-validator to backend packaging
fix(release): track VERSION file as semantic-release git asset
ci(ci): add semantic-release and multi-arch docker workflows, fix dependabot ecosystems

→ Keiner davon ist ein `feat`, also kein Minor-Release. Der PATCH-Level-Bump passiert erst,
wenn du diese Commits tatsächlich auf `main` pushst und die Release-Pipeline läuft.
