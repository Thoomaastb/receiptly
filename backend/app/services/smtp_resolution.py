from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.smtp_settings import SmtpSettings
from app.services.crypto import decrypt_secret

settings = get_settings()


@dataclass
class EffectiveSmtpConfig:
    host: str
    port: int
    username: str | None
    password: str | None  # Klartext, ggf. bereits entschlüsselt
    from_email: str
    encryption: str
    locked_by_server: bool


async def _load_smtp_settings(db: AsyncSession) -> SmtpSettings | None:
    result = await db.execute(select(SmtpSettings).where(SmtpSettings.id == 1))
    return result.scalar_one_or_none()


async def resolve_effective_smtp(db: AsyncSession) -> EffectiveSmtpConfig | None:
    """
    2-stufige Prioritätskette (im Unterschied zur 3-stufigen KI-Provider-Kette, siehe
    ai_provider_resolution.py, gibt es hier keinen Haushalts-Layer — SMTP ist ein reines
    Instanz-Konzept, siehe app/models/smtp_settings.py): server-weiter .env-Fallback
    (smtp_host gesetzt) > SmtpSettings-DB-Singleton-Zeile (id=1) > None (kein Mailversand
    konfiguriert). Genutzt von app/services/email.py (send_email) und
    app/api/smtp_settings.py (locked_by_server/effective_host in der GET-Response).

    Kann ValueError werfen, wenn encrypted_password nicht mehr entschlüsselbar ist (z.B.
    rotierter ENCRYPTION_KEY, siehe app/services/crypto.py) — Aufrufer fangen das analog zu
    _resolve_effective_provider_safe() in app/api/settings.py ab und degradieren auf "kein
    wirksames SMTP" statt eines 500ers.
    """
    if settings.smtp_host:
        return EffectiveSmtpConfig(
            host=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_username or None,
            password=settings.smtp_password or None,
            from_email=settings.smtp_from_email,
            encryption=settings.smtp_encryption,
            locked_by_server=True,
        )

    smtp_settings = await _load_smtp_settings(db)
    if smtp_settings is not None and smtp_settings.host:
        password = (
            decrypt_secret(smtp_settings.encrypted_password)
            if smtp_settings.encrypted_password
            else None
        )
        return EffectiveSmtpConfig(
            host=smtp_settings.host,
            port=smtp_settings.port,
            username=smtp_settings.username,
            password=password,
            from_email=smtp_settings.from_email or settings.smtp_from_email,
            encryption=smtp_settings.encryption,
            locked_by_server=False,
        )

    return None  # kein SMTP verfügbar -> Mailversand bleibt aus, wie bisher
