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
