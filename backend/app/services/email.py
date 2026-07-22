import logging
from email.message import EmailMessage

import aiosmtplib
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.smtp_resolution import resolve_effective_smtp

logger = logging.getLogger(__name__)


async def send_email(
    db: AsyncSession, to: str, subject: str, text_body: str, html_body: str | None = None
) -> None:
    """
    Versendet eine E-Mail per SMTP. Die wirksame Konfiguration kommt über
    resolve_effective_smtp() (server-.env > SmtpSettings-DB-Singleton > None) — braucht
    dafür eine AsyncSession für den DB-Fallback. Ohne wirksames SMTP wird nicht versucht zu
    senden, sondern nur geloggt — verhindert einen Crash, solange noch keine echten
    SMTP-Zugangsdaten hinterlegt sind (z.B. frisch aufgesetzte Instanz).

    `text_body` ist immer Pflicht (Plain-Text-Fallback für Clients ohne HTML-Darstellung,
    Barrierefreiheit). Wird zusätzlich `html_body` übergeben, baut `add_alternative()` daraus
    eine multipart/alternative-Mail — Clients wählen dann selbst die beste Darstellung.
    """
    try:
        effective = await resolve_effective_smtp(db)
    except ValueError:
        # encrypted_password nicht mehr entschlüsselbar (z.B. rotierter ENCRYPTION_KEY) —
        # wie "nicht konfiguriert" behandeln statt eines 500ers, analog zu
        # _resolve_effective_provider_safe() in app/api/settings.py.
        effective = None

    if effective is None:
        logger.warning(
            "SMTP nicht konfiguriert — E-Mail an %s (%s) nicht gesendet",
            to,
            subject,
        )
        return

    message = EmailMessage()
    message["From"] = effective.from_email
    message["To"] = to
    message["Subject"] = subject
    message.set_content(text_body)
    if html_body is not None:
        message.add_alternative(html_body, subtype="html")

    # "ssl" (Port 465) baut die Verbindung direkt verschlüsselt auf (use_tls) — ein
    # STARTTLS-Handshake (start_tls) würde der Server dort nicht erwarten und die
    # Verbindung bricht ab. Alles andere läuft als STARTTLS (Port 587, Standardfall).
    tls_kwargs = {"use_tls": True} if effective.encryption == "ssl" else {"start_tls": True}

    await aiosmtplib.send(
        message,
        hostname=effective.host,
        port=effective.port,
        username=effective.username or None,
        password=effective.password or None,
        **tls_kwargs,
    )
