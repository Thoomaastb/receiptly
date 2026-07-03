# --- Stage 1: Frontend statisch bauen ---
FROM node:20-slim AS frontend-build
WORKDIR /frontend
COPY frontend/package.json ./
RUN npm install
COPY frontend .
RUN npm run build

# --- Stage 2: Backend + ausgeliefertes Frontend, ein Prozess ---
FROM python:3.12-slim AS runtime

RUN groupadd -r receiptly && useradd -r -g receiptly -d /app -s /sbin/nologin receiptly

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

COPY backend/pyproject.toml ./
RUN pip install --no-cache-dir -e .

COPY backend/app ./app
COPY backend/alembic ./alembic
COPY backend/alembic.ini ./alembic.ini

# Statischer Frontend-Build landet dort, wo app/main.py ihn erwartet (app/../static)
COPY --from=frontend-build /frontend/build ./static

RUN chown -R receiptly:receiptly /app
USER receiptly

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
    CMD curl -f http://localhost:8000/api/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
