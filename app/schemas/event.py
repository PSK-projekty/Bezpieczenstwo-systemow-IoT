import enum
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.db.models import SecurityEventStatus


class SecurityEventResponse(BaseModel):
    """Widok zdarzenia bezpieczenstwa."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    actor_type: str
    actor_id: str | None
    event_type: str
    status: SecurityEventStatus
    detail: str | None


class SecuritySimulationScenario(str, enum.Enum):
    """Dostepne scenariusze symulacji zdarzen bezpieczenstwa."""

    jwt_invalid = "jwt_invalid"
    missing_authorization = "missing_authorization"
    device_forbidden = "device_forbidden"


class SecuritySimulationRequest(BaseModel):
    """Parametry prosby o rejestracje sztucznego zdarzenia."""

    scenario: SecuritySimulationScenario
    note: str | None = None
