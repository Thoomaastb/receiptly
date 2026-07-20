import enum
import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Numeric,
    SmallInteger,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.mixins import UpdatableTimestampMixin


class ReceiptStatus(str, enum.Enum):
    PENDING = "pending"  # hochgeladen, OCR/KI läuft noch
    PROCESSED = "processed"
    NEEDS_REVIEW = "needs_review"  # z.B. Duplikatsverdacht, niedrige OCR-Konfidenz


class Receipt(Base, UpdatableTimestampMixin):
    """
    Ein Beleg. `bucket_id` bestimmt Sichtbarkeit/Zugehörigkeit (ersetzt direkte household_id-Ref).
    Duplikatserkennung wirkt bucket-übergreifend im ganzen Haushalt (siehe Service-Schicht).
    """

    __tablename__ = "receipts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    merchant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("merchants.id", ondelete="SET NULL"), nullable=True
    )
    bucket_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("buckets.id", ondelete="CASCADE"), nullable=False
    )

    receipt_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    total_amount: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="EUR")

    # Anpassungszeilen, die die KI-Struktur-Extraktion nicht als items[] abbilden kann
    # (Item.total_price verlangt >= 0, siehe app/schemas/receipt.py) — bewusst dedizierte
    # Spalten statt Pseudo-Artikel. Alle drei nullable: NULL = "nicht erfasst", nicht "0".
    # tax_amount ist nur die *separat ausgewiesene* Steuer, sofern nicht bereits in
    # total_amount enthalten (siehe Migration 0011). Befüllung/Abgleichslogik folgt
    # separat, ist bewusst nicht Teil dieser Spalten-Definition.
    shipping_cost: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    discount_amount: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    tax_amount: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)

    ocr_raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    ocr_confidence: Mapped[float | None] = mapped_column(Numeric(4, 3), nullable=True)

    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    thumb_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    # Duplikatserkennung (zweistufig, siehe Produkt-Konzept)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    fuzzy_signature: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    # Dokumenttyp-statt-Merchant-Logik
    is_high_value: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    warranty_months: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    warranty_expires_at: Mapped[date | None] = mapped_column(Date, nullable=True)

    status: Mapped[ReceiptStatus] = mapped_column(
        Enum(ReceiptStatus, name="receipt_status", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=ReceiptStatus.PENDING,
    )

    # Kategorie-spezifische Zusatzfelder (z.B. Kilometerstand bei "Tanken"), Struktur pro
    # Kategorie in frontend/src/lib/categories.ts definiert. Bewusst JSONB statt eigener
    # Spalte pro Feld — neue Kategorie-Felder brauchen so keine eigene Migration.
    custom_fields: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # KI-Struktur-Extraktions-Vorschläge (siehe app/services/ai_extraction.py) — bewusst
    # getrennt von merchant_id/category, bis der Nutzer den Vorschlag bestätigt (KI legt
    # nie selbst einen Merchant an).
    ai_suggested_merchant_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ai_suggested_category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # Menschenlesbarer Grund bei needs_review (z.B. "Kein KI-Anbieter konfiguriert")
    ai_extraction_note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # Markiert "Extraktion wurde versucht" (Erfolg oder Fehlschlag), unabhängig vom Ergebnis
    ai_extracted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    items: Mapped[list["Item"]] = relationship(  # noqa: F821
        back_populates="receipt", cascade="all, delete-orphan"
    )
    merchant: Mapped["Merchant | None"] = relationship()  # noqa: F821

    @property
    def merchant_name(self) -> str | None:
        return self.merchant.name if self.merchant else None

    @property
    def category(self) -> str | None:
        return self.merchant.category if self.merchant else None

    @property
    def item_count(self) -> int:
        return len(self.items)
