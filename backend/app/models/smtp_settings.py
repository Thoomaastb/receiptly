from sqlalchemy import CheckConstraint, Integer, SmallInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.mixins import UpdatableTimestampMixin


class SmtpSettings(Base, UpdatableTimestampMixin):
    """
    Instanzweite SMTP-Konfiguration für den ausgehenden Mail-Versand — echtes Singleton,
    keine Haushalts-Zuordnung. Im Unterschied zu AISettings (haushaltsweit, siehe
    app/models/ai_settings.py: jeder Haushalt hat eigene KI-Einstellungen) ist SMTP ein
    Instanz-, kein Haushalts-Konzept — es gibt nur einen ausgehenden Mail-Versand für die
    gesamte Anwendung. `id` ist fix auf 1 gesetzt und per CHECK-Constraint auf genau
    diesen Wert beschränkt (siehe Migration 0015), was eine zweite Zeile strukturell
    verhindert statt sich nur auf Anwendungslogik zu verlassen.
    """

    __tablename__ = "smtp_settings"
    __table_args__ = (
        CheckConstraint("id = 1", name="singleton"),
        CheckConstraint("encryption IN ('starttls', 'ssl')", name="encryption"),
    )

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, default=1)
    host: Mapped[str | None] = mapped_column(String(255), nullable=True)
    port: Mapped[int] = mapped_column(Integer, nullable=False, default=587)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Nie im Klartext — nur über app.services.crypto ver-/entschlüsselt, wie
    # AISettings.encrypted_api_key
    encrypted_password: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    from_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # 'starttls' (Port 587, Klartext-Verbindung mit TLS-Upgrade) oder 'ssl' (Port 465,
    # TLS von Anfang an) — siehe app/config.py smtp_encryption / app/services/email.py
    encryption: Mapped[str] = mapped_column(String(16), nullable=False, default="starttls")
