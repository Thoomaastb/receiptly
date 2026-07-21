import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AuditLog(Base):
    """
    Ein sicherheitsrelevantes Ereignis (Login, Passwortänderung, Rate-Limit-Treffer, ...).

    Insert-only: bewusst kein UpdatableTimestampMixin, nur created_at. Die Tabelle ist per
    DB-Trigger (Migration 0012, `audit_log_immutable_trigger`) gegen UPDATE/DELETE
    gesperrt — ORM-`.update()`/`.delete()`-Aufrufe auf dieses Model schlagen als rohe
    Postgres-Exception fehl, nicht als saubere App-Fehlermeldung. Nur ein dedizierter
    Cleanup-Job (Retention-Löschung, spätere Phase) setzt `SET LOCAL audit.allow_delete =
    'true'` in eigener Transaktion und darf löschen.
    """

    __tablename__ = "audit_log"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    household_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("households.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(300), nullable=True)
    # Nur relevant bei Login-Fehlschlägen ohne bekannten user_id (falscher Username) —
    # ob dieses Feld tatsächlich befüllt wird, steuert später household_security_settings
    # .log_attempted_username (Phase 2).
    attempted_username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    event_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True, name="metadata")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
