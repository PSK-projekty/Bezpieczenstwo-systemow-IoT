from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.db.models import DeviceStatus


class DeviceCreateRequest(BaseModel):
    """Żądanie utworzenia nowego urządzenia."""

    name: str = Field(min_length=3, max_length=100)
    category: str = Field(min_length=3, max_length=50, description="Identyfikator kategorii urządzenia.")


class DeviceResponse(BaseModel):
    """Widok urządzenia na liście."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    category: str
    status: DeviceStatus
    created_at: datetime


class DeviceDetailResponse(DeviceResponse):
    """Szczegóły urządzenia."""

    updated_at: datetime
    last_reading_at: datetime | None


class DeviceSecretResponse(BaseModel):
    """Jednorazowy sekret wygenerowany dla urządzenia."""

    device_id: str
    device_secret: str
    category: str


class DeviceTokenRequest(BaseModel):
    """Żądanie wymiany sekretu na token urządzenia."""

    device_id: str
    device_secret: str


class DeviceTokenResponse(BaseModel):
    """Odpowiedź po autoryzacji urządzenia."""

    access_token: str
    token_type: str = "bearer"
    expires_in_minutes: int


class DeviceSecretRotateResponse(DeviceSecretResponse):
    """Sekret po rotacji."""


class DeviceStatusResponse(BaseModel):
    """Informacja o zmianie statusu urządzenia."""

    id: str
    status: DeviceStatus
    deactivated_at: datetime | None


class DeviceUpdateRequest(BaseModel):
    """Dane do aktualizacji urządzenia."""

    name: str | None = Field(default=None, min_length=3, max_length=100)
    category: str | None = Field(default=None, min_length=3, max_length=50)
    status: DeviceStatus | None = Field(default=None)


class DeviceCategoryResponse(BaseModel):
    """Informacje o dostępnej kategorii urządzenia."""

    slug: str
    name: str
    description: str
    default_name: str
    interval_seconds: tuple[int, int]
    sample_payload: dict[str, Any]
