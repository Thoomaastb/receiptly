import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.mixins import TimestampMixin


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    USER = "user"


class User(Base, TimestampMixin):
    """Ein Nutzer innerhalb eines Haushalts. RBAC über `role`, unabhängig von Bucket-Sichtbarkeit."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=UserRole.USER,
    )
    household_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("households.id", ondelete="CASCADE"), nullable=False
    )

    # v0.3.0 Security Hardening (Spalten bereits angelegt, Logik folgt später)
    totp_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # String(255): Fernet-Ciphertext ist länger als das Klartext-Base32-Secret von pyotp
    totp_secret: Mapped[str | None] = mapped_column(String(255), nullable=True)

    last_login: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Benachrichtigungssystem: Liste der Notification-`type`-Werte, für die dieser User
    # zusätzlich zur In-App-Zeile eine E-Mail erhalten möchte (Opt-in pro Typ, Default
    # leer = konservativ, siehe Migration 0019).
    notification_email_opt_ins: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, server_default="[]"
    )

    household: Mapped["Household"] = relationship(back_populates="users")  # noqa: F821
    owned_buckets: Mapped[list["Bucket"]] = relationship(back_populates="owner")  # noqa: F821
