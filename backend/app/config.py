from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    cors_origins: str = "http://localhost:5173"

    database_url: str
    redis_url: str = "redis://redis:6379/0"

    session_secret: str
    session_cookie_name: str = "receiptly_session"
    session_max_age_seconds: int = 1209600  # 14 Tage

    ai_provider: str = "ollama"
    ollama_base_url: str = "http://ollama:11434"
    external_ai_api_key: str | None = None

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
