import uuid
from datetime import datetime

from pydantic import BaseModel


class AuditLogEntry(BaseModel):
    id: uuid.UUID
    event_type: str
    ip: str | None
    user_agent: str | None
    attempted_username: str | None
    # Attribut-Name bewusst identisch zu AuditLog.event_metadata (app/models/audit_log.py)
    # gehalten, damit from_attributes ohne Alias-Mapping funktioniert. Die DB-Spalte heißt
    # weiterhin "metadata", das Python-seitige "event_metadata" ist nur eine ORM-Namens-
    # kollisionsvermeidung (Base.metadata), keine bewusste API-Vertrag-Entscheidung.
    event_metadata: dict | None
    created_at: datetime
    # Bei scope="own" immer der anfragende User selbst, bei scope="household" die
    # einzige Möglichkeit, Events verschiedener Haushaltsmitglieder zu unterscheiden
    # (siehe app/api/audit_log.py). None, wenn kein User bekannt ist (z.B. Event wurde
    # nach Account-Löschung ON DELETE SET NULL) oder nie einer gesetzt war.
    user_id: uuid.UUID | None
    username: str | None

    model_config = {"from_attributes": True}
