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

    model_config = {"from_attributes": True}


class SecurityPolicyUpdate(BaseModel):
    totp_required_for_household: bool
    audit_retention_days: AuditRetentionDays
    log_attempted_username: bool
