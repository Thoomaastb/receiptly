import uuid
from datetime import date, datetime

from pydantic import BaseModel


class ReceiptUploadResponse(BaseModel):
    id: uuid.UUID
    bucket_id: uuid.UUID
    status: str
    file_path: str
    content_hash: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ReceiptListItem(BaseModel):
    id: uuid.UUID
    bucket_id: uuid.UUID
    status: str
    receipt_date: date | None
    total_amount: float | None
    currency: str
    thumb_path: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ReceiptDetail(ReceiptListItem):
    ocr_raw_text: str | None
    ocr_confidence: float | None
    file_path: str
    is_high_value: bool

