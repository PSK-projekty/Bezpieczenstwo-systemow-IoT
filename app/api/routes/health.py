from datetime import datetime, timezone

from fastapi import APIRouter, Depends

from app.api.dependencies import get_app_settings
from app.core.config import Settings


router = APIRouter(tags=["zdrowie"])


@router.get("/healthz")
def healthcheck(settings: Settings = Depends(get_app_settings)) -> dict[str, str]:
    """Publiczny punkt sprawdzający stan usługi."""
    now = datetime.now(tz=timezone.utc).isoformat()
    return {
        "status": "działa",
        "aplikacja": settings.app_name,
        "czas": now,
        "środowisko": settings.environment,
    }
