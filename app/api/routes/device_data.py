from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_app_settings, get_db, get_device_from_token
from app.core.config import Settings
from app.db.models import Device
from app.schemas.device import DeviceTokenRequest, DeviceTokenResponse
from app.schemas.reading import ReadingCreateRequest, ReadingResponse
from app.services.device_service import DeviceService
from app.services.reading_service import ReadingService


router = APIRouter(prefix="/device", tags=["interfejs urządzenia"])


def _device_service(db: Session, settings: Settings) -> DeviceService:
    return DeviceService(db, settings)


def _reading_service(db: Session, settings: Settings) -> ReadingService:
    return ReadingService(db, settings)


@router.post("/token", response_model=DeviceTokenResponse)
def issue_device_token(
    payload: DeviceTokenRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
) -> DeviceTokenResponse:
    """Wydaje krótkoterminowy token dostępu dla urządzenia."""
    service = _device_service(db, settings)
    token, expires = service.issue_device_token(device_id=payload.device_id, device_secret=payload.device_secret)
    return DeviceTokenResponse(access_token=token, expires_in_minutes=expires)


@router.post("/readings", response_model=ReadingResponse, status_code=status.HTTP_201_CREATED)
def submit_device_reading(
    payload: ReadingCreateRequest,
    device: Device = Depends(get_device_from_token),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
) -> ReadingResponse:
    """Przyjmuje odczyt urządzenia."""
    reading_service = _reading_service(db, settings)
    reading = reading_service.create_reading(device=device, payload=payload.payload, device_timestamp=payload.device_timestamp)
    return ReadingResponse.model_validate(reading)
