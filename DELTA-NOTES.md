# Delta 02 — Scan & Upload (auf receiptly-v0.1.0-alpha.1.zip anwenden)

Nur neue/geänderte Dateien. In deine lokale Kopie kopieren, gleiche relative Pfade,
alles überschreiben.

## Neu
- backend/app/services/storage.py
- backend/app/services/__init__.py
- backend/app/api/receipts.py
- backend/app/schemas/receipt.py
- backend/alembic/versions/0002_receipts_nullable_date_amount.py
- frontend/src/lib/ocr/types.ts
- frontend/src/lib/ocr/tesseract-provider.ts
- frontend/src/lib/ocr/native-provider.ts
- frontend/src/lib/ocr/index.ts
- frontend/src/routes/upload/+page.svelte

## Geändert (ersetzen)
- backend/app/main.py — receipts-Router eingehängt
- backend/app/models/receipt.py — receipt_date/total_amount nullable
- frontend/src/routes/+page.svelte — Hero-Buttons verlinken auf /upload
- frontend/package.json — tesseract.js als Dependency
- frontend/vite.config.ts — /api-Dev-Proxy zum Backend
- CHANGELOG.md

## Nach dem Einspielen
docker compose exec backend alembic upgrade head    # Migration 0002 anwenden
cd frontend && npm install                          # tesseract.js nachziehen

## Commit-Message (reine Zeile, kein git-Wrapper)
feat(pim): add receipt upload flow with client-side OCR and file storage service

## Bekannte offene Lücke
bucket_id ist im Upload-Formular noch ein Platzhalter (leerer String) — echte Buckets
kommen mit dem nächsten Paket. Bis dahin schlägt der Upload ohne gültige bucket_id fehl.
