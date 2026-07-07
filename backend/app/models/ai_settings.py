import enum
import uuid

from sqlalchemy import Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.mixins import UpdatableTimestampMixin


class AIProviderType(str, enum.Enum):
    OLLAMA = "ollama"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    CUSTOM = "custom"


class AISettings(Base, UpdatableTimestampMixin):
    """
    Haushaltsweite KI-Provider-Konfiguration. Ollama ist der Default und braucht
    keinen Key (läuft lokal). Alle anderen Provider sind laut Security-&-Privacy-Konzept
    explizites Opt-in — die UI-Warnung dafür ist Pflicht, nicht optional.
    """

    __tablename__ = "ai_settings"

    household_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("households.id", ondelete="CASCADE"), primary_key=True
    )
    provider: Mapped[AIProviderType] = mapped_column(
        Enum(AIProviderType, name="ai_provider_type", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=AIProviderType.OLLAMA,
    )
    # Nie im Klartext — nur über app.services.crypto ver-/entschlüsselt
    encrypted_api_key: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    custom_endpoint: Mapped[str | None] = mapped_column(String(512), nullable=True)
