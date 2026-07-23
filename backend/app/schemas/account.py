from datetime import datetime

from pydantic import BaseModel, Field


class AccountDeletionRequest(BaseModel):
    """
    Re-Auth-Body für POST /account/deletion (Konzept Q11): entweder Passwort ODER
    Passkey-Bestätigung (je nachdem, ob passkey_exclusive_login aktiv ist — siehe
    app/services/account_deletion.py::verify_active_login_factor), zusätzlich ein
    TOTP-Code, falls für den User aktiv. Alle drei Faktor-Felder bewusst optional, da nur
    die jeweils zutreffende Teilmenge tatsächlich befüllt wird — die Prüfung selbst
    entscheidet, was verpflichtend ist.
    """

    current_password: str | None = None
    passkey_credential: str | None = None
    passkey_options_id: str | None = None
    totp_code: str | None = None
    # UI-Friktion (Konzept 3.3): Nutzername oder "LÖSCHEN" als bewusste Bestätigung.
    confirmation_text: str = Field(min_length=1, max_length=64)


class AccountDeletionResponse(BaseModel):
    scheduled_deletion_at: datetime


class RequiresReactivationResponse(BaseModel):
    """
    Antwort von POST /auth/login bzw. /auth/login/totp, wenn die Login-Faktoren zwar
    vollständig korrekt sind, das Konto sich aber noch in der 14-tägigen Löschungs-
    Karenzzeit befindet (siehe app/services/account_deletion.py::check_reactivation_required).
    Gleiches Idiom wie RequiresTotpResponse (app/schemas/auth.py) — ein Response-Feld statt
    eines eigenen HTTP-Statuscodes, weil das Signal erst NACH vollständiger Auth entsteht.
    """

    requires_reactivation: bool = True
    scheduled_deletion_at: datetime
