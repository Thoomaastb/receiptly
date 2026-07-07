import uuid

from pydantic import BaseModel, Field


class BucketResponse(BaseModel):
    id: uuid.UUID
    name: str
    type: str
    visibility: str
    is_default: bool
    owner_id: uuid.UUID

    model_config = {"from_attributes": True}


class BucketCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class BucketVisibilityUpdate(BaseModel):
    visibility: str = Field(pattern="^(transparent|private)$")


class BucketRename(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class BucketAccessGrant(BaseModel):
    access_level: str = Field(pattern="^(view|edit)$")


class BucketAccessResponse(BaseModel):
    user_id: uuid.UUID
    username: str
    access_level: str

    model_config = {"from_attributes": True}
