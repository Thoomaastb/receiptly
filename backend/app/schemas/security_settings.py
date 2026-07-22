from typing import Literal

from pydantic import BaseModel

# Feste Stufen statt Freitext (siehe household_security_settings CHECK-Constraint,
# Migration 0014) — Literal statt eines eigenen field_validator, damit FastAPI die
# Auswahl bereits im OpenAPI-Schema als Enum ausweist.
AuditRetentionDays = Literal[30, 90, 180, 365]


class SecurityPolicyResponse(BaseModel):
    totp_required_for_household: bool
    audit_retention_days: AuditRetentionDays
    log_attempted_username: bool
    passkey_exclusive_login: bool

    model_config = {"from_attributes": True}


class SecurityPolicyUpdate(BaseModel):
    totp_required_for_household: bool
    audit_retention_days: AuditRetentionDays
    log_attempted_username: bool
    passkey_exclusive_login: bool


class PasskeyExclusiveGateStatus(BaseModel):
    """
    Live-Precondition-Status für den Passkey-Exklusiv-Schalter (Security-Hardening
    Phase 4) — eigener GET-Endpoint statt nur ein Fehlerfall am PUT, damit das Frontend
    den Schalter schon proaktiv deaktiviert/mit Live-Feedback anzeigen kann ("3 von 4
    Mitgliedern haben noch keinen Passkey"), bevor der Admin überhaupt einen Aktivierungs-
    versuch startet. Das PUT prüft dieselbe Bedingung zusätzlich serverseitig (defense in
    depth, siehe app/api/security_settings.py) und liefert bei Ablehnung dieselben Felder
    im HTTPException-detail, damit beide Stellen konsistent bleiben.
    """

    eligible: bool
    total_members: int
    missing_count: int
    missing_usernames: list[str]
