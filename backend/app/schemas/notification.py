import uuid
from datetime import datetime

from pydantic import BaseModel


class NotificationResponse(BaseModel):
    id: uuid.UUID
    category: str
    type: str
    title: str
    body: str
    link: str | None
    read_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class UnreadCountResponse(BaseModel):
    total: int
    by_category: dict[str, int]


class NotificationEmailPreferences(BaseModel):
    """Personale E-Mail-Opt-ins pro Notification-`type` (siehe services/notifications.py)."""

    opted_in_types: list[str]
