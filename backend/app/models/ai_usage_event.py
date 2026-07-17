import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Integer, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AIUsageEvent(Base):
    """
    Ein Log-Eintrag pro KI-Extraktions-Call — global/systemweit, bewusst ohne
    household_id (Produktentscheidung: der Admin-Zähler zeigt kumulierten Token-
    Verbrauch/Kosten über die gesamte Instanz, nicht pro Haushalt). Zeilen sind
    unveränderlich (nur created_at, kein updated_at) — es gibt kein nachträgliches
    Editieren eines bereits geloggten API-Calls.

    provider ist bewusst ein freier String statt AIProviderType-Enum: ein Log-Eintrag
    soll auch dann noch lesbar sein, wenn sich die unterstützten Provider-Werte später
    ändern (Enum-Alter auf einer Log-Tabelle ist unnötig riskant, siehe Migration 0008).
    Die Werte entsprechen aktuell AIProviderType (app/models/ai_settings.py):
    "ollama" | "openai" | "anthropic" | "google".
    """

    __tablename__ = "ai_usage_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    model: Mapped[str] = mapped_column(String(255), nullable=False)

    prompt_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    completion_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False)

    # Nullable: Kosten sind unbekannt bei einem nicht erkannten/benutzerdefinierten
    # Modellnamen (kein Preis-Mapping vorhanden) — dann lieber NULL als ein falscher Wert.
    estimated_cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)

    # Bewusst kein TimestampMixin (app/models/mixins.py) — die Mixin-Variante hat keinen
    # Index, hier aber gewollt (Zeitraum-Filter, siehe Migration 0009). Ein index=True
    # auf dem Mixin selbst hätte receipts/users ungefragt mit-indiziert.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
