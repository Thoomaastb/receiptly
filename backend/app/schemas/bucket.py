import uuid

from pydantic import BaseModel


class BucketResponse(BaseModel):
    id: uuid.UUID
    name: str
    type: str
    visibility: str
    is_default: bool

    model_config = {"from_attributes": True}
