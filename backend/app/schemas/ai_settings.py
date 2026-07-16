from pydantic import BaseModel, Field


class AISettingsResponse(BaseModel):
    provider: str | None
    has_api_key: bool
    endpoint_url: str | None
    model_name: str | None
    # True, wenn eine server-weite .env-Konfiguration (OLLAMA_HOST/AI_HOST) den Provider
    # erzwingt — siehe app/services/ai_provider_resolution.py. Der gespeicherte
    # Haushalts-Wert bleibt dann zwar in der DB, ist aber ohne Wirkung.
    locked_by_server: bool
    # Nur gesetzt, wenn locked_by_server=True — der tatsächlich wirksame Wert für die
    # read-only-Anzeige im Frontend, unabhängig vom gespeicherten Haushalts-Wert.
    effective_provider: str | None = None
    effective_model: str | None = None


class AISettingsUpdate(BaseModel):
    provider: str = Field(pattern="^(ollama|openai|anthropic|google)$")
    # Optional: nur mitschicken, wenn ein neuer Key gesetzt/geändert werden soll.
    # Leer lassen, um den bestehenden Key unverändert zu lassen.
    api_key: str | None = Field(default=None, min_length=1, max_length=512)
    # Nur bei provider="ollama" relevant (haushaltseigene Lokal-Instanz), z.B. "http://ollama:11434"
    endpoint_url: str | None = Field(default=None, max_length=512)
    # Bei Ollama: lokales Modell auf dem eigenen Host. Bei Cloud-Providern: optionaler
    # Override des Hardcoded-Defaults (z.B. "gpt-4o-mini").
    model_name: str | None = Field(default=None, max_length=255)
