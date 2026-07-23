import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.mixins import TimestampMixin


class ReceiptShare(Base, TimestampMixin):
    """
    Ein anonymer Freigabe-Link für genau einen Beleg (`receipt_id`), z.B. für
    Versicherung/Handel bei Reklamation — kein Empfänger-Account nötig.

    `token_hash` ist SHA-256 (hex, 64 Zeichen), NICHT Argon2id wie bei
    Recovery-Codes/Passwörtern — siehe Migration `0020_receipt_shares.py` für die volle
    Begründung (Kurzfassung: der einzige Zugriffspfad ist "gegeben nur der Token, finde
    die Zeile", was eine gesalzene Argon2id-Hash strukturell nicht per Index unterstützen
    kann; SHA-256 ist deterministisch und damit über den Unique-Index lookupbar).

    `household_id` ist bei Erstellung denormalisiert aus dem Beleg übernommen (spart
    einen Join beim anonymen `share_link_accessed`-Audit-Event, der keinen `user_id` zur
    Auflösung hat). Keine ORM-Relationships zu `Receipt`/`Household`/`User` (folgt der
    `Notification`-/`AuditLog`-Konvention) — Zugriff läuft über die Service-Schicht.

    Anders als `AuditLog` ist diese Tabelle bewusst NICHT immutable — `revoked_at`,
    `accessed_at` und `access_count` werden gezielt von der Anwendungslogik mutiert
    (Widerruf, Verbrauchs-Tracking), kein Beweismittel-Log. Nur `created_at` (aus
    `TimestampMixin`), kein `updated_at` — die anderen Zeitstempel sind eigene, gezielt
    gesetzte Felder, kein generisches "zuletzt geändert".

    `label` ist optional und ausschließlich zur eigenen Wiedererkennung durch den
    Ersteller gedacht (z.B. "Für Versicherung XY"), damit ein Link auch nach Ablauf/
    Widerruf/Verbrauch in der persistenten Historie auffindbar bleibt. Darf NICHT im
    öffentlichen/anonymen Schema (das der Empfänger des Links sieht) exponiert werden —
    nur in der haushaltsinternen Verwaltungsansicht.
    """

    __tablename__ = "receipt_shares"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    receipt_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("receipts.id", ondelete="CASCADE"), nullable=False
    )
    household_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("households.id", ondelete="CASCADE"), nullable=False
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    single_use: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    label: Mapped[str | None] = mapped_column(String(100), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    accessed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    access_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
