from sqlalchemy import Boolean, CheckConstraint, SmallInteger
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.mixins import UpdatableTimestampMixin


class UpdateCheckSettings(Base, UpdatableTimestampMixin):
    """
    Instanzweiter Schalter für den automatischen Update-Check — echtes Singleton, analog
    zu SmtpSettings (siehe app/models/smtp_settings.py). Im Unterschied zu SmtpSettings
    gibt es hier bewusst kein Server-Lock/.env-Override-Feld und keinen
    `resolve_effective_*`-Mechanismus — ein einfacher DB-Wert reicht. `id` ist fix auf 1
    gesetzt und per CHECK-Constraint auf genau diesen Wert beschränkt (siehe Migration
    0026), was eine zweite Zeile strukturell verhindert statt sich nur auf
    Anwendungslogik zu verlassen.
    """

    __tablename__ = "update_check_settings"
    __table_args__ = (CheckConstraint("id = 1", name="singleton"),)

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, default=1)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
