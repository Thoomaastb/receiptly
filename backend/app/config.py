from functools import lru_cache
from pathlib import Path

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

    ai_provider: str = "ollama"
    ollama_base_url: str = "http://ollama:11434"
    external_ai_api_key: str | None = None

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

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
