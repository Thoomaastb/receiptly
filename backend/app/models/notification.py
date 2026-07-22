import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.mixins import TimestampMixin


class Notification(Base, TimestampMixin):
    """
    Eine In-App-Benachrichtigung für genau einen Empfänger (`user_id`) — auch bei
    haushaltsweiten Ereignissen (z.B. Passkey-Exklusiv-Login-Toggle) gibt es eine eigene
    Zeile pro Haushaltsmitglied, keine gemeinsame Zeile mit Auflösung zur Laufzeit.

    Anders als `AuditLog` (siehe `app/models/audit_log.py`) ist diese Tabelle bewusst
    NICHT immutable — kein DB-Trigger, siehe Migration `0018_notifications.py` für die
    volle Begründung. `read_at` wird gezielt mutiert (Als-gelesen-Markieren), und ein
    Retention-Job löscht abgelaufene gelesene Zeilen (90 Tage, Q9).

    `category`/`type` sind plain `String`, kein Postgres-Enum — analog zu
    `AuditLog.event_type`, aus demselben Grund (Erweiterbarkeit ohne Migration). Die
    v1-Werteliste wird als Konstante in `app/services/notifications.py` geführt, nicht
    als DB-Constraint. Keine ORM-Relationships zu `User`/`Household` (folgt der
    `AuditLog`-Konvention) — Zugriff läuft über die Service-Schicht, nicht über
    Navigations-Properties.
    """

    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    household_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("households.id", ondelete="CASCADE"), nullable=False
    )
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    type: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    link: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # Idempotenz-Basis (siehe uq_notifications_user_id_dedup_key in Migration 0018) —
    # jeder v1-Notification-Typ setzt diesen Wert immer.
    dedup_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
