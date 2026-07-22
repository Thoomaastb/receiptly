from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api import (
    audit_log,
    auth,
    buckets,
    health,
    receipts,
    security_settings,
    settings as settings_router,
    smtp_settings,
    totp,
)
from app.config import get_settings

settings = get_settings()

app = FastAPI(
    title="receiptly API",
    version=settings.app_version,
    description="Privacy-first Belege-DMS — Originalbild verlässt das Gerät nie.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,  # notwendig für HTTP-Only Session-Cookies
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def security_headers(request, call_next):
    """Ring 2 — Strikte HTTP-Security-Header, siehe Security & Privacy Konzept."""
    response = await call_next(request)
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    if settings.app_env != "development":
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
        response.headers["Content-Security-Policy"] = "default-src 'self'"
    return response


# Alle API-Routen unter /api — notwendig, seit Frontend + Backend im selben Origin
# (Single-Container-Image) laufen und sich sonst mit den SvelteKit-Routen überschneiden.
app.include_router(health.router, prefix="/api")
app.include_router(auth.router, prefix="/api")
app.include_router(totp.router, prefix="/api")
app.include_router(receipts.router, prefix="/api")
app.include_router(buckets.router, prefix="/api")
app.include_router(settings_router.router, prefix="/api")
app.include_router(security_settings.router, prefix="/api")
app.include_router(smtp_settings.router, prefix="/api")
app.include_router(audit_log.router, prefix="/api")


# Statisches Frontend (adapter-static-Build) ausliefern. Der Ordner existiert nur im
# Produktions-Image (siehe Root-Dockerfile) — im reinen Backend-Container (lokale
# Entwicklung, docker-compose.dev.yml) fehlt er, dann bleibt dieser Block wirkungslos.
_frontend_dist = Path(__file__).resolve().parent.parent / "static"

if _frontend_dist.is_dir():
    app.mount("/_app", StaticFiles(directory=_frontend_dist / "_app"), name="frontend-assets")

    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str, request: Request):
        """
        SPA-Fallback: existiert die angeforderte Datei im Static-Build, wird sie
        ausgeliefert, sonst index.html — SvelteKits Client-Router übernimmt danach
        das Routing (z.B. /receipts, /upload nach einem harten Reload).
        """
        candidate = _frontend_dist / full_path
        if candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(_frontend_dist / "index.html")
