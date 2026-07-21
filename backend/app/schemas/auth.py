import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    household_name: str = Field(min_length=1, max_length=255)
    username: str = Field(min_length=3, max_length=64)
    email: EmailStr
    password: str = Field(min_length=8, max_length=255)


class LoginRequest(BaseModel):
    username: str
    password: str


class RequiresTotpResponse(BaseModel):
    """Antwort von POST /auth/login, wenn der erste Faktor stimmt, aber TOTP noch aussteht."""

    requires_totp: bool = True


class LoginTotpRequest(BaseModel):
    # Nimmt sowohl den 6-stelligen TOTP-Code als auch einen Recovery-Code entgegen
    # (Format "XXXXX-XXXXX", siehe app/services/totp.py) — Unterscheidung erfolgt serverseitig
    # rein anhand des Formats, daher hier bewusst kein einschränkendes Pattern.
    code: str = Field(min_length=6, max_length=32)


class InviteRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    email: EmailStr
    password: str = Field(min_length=8, max_length=255)


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=255)


class UserResponse(BaseModel):
    id: uuid.UUID
    username: str
    email: EmailStr
    role: str
    household_id: uuid.UUID
    # Frontend braucht das u.a. für das Zwangs-Enrollment-Gate bei Admins ohne
    # abgeschlossene TOTP-Einrichtung (siehe bekannte Lücke: /auth/register loggt einen
    # frischen Admin sofort ein, TOTP ist aber erst nach /auth/totp/confirm aktiv).
    totp_enabled: bool

    model_config = {"from_attributes": True}


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=255)


class SessionInfo(BaseModel):
    session_id: uuid.UUID
    user_agent: str
    ip: str
    created_at: datetime
    last_seen_at: datetime
    is_current: bool
