import uuid

from sqlalchemy import ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.mixins import TimestampMixin


class Item(Base, TimestampMixin):
    __tablename__ = "items"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    receipt_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("receipts.id", ondelete="CASCADE"), nullable=False
    )
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="SET NULL"), nullable=True
    )
    raw_name: Mapped[str] = mapped_column(String(255), nullable=False)
    quantity: Mapped[float] = mapped_column(Numeric(10, 3), nullable=False, default=1)
    unit: Mapped[str | None] = mapped_column(String(20), nullable=True)
    unit_price: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    total_price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)

    # Anzahl (quantity) vs. Menge pro Einheit: "6x Wasser à 1,5l" ist quantity=6,
    # pack_amount=1.5, pack_unit="l" — ergibt 9l Gesamtmenge. Getrennt von quantity/unit,
    # weil quantity/unit bereits die Zähl-Einheit für den Preis abbildet (z.B. "1 Stk"),
    # pack_amount/pack_unit aber die Füllmenge je Stück für Preisintelligenz (Preis pro
    # Liter/kg) — beides zusammen ergäbe sonst eine widersprüchliche Doppelbedeutung.
    pack_amount: Mapped[float | None] = mapped_column(Numeric(10, 3), nullable=True)
    pack_unit: Mapped[str | None] = mapped_column(String(20), nullable=True)

    receipt: Mapped["Receipt"] = relationship(back_populates="items")  # noqa: F821
