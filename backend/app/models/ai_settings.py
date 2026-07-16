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
    GOOGLE = "google"


class AISettings(Base, UpdatableTimestampMixin):
    """
    Haushaltsweite KI-Provider-Konfiguration — die unterste Stufe einer 3-stufigen
    Prioritätskette (siehe app/services/ai_provider_resolution.py): server-weiter
    OLLAMA_HOST-Fallback > server-weiter AI_HOST-Fallback > diese Haushalts-Einstellung.
    provider=None heißt explizit "kein Haushalts-Provider konfiguriert" (dann ggf. nur
    lokale Texterfassung ohne KI-Strukturierung).

    OLLAMA bezeichnet hier die haushaltseigene Lokal-Instanz (eigener Host in
    endpoint_url + Modell in model_name, kein Key) — zu unterscheiden vom server-weiten
    OLLAMA_HOST/OLLAMA_MODEL-Fallback in app/config.py, der Vorrang vor dieser Ebene hat.
    Alle anderen Provider sind laut Security-&-Privacy-Konzept explizites Opt-in — die
    UI-Warnung dafür ist Pflicht, nicht optional.
    """

    __tablename__ = "ai_settings"

    household_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("households.id", ondelete="CASCADE"), primary_key=True
    )
    provider: Mapped[AIProviderType | None] = mapped_column(
        Enum(AIProviderType, name="ai_provider_type", values_callable=lambda e: [m.value for m in e]),
        nullable=True,
    )
    # Nie im Klartext — nur über app.services.crypto ver-/entschlüsselt
    encrypted_api_key: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    # Nur bei provider=OLLAMA relevant (haushaltseigene Instanz), sonst None
    endpoint_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    # Bei Ollama: lokales Modell auf dem eigenen Host. Bei Cloud-Providern: optionaler
    # Override der Hardcoded-Defaults (z.B. gpt-4o-mini).
    model_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
