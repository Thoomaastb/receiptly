import enum
import uuid

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.mixins import TimestampMixin


class BucketType(str, enum.Enum):
    HOUSEHOLD = "household"
    PERSONAL = "personal"


class BucketVisibility(str, enum.Enum):
    TRANSPARENT = "transparent"
    PRIVATE = "private"


class BucketAccessLevel(str, enum.Enum):
    VIEW = "view"
    EDIT = "edit"


class Bucket(Base, TimestampMixin):
    """
    Geteilte oder private Beleglisten.
    Household-Bucket: is_default=True, immer 'transparent', nicht löschbar (Business-Regel,
    nicht DB-Constraint — Löschen/Umschalten wird in der Service-Schicht verhindert).
    """

    __tablename__ = "buckets"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    household_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("households.id", ondelete="CASCADE"), nullable=False
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[BucketType] = mapped_column(Enum(BucketType, name="bucket_type"), nullable=False)
    visibility: Mapped[BucketVisibility] = mapped_column(
        Enum(BucketVisibility, name="bucket_visibility"),
        nullable=False,
        default=BucketVisibility.TRANSPARENT,
    )
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    household: Mapped["Household"] = relationship(back_populates="buckets")  # noqa: F821
    owner: Mapped["User"] = relationship(back_populates="owned_buckets")  # noqa: F821
    access_grants: Mapped[list["BucketAccess"]] = relationship(
        back_populates="bucket", cascade="all, delete-orphan"
    )


class BucketAccess(Base):
    """Zusätzliche, granulare Freigaben auf einzelne Buckets (view/edit)."""

    __tablename__ = "bucket_access"

    bucket_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("buckets.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    access_level: Mapped[BucketAccessLevel] = mapped_column(
        Enum(BucketAccessLevel, name="bucket_access_level"), nullable=False
    )
    granted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    bucket: Mapped["Bucket"] = relationship(back_populates="access_grants")
