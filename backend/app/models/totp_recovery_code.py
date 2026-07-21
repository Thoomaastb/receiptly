import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.mixins import TimestampMixin


class TotpRecoveryCode(Base, TimestampMixin):
    """
    Einmal-Recovery-Code für TOTP-Login ohne Zugriff auf den zweiten Faktor (verlorenes
    Gerät). Eigene Tabelle statt JSONB-Array auf `users`, damit das "verbraucht"-Markieren
    atomar ist (`UPDATE ... WHERE used_at IS NULL`) statt Race-Bedingung bei parallelem
    Verbrauchsversuch. `code_hash` über die bestehende Argon2id-Hashing-Funktion
    (app/auth/security.py), nicht im Klartext. "Neu generieren" läuft über
    Delete-all+Insert-all, kein In-Place-Edit einzelner Codes.
    """

    __tablename__ = "totp_recovery_codes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    code_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
