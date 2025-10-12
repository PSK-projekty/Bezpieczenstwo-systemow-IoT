from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ReadingCreateRequest(BaseModel):
    """Ładunek przesyłany przez urządzenie."""

    device_timestamp: datetime | None = Field(default=None, description="Znacznik czasu z urządzenia.")
    payload: dict[str, Any] = Field(description="Dowolny niewielki JSON z danymi odczytu.")


class ReadingResponse(BaseModel):
    """Widok pojedynczego odczytu."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    device_id: str
    device_timestamp: datetime | None
    received_at: datetime
    payload: dict[str, Any]
    payload_size: int


class ReadingQueryParams(BaseModel):
    """Filtry pobierania odczytów."""

    device_id: str
    limit: int = Field(default=100, le=500, gt=0)
    since: datetime | None = None
    until: datetime | None = None


class ReadingMetaResponse(BaseModel):
    """Metadane kolekcji odczytów."""

    total_readings: int
    latest_received_at: datetime | None
    oldest_received_at: datetime | None
