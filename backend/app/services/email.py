import logging
from email.message import EmailMessage

import aiosmtplib

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


async def send_email(to: str, subject: str, text_body: str) -> None:
    """
    Versendet eine reine Text-Mail per SMTP (STARTTLS, sofern smtp_use_tls gesetzt ist —
    Standardfall für Port 587). Ohne konfigurierten smtp_host wird nicht versucht zu senden,
    sondern nur geloggt — verhindert einen Crash, solange noch keine echten SMTP-Zugangsdaten
    hinterlegt sind (z.B. frisch aufgesetzte Instanz).
    """
    if not settings.smtp_host:
        logger.warning(
            "SMTP nicht konfiguriert (smtp_host leer) — E-Mail an %s (%s) nicht gesendet",
            to,
            subject,
        )
        return

    message = EmailMessage()
    message["From"] = settings.smtp_from_email
    message["To"] = to
    message["Subject"] = subject
    message.set_content(text_body)

    # "ssl" (Port 465) baut die Verbindung direkt verschlüsselt auf (use_tls) — ein
    # STARTTLS-Handshake (start_tls) würde der Server dort nicht erwarten und die
    # Verbindung bricht ab. Alles andere läuft als STARTTLS (Port 587, Standardfall).
    tls_kwargs = (
        {"use_tls": True} if settings.smtp_encryption == "ssl" else {"start_tls": True}
    )

    await aiosmtplib.send(
        message,
        hostname=settings.smtp_host,
        port=settings.smtp_port,
        username=settings.smtp_username or None,
        password=settings.smtp_password or None,
        **tls_kwargs,
    )
