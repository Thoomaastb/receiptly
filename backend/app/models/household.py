import uuid

from sqlalchemy import String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.mixins import TimestampMixin


class Household(Base, TimestampMixin):
    """Ein Haushalt — Wurzel-Entität für Multi-User-Modell (kein Multi-Tenant-SaaS)."""

    __tablename__ = "households"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    users: Mapped[list["User"]] = relationship(back_populates="household")  # noqa: F821
    buckets: Mapped[list["Bucket"]] = relationship(back_populates="household")  # noqa: F821
