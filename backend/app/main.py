from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, health
from app.config import get_settings

settings = get_settings()

app = FastAPI(
    title="receiptly API",
    version="0.1.0-alpha.1",
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


app.include_router(health.router)
app.include_router(auth.router)
