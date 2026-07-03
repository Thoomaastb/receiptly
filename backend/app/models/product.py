import uuid

from sqlalchemy import Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.mixins import TimestampMixin


class Product(Base, TimestampMixin):
    """Normalisierter Artikel. Basis für Preisverlauf (price_history folgt in v0.1.0-alpha.3)."""

    __tablename__ = "products"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    normalized_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    brand: Mapped[str | None] = mapped_column(String(255), nullable=True)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    base_unit: Mapped[str | None] = mapped_column(String(20), nullable=True)
    base_quantity: Mapped[float | None] = mapped_column(Numeric(10, 3), nullable=True)
