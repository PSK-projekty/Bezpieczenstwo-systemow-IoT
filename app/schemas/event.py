from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.db.models import SecurityEventStatus


class SecurityEventResponse(BaseModel):
    """Widok zdarzenia bezpieczeństwa."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    actor_type: str
    actor_id: str | None
    event_type: str
    status: SecurityEventStatus
    detail: str | None
