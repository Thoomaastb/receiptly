"""GET/PUT instanzweite SMTP-Konfiguration + Testmail-Versand — analog zum KI-Provider-Muster
(app/api/settings.py), aber ohne Haushalts-Layer: SMTP ist ein reines Instanz-Konzept, siehe
app/models/smtp_settings.py. Alle Endpoints Admin-only.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_admin
from app.auth.rate_limit import check_rate_limit
from app.database import get_db
from app.models.smtp_settings import SmtpSettings
from app.models.user import User
from app.schemas.smtp_settings import SmtpSettingsResponse, SmtpSettingsUpdate
from app.services.crypto import encrypt_secret
from app.services.email import send_email
from app.services.email_templates import render_test_email
from app.services.smtp_resolution import EffectiveSmtpConfig, resolve_effective_smtp

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/settings", tags=["smtp-settings"])


async def _resolve_effective_smtp_safe(db: AsyncSession) -> EffectiveSmtpConfig | None:
    """
    resolve_effective_smtp() kann ValueError werfen, wenn der gespeicherte
    encrypted_password nicht mehr entschlüsselbar ist (z.B. rotierter ENCRYPTION_KEY, siehe
    app/services/crypto.py). Die Settings-Seite muss trotzdem ladbar bleiben, daher
    degradiert das auf "kein wirksames SMTP" statt 500 — analog zu
    _resolve_effective_provider_safe() in app/api/settings.py.
    """
    try:
        return await resolve_effective_smtp(db)
    except ValueError:
        return None


async def _get_or_create(db: AsyncSession) -> SmtpSettings:
    result = await db.execute(select(SmtpSettings).where(SmtpSettings.id == 1))
    settings = result.scalar_one_or_none()
    if settings is None:
        settings = SmtpSettings(id=1)
        db.add(settings)
        await db.flush()
    return settings


@router.get("/smtp", response_model=SmtpSettingsResponse)
async def get_smtp_settings(
    admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)
) -> SmtpSettingsResponse:
    settings = await _get_or_create(db)
    effective = await _resolve_effective_smtp_safe(db)
    await db.commit()

    locked = effective is not None and effective.locked_by_server
    return SmtpSettingsResponse(
        host=settings.host,
        port=settings.port,
        username=settings.username,
        password_set=settings.encrypted_password is not None,
        from_email=settings.from_email,
        encryption=settings.encryption,
        locked_by_server=locked,
        effective_host=effective.host if locked else None,
    )


@router.put("/smtp", response_model=SmtpSettingsResponse)
async def update_smtp_settings(
    payload: SmtpSettingsUpdate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> SmtpSettingsResponse:
    """
    Admin-only. Das Passwort wird nie im Klartext gespeichert oder zurückgegeben — nur
    password_set als Boolean. Leeres/fehlendes password-Feld lässt ein vorhandenes Passwort
    unverändert (exakt wie api_key im KI-Provider-Muster, siehe app/api/settings.py). Bei
    serverseitig erzwungener SMTP-Konfiguration (.env smtp_host gesetzt) wird die Änderung
    abgelehnt — die UI zeigt das Formular zwar bereits read-only, das Backend darf sich
    darauf aber nicht allein verlassen.
    """
    effective = await _resolve_effective_smtp_safe(db)
    if effective is not None and effective.locked_by_server:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="SMTP ist serverseitig fest konfiguriert und kann hier nicht geändert werden",
        )

    settings = await _get_or_create(db)
    settings.host = payload.host
    settings.port = payload.port
    settings.username = payload.username
    if payload.password:
        settings.encrypted_password = encrypt_secret(payload.password)
    settings.from_email = payload.from_email
    settings.encryption = payload.encryption

    await db.commit()
    await db.refresh(settings)

    return SmtpSettingsResponse(
        host=settings.host,
        port=settings.port,
        username=settings.username,
        password_set=settings.encrypted_password is not None,
        from_email=settings.from_email,
        encryption=settings.encryption,
        locked_by_server=False,
    )


@router.post("/smtp/test-email", status_code=status.HTTP_204_NO_CONTENT)
async def send_test_email(
    admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)
) -> None:
    """
    Schickt eine Testmail an die Admin-E-Mail. Anders als der stille No-Op in send_email()
    bei fehlender Konfiguration gibt es hier explizites Feedback: 400, wenn kein wirksames
    SMTP konfiguriert ist, 502 bei einem tatsächlichen Versandfehler (z.B. falsche
    Zugangsdaten, Server nicht erreichbar).
    """
    await check_rate_limit("test_email", str(admin.id), 5, 3600)

    effective = await _resolve_effective_smtp_safe(db)
    if effective is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="SMTP ist nicht konfiguriert"
        )

    try:
        await send_email(
            db,
            to=admin.email,
            subject="receiptly – Testmail",
            text_body=(
                "Wenn du das hier liest, ist dein SMTP-Versand korrekt konfiguriert — "
                "Passwort-Reset- und andere Systemmails sollten damit zuverlässig ankommen."
            ),
            html_body=render_test_email(),
        )
    except Exception as exc:
        logger.exception("Testmail-Versand an %s fehlgeschlagen", admin.email)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Versand fehlgeschlagen: {exc}",
        ) from exc
