from pydantic import BaseModel, Field


class AISettingsResponse(BaseModel):
    provider: str
    has_api_key: bool
    custom_endpoint: str | None


class AISettingsUpdate(BaseModel):
    provider: str = Field(pattern="^(ollama|openai|anthropic|custom)$")
    # Optional: nur mitschicken, wenn ein neuer Key gesetzt/geändert werden soll.
    # Leer lassen, um den bestehenden Key unverändert zu lassen.
    api_key: str | None = Field(default=None, min_length=1, max_length=512)
    custom_endpoint: str | None = Field(default=None, max_length=512)
