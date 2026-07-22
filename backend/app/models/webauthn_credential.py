import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, LargeBinary, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.mixins import TimestampMixin


class WebauthnCredential(Base, TimestampMixin):
    """
    Ein registrierter Passkey/FIDO2-Credential eines Users (Phase 3 des Security-
    Hardening-Plans, siehe concepts/security-hardening.md Abschnitt 4.3). 1:n zu `users`
    — Mehrfach-Registrierung ist gewollt (Backup-Redundanz, z.B. Zweitgerät/Security-Key).

    `public_key` ist der rohe COSE-Public-Key (Binärformat, `BYTEA`) wie ihn
    `py_webauthn` bei der Registrierung liefert — keine Textkodierung. `sign_count` dient
    der Clone-Detection beim späteren Login-Verify: viele Platform-Authenticatoren (Touch
    ID, Face ID, Windows Hello) melden dauerhaft `0`, was der Verify-Code entsprechend
    berücksichtigen muss (kein starrer "muss > gespeicherten Wert sein"-Vergleich).

    `last_used_at` bewusst nicht über TimestampMixin, sondern als eigenes nullable Feld —
    anders als `created_at` gibt es hier einen echten "noch nie benutzt"-Zustand (NULL).
    """

    __tablename__ = "webauthn_credentials"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Base64url-kodierte Credential-ID vom Authenticator (Text, im Unterschied zu
    # public_key) — vom Client bei jeder Authentication-Assertion mitgeschickt, darüber
    # wird der passende Credential-Datensatz nachgeschlagen.
    credential_id: Mapped[str] = mapped_column(String(1024), unique=True, nullable=False)
    public_key: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    sign_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Komma-getrennt, z.B. "usb,nfc,ble,internal" — vom Authenticator gemeldete
    # Transport-Hints, rein informativ für die UI (Credential-Verwaltung).
    transports: Mapped[str | None] = mapped_column(String(255), nullable=True)
    device_label: Mapped[str] = mapped_column(String(100), nullable=False)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
