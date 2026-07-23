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

    # Konto löschen (DSGVO, v0.36.0): 14-Tage-Karenzzeit. NULL = aktiv, gesetzt = zur
    # endgültigen Löschung vorgesehen zum jeweiligen Zeitpunkt (siehe
    # app/scripts/account_deletion_teardown.py). Kein eigenes Status-Enum nötig, der
    # Timestamp trägt die gesamte Zustandsmaschine.
    scheduled_deletion_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Tombstone-Zeile pro Haushalt, auf die Uploader-Referenzen verbliebener geteilter
    # Belege beim endgültigen Löschen eines Users umgeschrieben werden (max. eine pro
    # Haushalt, siehe Migration 0022). Muss von jeder Abfrage "echter" Haushaltsmitglieder
    # ausgeschlossen werden (list_household_members, Passkey-Exklusiv-Gate, Notification-
    # Fan-outs) — sonst leakt der Platzhalter in Logik, die alle User als reale Personen
    # behandelt.
    is_placeholder: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Benachrichtigungssystem: Liste der Notification-`type`-Werte, für die dieser User
    # zusätzlich zur In-App-Zeile eine E-Mail erhalten möchte (Opt-in pro Typ, Default
    # leer = konservativ, siehe Migration 0019).
    notification_email_opt_ins: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, server_default="[]"
    )

    household: Mapped["Household"] = relationship(back_populates="users")  # noqa: F821
    # passive_deletes=True (Konto-Löschung/DSGVO, siehe app/scripts/account_deletion_teardown.py
    # — der erste Ort im Projekt, der einen User per ORM löscht): analog zu
    # app/models/household.py — verhindert, dass die ORM beim Löschen eines Users versucht,
    # buckets.owner_id selbst auf NULL zu setzen (NOT NULL, würde scheitern), statt die
    # DB-seitige ON DELETE CASCADE greifen zu lassen. In der Teardown-Routine sind zu diesem
    # Zeitpunkt ohnehin bereits alle eigenen Buckets übertragen/gelöscht — reine Absicherung.
    owned_buckets: Mapped[list["Bucket"]] = relationship(  # noqa: F821
        back_populates="owner", passive_deletes=True
    )
