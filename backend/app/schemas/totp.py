from pydantic import BaseModel, Field


class TotpEnrollResponse(BaseModel):
    # Klartext-Secret für die manuelle Eingabe (Alternative zum Scannen), analog zum
    # QR-Code — beides zeigt dasselbe Secret nur in unterschiedlicher Form.
    secret: str
    qr_svg: str


class TotpConfirmRequest(BaseModel):
    code: str = Field(pattern=r"^\d{6}$")


class TotpReauthRequest(BaseModel):
    """
    Re-Verifizierung für /disable und /recovery-codes/regenerate — analog zum bestehenden
    change_password()-Reauth-Muster (aktuelles Passwort UND/ODER gültiger TOTP-Code).
    Mindestens eines der beiden Felder muss gesetzt und gültig sein.
    """

    current_password: str | None = None
    code: str | None = None


class TotpRecoveryCodesResponse(BaseModel):
    # Nur in dieser einen Antwort im Klartext — danach ausschließlich Hashes in der DB.
    recovery_codes: list[str]
