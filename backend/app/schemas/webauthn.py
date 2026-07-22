import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class WebauthnRegisterOptionsResponse(BaseModel):
    # Rohes JSON von webauthn.options_to_json() — 1:1 an navigator.credentials.create()
    # im Frontend durchreichen, hier keine strukturierte Aufschlüsselung nötig.
    options: str


class WebauthnRegisterVerifyRequest(BaseModel):
    # Rohes JSON von navigator.credentials.create() (per JSON.stringify serialisiert) —
    # py_webauthn parst und verifiziert es selbst, kein eigenes Schema für das komplette
    # WebAuthn-Antwortformat nötig.
    credential: str
    device_label: str = Field(min_length=1, max_length=100)


class WebauthnCredentialResponse(BaseModel):
    """Niemals public_key/credential_id roh exponieren (siehe Auftrag) — nur Verwaltungsfelder."""

    id: uuid.UUID
    device_label: str
    created_at: datetime
    last_used_at: datetime | None
    transports: str | None

    model_config = {"from_attributes": True}


class WebauthnCredentialRename(BaseModel):
    device_label: str = Field(min_length=1, max_length=100)


class WebauthnAuthenticateOptionsRequest(BaseModel):
    # Wie beim Passwort-Login: Username ODER E-Mail im selben Feld.
    username: str


class WebauthnAuthenticateOptionsResponse(BaseModel):
    options: str
    # Referenziert die serverseitig zwischengespeicherte Challenge + den per Username
    # aufgelösten User — kein Cookie, muss vom Client bei /authenticate/verify mitgeschickt
    # werden (siehe app/auth/webauthn_challenge.py).
    options_id: str


class WebauthnAuthenticateVerifyRequest(BaseModel):
    options_id: str
    credential: str
