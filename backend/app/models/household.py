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

    # passive_deletes=True (Konto-Löschung/DSGVO, siehe app/scripts/account_deletion_teardown.py
    # ::_dissolve_household — der erste Ort im Projekt, der ein Household per ORM löscht):
    # ohne das versucht SQLAlchemys Unit-of-Work beim Löschen eines Household, users.
    # household_id/buckets.household_id VORHER selbst auf NULL zu setzen (Default-Verhalten
    # für Relationships ohne cascade="all, delete-orphan"), was an der NOT-NULL-Constraint
    # scheitert — die DB-seitige ON DELETE CASCADE (siehe Migrationen) übernimmt das stattdessen
    # vollständig, sobald die ORM sich hier nicht mehr einmischt.
    users: Mapped[list["User"]] = relationship(  # noqa: F821
        back_populates="household", passive_deletes=True
    )
    buckets: Mapped[list["Bucket"]] = relationship(  # noqa: F821
        back_populates="household", passive_deletes=True
    )
