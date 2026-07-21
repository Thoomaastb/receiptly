import uuid

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, SmallInteger
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.mixins import UpdatableTimestampMixin


class HouseholdSecuritySettings(Base, UpdatableTimestampMixin):
    """
    Haushaltsweite Sicherheitsrichtlinien (Phase 2 des Security-Hardening-Plans):
    TOTP-Pflicht für alle Haushaltsmitglieder, Audit-Log-Retention und ob fehlgeschlagene
    Logins mit unbekanntem Username den versuchten Usernamen mitloggen (Datenschutz-
    Schalter). Bewusst OHNE `passkey_exclusive_login` — kommt erst in Phase 4, wenn
    dahinter tatsächlich Logik steht (Lehre aus `users.totp_secret`, das jahrelang
    ungenutzt existierte, bevor jetzt in Phase 2 endlich Logik dazukam).
    """

    __tablename__ = "household_security_settings"
    __table_args__ = (
        CheckConstraint(
            "audit_retention_days IN (30, 90, 180, 365)",
            name="audit_retention_days",
        ),
    )

    household_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("households.id", ondelete="CASCADE"), primary_key=True
    )
    totp_required_for_household: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    audit_retention_days: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=90)
    log_attempted_username: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
