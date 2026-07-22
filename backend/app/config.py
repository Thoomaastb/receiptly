from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _fallback_app_version() -> str:
    """
    Greift nur, wenn kein APP_VERSION-Env gesetzt ist (Prod-Images setzen es per
    Docker-Build-Arg aus dem Release-Tag, siehe Dockerfile/docker.yml). Für den lokalen
    Dev-Container liest das die Repo-Root-VERSION-Datei, die docker-compose.dev.yml nach
    /app/VERSION mountet — sonst bliebe die Versionsanzeige im Dev-Setup immer "dev".
    """
    version_file = Path(__file__).resolve().parent.parent / "VERSION"
    if version_file.is_file():
        return version_file.read_text().strip()
    return "dev"


class Settings(BaseSettings):
    # env_ignore_empty: das Dockerfile setzt ENV APP_VERSION immer (ARG-Default ""), damit
    # ein leerer String im Dev-Image für pydantic-settings als "nicht gesetzt" zählt und der
    # default_factory-Fallback von app_version greift — ohne das würde eine leere Env-Variable
    # sonst Vorrang vor dem Fallback bekommen und die VERSION-Datei nie gelesen.
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", env_ignore_empty=True)

    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    cors_origins: str = "http://localhost:5173"

    app_version: str = Field(default_factory=_fallback_app_version)

    database_url: str
    redis_url: str = "redis://redis:6379/0"

    session_secret: str
    session_cookie_name: str = "receiptly_session"
    session_max_age_seconds: int = 1209600  # 14 Tage

    encryption_key: str  # Fernet-Key (Fernet.generate_key()), separat von session_secret rotierbar

    # Server-weite KI-Provider-Konfiguration — 3-stufige Prioritätskette, siehe
    # app/services/ai_provider_resolution.py: ollama_host > ai_host/ai_key >
    # Haushalts-AISettings > None (nur lokale Texterfassung, keine KI-Strukturierung).
    ollama_host: str | None = None  # z.B. http://ollama:11434 — erzwingt Ollama server-weit
    ollama_model: str | None = None  # z.B. llama3.1 — Modell-Override, nur mit ollama_host relevant
    ai_host: str | None = None  # "openai" | "anthropic" | "google" — erzwingt diesen Provider
    ai_key: str | None = None  # zugehöriger API-Key, direkt aus .env, nie in der DB
    ai_extraction_timeout_seconds: float = 25.0
    ai_extraction_max_ocr_chars: int = 4000

    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_email: str = "noreply@receiptly.local"
    # "starttls" (Port 587, Klartext-Verbindung mit TLS-Upgrade) oder "ssl" (Port 465,
    # TLS von Anfang an) — je nach Provider nur eine der beiden Varianten unterstützt,
    # daher explizit statt aus der Portnummer zu raten. Alles außer "ssl" läuft als starttls.
    smtp_encryption: str = "starttls"
    public_app_url: str = "http://localhost:5173"

    # Security-Hardening Phase 3 (Passkeys/WebAuthn, siehe concepts/security-hardening.md
    # Abschnitt 4.3). WebAuthn verlangt eine reine Domain als RP-ID (kein Schema/Port) —
    # ohne expliziten Override wird sie aus public_app_url abgeleitet (Ein-Domain-
    # Deployment braucht i.d.R. keinen separat zu pflegenden zweiten Wert). Wechselt die
    # Domain, werden bestehende Passkeys ungültig (Deployment-Fallstrick, siehe Konzept).
    webauthn_rp_id: str | None = None
    webauthn_rp_name: str = "receiptly"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def webauthn_rp_id_resolved(self) -> str:
        if self.webauthn_rp_id:
            return self.webauthn_rp_id
        return urlparse(self.public_app_url).hostname or "localhost"


@lru_cache
def get_settings() -> Settings:
    return Settings()
