import enum
import uuid
from datetime import date

from sqlalchemy import Boolean, Date, Enum, ForeignKey, Numeric, SmallInteger, String, Text
from sqlalchemy.dialects.postgresql import UUID
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

    receipt_date: Mapped[date] = mapped_column(Date, nullable=False)
    total_amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="EUR")

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
        Enum(ReceiptStatus, name="receipt_status"), nullable=False, default=ReceiptStatus.PENDING
    )

    items: Mapped[list["Item"]] = relationship(  # noqa: F821
        back_populates="receipt", cascade="all, delete-orphan"
    )
