from pydantic import BaseModel, EmailStr, Field


class SmtpSettingsResponse(BaseModel):
    host: str | None
    port: int
    username: str | None
    # Nie das Passwort im Klartext zurückgeben — nur ob eines hinterlegt ist.
    password_set: bool
    from_email: str | None
    encryption: str
    # True, wenn eine server-weite .env-Konfiguration (smtp_host) den SMTP-Versand
    # erzwingt — siehe app/services/smtp_resolution.py. Der gespeicherte DB-Wert bleibt
    # dann zwar erhalten, ist aber ohne Wirkung.
    locked_by_server: bool
    # Nur gesetzt, wenn locked_by_server=True — der tatsächlich wirksame Host für die
    # read-only-Anzeige im Frontend, unabhängig vom gespeicherten DB-Wert.
    effective_host: str | None = None


class SmtpSettingsUpdate(BaseModel):
    host: str = Field(min_length=1, max_length=255)
    port: int = Field(ge=1, le=65535)
    username: str | None = Field(default=None, max_length=255)
    # Optional: nur mitschicken, wenn ein neues Passwort gesetzt/geändert werden soll.
    # Leer/None lassen, um das bestehende Passwort unverändert zu lassen.
    password: str | None = Field(default=None, min_length=1, max_length=512)
    from_email: EmailStr
    encryption: str = Field(pattern="^(starttls|ssl)$")
