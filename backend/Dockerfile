FROM python:3.12-slim AS base

# von docker.yml aus dem Release-Git-Tag befüllt (siehe ARG APP_VERSION im Build-Step).
# Bewusst OHNE Default: ein leerer ENV-Wert zählt dank env_ignore_empty in app/config.py als
# "nicht gesetzt", erst dann greift dort der Fallback auf die gemountete VERSION-Datei. Ein
# Default wie "dev" hier würde die Env-Variable immer befüllen und den Fallback nie feuern
# lassen (pydantic-settings bevorzugt eine gesetzte Env-Variable immer vor dem Fallback).
ARG APP_VERSION=
ENV APP_VERSION=${APP_VERSION}

# rootless: dedizierter, unprivilegierter User
RUN groupadd -r receiptly && useradd -r -g receiptly -d /app -s /sbin/nologin receiptly

WORKDIR /app


# tesseract-ocr + deutsches Sprachpaket: OCR-Fallback für PDFs ohne Text-Ebene (siehe
# app/services/pdf_extraction.py), passend zum client-seitigen Tesseract (auch dort "deu",
# siehe frontend/src/lib/ocr/tesseract-provider.ts). Debian installiert das Binary nach
# /usr/bin/tesseract, das liegt bereits im Standard-PATH.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev curl tesseract-ocr tesseract-ocr-deu \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
RUN pip install --no-cache-dir -e .

COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./alembic.ini

# storage/originals + storage/thumbs vorab anlegen: die docker-compose-Volumes mounten
# hier erst zur Laufzeit hinein, und Docker kopiert beim allerersten (leeren) Mount den
# bestehenden Image-Inhalt inkl. Eigentümer in das Volume. Ohne das existiert der Pfad im
# Image nicht (nur Python legt ihn zur Laufzeit per mkdir an) — das Volume landet dann
# root-owned, und der non-root User "receiptly" kann nie hineinschreiben (jeder Upload
# schlägt mit PermissionError fehl).
RUN mkdir -p storage/originals storage/thumbs && chown -R receiptly:receiptly /app
USER receiptly

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
    CMD curl -f http://localhost:8000/api/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
