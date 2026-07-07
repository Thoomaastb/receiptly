import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field


class ReceiptUploadResponse(BaseModel):
    id: uuid.UUID
    bucket_id: uuid.UUID
    status: str
    file_path: str
    content_hash: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ItemResponse(BaseModel):
    id: uuid.UUID
    raw_name: str
    quantity: float
    unit: str | None
    unit_price: float | None
    total_price: float

    model_config = {"from_attributes": True}


class ItemCreate(BaseModel):
    raw_name: str = Field(min_length=1, max_length=255)
    quantity: float = Field(default=1, gt=0)
    unit: str | None = Field(default=None, max_length=20)
    unit_price: float | None = Field(default=None, ge=0)
    total_price: float = Field(ge=0)


class ItemUpdate(BaseModel):
    raw_name: str | None = Field(default=None, min_length=1, max_length=255)
    quantity: float | None = Field(default=None, gt=0)
    unit: str | None = Field(default=None, max_length=20)
    unit_price: float | None = Field(default=None, ge=0)
    total_price: float | None = Field(default=None, ge=0)


class ReceiptListItem(BaseModel):
    id: uuid.UUID
    bucket_id: uuid.UUID
    status: str
    receipt_date: date | None
    total_amount: float | None
    currency: str
    thumb_path: str | None
    merchant_name: str | None
    item_count: int
    created_at: datetime

    model_config = {"from_attributes": True}


class ReceiptDetail(ReceiptListItem):
    ocr_raw_text: str | None
    ocr_confidence: float | None
    file_path: str
    is_high_value: bool
    warranty_months: int | None
    warranty_expires_at: date | None
    items: list[ItemResponse]


class ReceiptUpdate(BaseModel):
    """Alle Felder optional — nur mitgeschickte Felder werden geändert (siehe update_receipt)."""

    receipt_date: date | None = None
    total_amount: float | None = Field(default=None, ge=0)
    merchant_name: str | None = Field(default=None, min_length=1, max_length=255)
    is_high_value: bool | None = None
    warranty_months: int | None = Field(default=None, ge=0, le=600)

