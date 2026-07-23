import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class PublicReceiptShare(BaseModel):
    """
    Strikte Allowlist (Q4) für den anonymen Betrachter — bewusst NICHT ReceiptDetail
    wiederverwendet/erweitert (Leak-Risiko, sobald dort künftig neue Felder ergänzt werden).
    """

    merchant_name: str | None
    receipt_date: date | None
    total_amount: float | None
    currency: str
    content_type: str


class ReceiptShareCreateRequest(BaseModel):
    single_use: bool
    expiry_preset: Literal["7d", "30d", "90d", "unlimited"]
    # Rein zur eigenen Wiedererkennung durch den Ersteller (siehe Docstring in
    # app/models/receipt_share.py) — bewusst nicht in PublicReceiptShare.
    label: str | None = Field(None, max_length=100)

    @field_validator("label")
    @classmethod
    def _blank_label_to_none(cls, value: str | None) -> str | None:
        """Ein leeres/nur-Leerzeichen-Label soll NULL speichern, nicht "" — die
        Normalisierung sitzt hier statt in der Service-Schicht, damit sie unabhängig
        davon greift, wer create_share() künftig sonst noch aufruft."""
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class ReceiptShareCreateResponse(BaseModel):
    """Wird von der Route direkt konstruiert (Token + URL existieren nur hier), kein
    `from_attributes`-Mapping von der ORM-Zeile nötig."""

    id: uuid.UUID
    url: str  # vollständige, kopierbare URL — existiert nur in dieser Response
    single_use: bool
    expires_at: datetime | None
    created_at: datetime
    label: str | None


class ReceiptShareListItem(BaseModel):
    id: uuid.UUID
    single_use: bool
    expires_at: datetime | None
    accessed_at: datetime | None
    access_count: int
    created_at: datetime
    label: str | None
    # Von der Route berechnet (siehe _share_status() in services/receipt_shares.py),
    # keine Spalte auf dem ORM-Modell — from_attributes deckt nur die übrigen Felder ab.
    status: Literal["active", "consumed", "expired", "revoked"]

    model_config = {"from_attributes": True}
