from pydantic import BaseModel


class UpdateCheckSettingsResponse(BaseModel):
    enabled: bool

    model_config = {"from_attributes": True}


class UpdateCheckSettingsUpdate(BaseModel):
    enabled: bool
