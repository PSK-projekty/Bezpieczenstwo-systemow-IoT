"""Endpointy REST do zarządzania urządzeniami oraz ich odczytami."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_app_settings, get_current_user, get_db
from app.core.config import Settings
from app.db.models import DeviceStatus, User
from app.schemas.device import (
    DeviceCategoryResponse,
    DeviceCreateRequest,
    DeviceDetailResponse,
    DeviceResponse,
    DeviceSecretResponse,
    DeviceSecretRotateResponse,
    DeviceStatusResponse,
    DeviceUpdateRequest,
)
from app.schemas.reading import ReadingMetaResponse, ReadingResponse
from app.services.device_profiles import DEVICE_CATEGORIES
from app.services.device_service import DeviceService
from app.services.reading_service import ReadingService


router = APIRouter(prefix="/devices", tags=["urządzenia"])


def _service(db: Session, settings: Settings) -> DeviceService:
    return DeviceService(db, settings)


def _reading_service(db: Session, settings: Settings) -> ReadingService:
    return ReadingService(db, settings)


@router.get("/categories", response_model=list[DeviceCategoryResponse])
def list_categories() -> list[DeviceCategoryResponse]:
    """Zwraca dostępne kategorie urządzeń."""
    categories = []
    for profile in DEVICE_CATEGORIES.values():
        categories.append(
            DeviceCategoryResponse(
                slug=profile.slug,
                name=profile.name,
                description=profile.description,
                default_name=profile.default_name,
                interval_seconds=profile.interval_seconds,
                sample_payload=profile.sample_payload,
            )
        )
    return categories


@router.post("", response_model=DeviceSecretResponse, status_code=status.HTTP_201_CREATED)
def create_device(
    payload: DeviceCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
) -> DeviceSecretResponse:
    """Tworzy urządzenie dla zalogowanego użytkownika."""
    service = _service(db, settings)
    device, secret = service.create_device(owner=current_user, name=payload.name, category=payload.category)
    return DeviceSecretResponse(device_id=device.id, device_secret=secret, category=device.category)


@router.get("", response_model=list[DeviceResponse])
def list_devices(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
) -> list[DeviceResponse]:
    """Zwraca urządzenia użytkownika lub wszystkie dla administratora."""
    service = _service(db, settings)
    devices = service.list_devices(requester=current_user)
    return [DeviceResponse.model_validate(d) for d in devices]


@router.get("/{device_id}", response_model=DeviceDetailResponse)
def get_device(
    device_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
) -> DeviceDetailResponse:
    """Zwraca szczegóły urządzenia."""
    service = _service(db, settings)
    device = service.get_device(device_id=device_id, requester=current_user)
    return DeviceDetailResponse.model_validate(device)


@router.post("/{device_id}/deactivate", response_model=DeviceStatusResponse)
def deactivate_device(
    device_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
) -> DeviceStatusResponse:
    """Blokuje urządzenie i unieważnia tokeny."""
    service = _service(db, settings)
    device = service.get_device(device_id=device_id, requester=current_user)
    updated = service.deactivate_device(device=device, requester=current_user)
    return DeviceStatusResponse(id=updated.id, status=updated.status, deactivated_at=updated.deactivated_at)


@router.delete("/{device_id}", response_model=DeviceStatusResponse)
def delete_device(
    device_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
) -> DeviceStatusResponse:
    """Usuwa logicznie urządzenie."""
    service = _service(db, settings)
    device = service.get_device(device_id=device_id, requester=current_user)
    device_id_removed, removed_at = service.delete_device(device=device, requester=current_user)
    return DeviceStatusResponse(id=device_id_removed, status=DeviceStatus.deleted, deactivated_at=removed_at)


@router.put("/{device_id}", response_model=DeviceDetailResponse)
def update_device(
    device_id: str,
    payload: DeviceUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
) -> DeviceDetailResponse:
    """Aktualizuje nazwę, kategorię lub status urządzenia."""
    service = _service(db, settings)
    device = service.get_device(device_id=device_id, requester=current_user)
    updated = service.update_device(
        device=device,
        requester=current_user,
        name=payload.name,
        category=payload.category,
        status=payload.status,
    )
    return DeviceDetailResponse.model_validate(updated)


@router.post("/{device_id}/rotate-secret", response_model=DeviceSecretRotateResponse)
def rotate_device_secret(
    device_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
) -> DeviceSecretRotateResponse:
    """Rotuje sekret urządzenia i unieważnia stare tokeny."""
    service = _service(db, settings)
    device = service.get_device(device_id=device_id, requester=current_user)
    secret = service.rotate_secret(device=device, requester=current_user)
    return DeviceSecretRotateResponse(device_id=device.id, device_secret=secret, category=device.category)


@router.post("/{device_id}/invalidate-tokens", response_model=DeviceStatusResponse)
def invalidate_device_tokens(
    device_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
) -> DeviceStatusResponse:
    """Unieważnia natychmiast wszystkie aktywne tokeny urządzenia."""
    service = _service(db, settings)
    device = service.get_device(device_id=device_id, requester=current_user)
    updated = service.invalidate_tokens(device=device, requester=current_user)
    return DeviceStatusResponse(id=updated.id, status=updated.status, deactivated_at=updated.deactivated_at)


@router.get("/{device_id}/readings", response_model=list[ReadingResponse])
def list_device_readings(
    device_id: str,
    limit: int = Query(default=100, gt=0, le=500),
    since: datetime | None = Query(default=None),
    until: datetime | None = Query(default=None),
    include_simulated: bool = Query(default=False),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
) -> list[ReadingResponse]:
    """Zwraca odczyty urządzenia z filtrowaniem."""
    effective_limit = min(limit, settings.max_readings_page_size)
    device_service = _service(db, settings)
    reading_service = _reading_service(db, settings)
    device = device_service.get_device(device_id=device_id, requester=current_user)
    readings = reading_service.list_readings(
        device=device,
        requester=current_user,
        limit=effective_limit,
        since=since,
        until=until,
        include_simulated=include_simulated,
    )
    return [ReadingResponse.model_validate(r) for r in readings]


@router.get("/{device_id}/readings/meta", response_model=ReadingMetaResponse)
def device_readings_meta(
    device_id: str,
    since: datetime | None = Query(default=None),
    until: datetime | None = Query(default=None),
    include_simulated: bool = Query(default=False),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
) -> ReadingMetaResponse:
    """Zwraca metadane odczytów urządzenia."""
    device_service = _service(db, settings)
    reading_service = _reading_service(db, settings)
    device = device_service.get_device(device_id=device_id, requester=current_user)
    return reading_service.readings_meta(
        device=device,
        requester=current_user,
        since=since,
        until=until,
        include_simulated=include_simulated,
    )
