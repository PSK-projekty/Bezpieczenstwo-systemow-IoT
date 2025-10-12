"""Obsługa funkcji powiązanych z urządzeniami IoT."""

from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.security import (
    create_device_access_token,
    generate_device_secret,
    hash_secret,
    verify_secret,
)
from app.db.models import Device, DeviceStatus, SecurityEventStatus, User, UserRole
from app.db.session import get_session
from app.services.device_profiles import DEVICE_CATEGORIES, DeviceCategoryProfile, get_category_or_raise
from app.services.logging_service import SecurityLogger
from app.services.reading_service import ReadingService


class DeviceService:
    """Logika biznesowa dla zarządzania urządzeniami."""

    def __init__(self, db: Session, settings: Settings):
        self.db = db
        self.settings = settings
        self.logger = SecurityLogger(get_session)

    def create_device(self, *, owner: User, name: str, category: str) -> tuple[Device, str]:
        """Tworzy urządzenie, generuje sekret i wypełnia przykładowe dane."""
        profile = get_category_or_raise(category)
        secret = generate_device_secret()
        device = Device(
            name=name,
            category=profile.slug,
            owner_id=owner.id,
            secret_hash=hash_secret(secret),
            status=DeviceStatus.active,
        )
        self.db.add(device)
        self.db.commit()
        self.db.refresh(device)
        self.logger.log(
            actor_type="user",
            actor_id=str(owner.id),
            event_type="device_create",
            status=SecurityEventStatus.success,
            detail=f"Utworzono urządzenie {device.id}.",
        )

        self._seed_initial_readings(device)

        return device, secret

    def list_devices(self, *, requester: User) -> list[Device]:
        """Zwraca listę urządzeń użytkownika lub wszystkie dla administratora."""
        stmt = select(Device)
        if requester.role != UserRole.admin:
            stmt = stmt.where(Device.owner_id == requester.id)
        stmt = stmt.order_by(Device.created_at.desc())
        return list(self.db.execute(stmt).scalars().all())

    def get_device(self, *, device_id: str, requester: User) -> Device:
        """Pobiera urządzenie z kontrolą dostępu."""
        device = self.db.get(Device, device_id)
        if not device:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Urządzenie nie istnieje.")
        if requester.role != UserRole.admin and device.owner_id != requester.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Brak dostępu do urządzenia.")
        return device

    def deactivate_device(self, *, device: Device, requester: User) -> Device:
        """Oznacza urządzenie jako zablokowane."""
        if device.status == DeviceStatus.deleted:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Urządzenie już usunięte.")
        device.status = DeviceStatus.blocked
        device.deactivated_at = datetime.now(tz=timezone.utc)
        device.token_version += 1
        self.db.commit()
        self.logger.log(
            actor_type="user",
            actor_id=str(requester.id),
            event_type="device_block",
            status=SecurityEventStatus.success,
            detail=f"Zablokowano urządzenie {device.id}.",
        )
        return device

    def delete_device(self, *, device: Device, requester: User) -> tuple[str, datetime]:
        """Usuwa urządzenie z systemu (pełne usunięcie)."""
        if requester.role != UserRole.admin and device.owner_id != requester.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Brak uprawnień do usunięcia urządzenia.")
        removal_time = datetime.now(tz=timezone.utc)
        device_id = device.id
        self.db.delete(device)
        self.db.commit()
        self.logger.log(
            actor_type="user",
            actor_id=str(requester.id),
            event_type="device_delete",
            status=SecurityEventStatus.success,
            detail=f"Usunięto urządzenie {device_id}.",
        )
        return device_id, removal_time

    def update_device(
        self,
        *,
        device: Device,
        requester: User,
        name: str | None = None,
        category: str | None = None,
        status: DeviceStatus | None = None,
    ) -> Device:
        """Aktualizuje podstawowe informacje o urządzeniu."""
        if requester.role != UserRole.admin and device.owner_id != requester.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Brak uprawnień do modyfikacji urządzenia.")

        if name:
            device.name = name
        if category:
            profile = get_category_or_raise(category)
            if device.category != profile.slug:
                device.category = profile.slug
                self.db.flush()
                self._seed_initial_readings(device)
        if status:
            if status == DeviceStatus.deleted:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Użyj końcówki usuwającej urządzenie.")
            device.status = status
            if status == DeviceStatus.blocked:
                device.deactivated_at = datetime.now(tz=timezone.utc)
            elif status == DeviceStatus.active:
                device.deactivated_at = None

        self.db.commit()
        self.db.refresh(device)
        self.logger.log(
            actor_type="user",
            actor_id=str(requester.id),
            event_type="device_update",
            status=SecurityEventStatus.success,
            detail=f"Zaktualizowano urządzenie {device.id}.",
        )
        return device

    def rotate_secret(self, *, device: Device, requester: User) -> str:
        """Generuje nowy sekret urządzenia i unieważnia stare tokeny."""
        secret = generate_device_secret()
        device.secret_hash = hash_secret(secret)
        device.token_version += 1
        device.status = DeviceStatus.active
        device.deactivated_at = None
        device.last_reading_at = None
        self.db.commit()
        self.logger.log(
            actor_type="user",
            actor_id=str(requester.id),
            event_type="device_secret_rotate",
            status=SecurityEventStatus.success,
            detail=f"Zrotowano sekret urządzenia {device.id}.",
        )
        return secret

    def invalidate_tokens(self, *, device: Device, requester: User) -> Device:
        """Natychmiast unieważnia tokeny urządzenia."""
        device.token_version += 1
        self.db.commit()
        self.logger.log(
            actor_type="user",
            actor_id=str(requester.id),
            event_type="device_token_invalidate",
            status=SecurityEventStatus.success,
            detail=f"Unieważniono tokeny urządzenia {device.id}.",
        )
        return device

    def issue_device_token(self, *, device_id: str, device_secret: str) -> tuple[str, int]:
        """Weryfikuje sekret i wydaje token urządzenia."""
        device = self.db.get(Device, device_id)
        if not device:
            self.logger.log(
                actor_type="device",
                actor_id=device_id,
                event_type="device_auth",
                status=SecurityEventStatus.denied,
                detail="Nieznane urządzenie.",
            )
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Niepoprawne dane urządzenia.")
        if device.status != DeviceStatus.active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Urządzenie jest nieaktywne.")
        if not verify_secret(device_secret, device.secret_hash):
            self.logger.log(
                actor_type="device",
                actor_id=device_id,
                event_type="device_auth",
                status=SecurityEventStatus.denied,
                detail="Błędny sekret.",
            )
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Niepoprawne dane urządzenia.")
        token_payload = {"sub": device.id, "token_version": device.token_version}
        token = create_device_access_token(token_payload, self.settings)
        expires = self.settings.device_token_exp_minutes
        self.logger.log(
            actor_type="device",
            actor_id=device_id,
            event_type="device_auth",
            status=SecurityEventStatus.success,
            detail="Token urządzenia wydany.",
        )
        return token, expires

    def _seed_initial_readings(self, device: Device) -> None:
        """Buduje kilka przykładowych odczytów po dodaniu urządzenia."""
        reading_service = ReadingService(self.db, self.settings)
        profile: DeviceCategoryProfile = DEVICE_CATEGORIES.get(device.category, DEVICE_CATEGORIES["weather_station"])
        rng = random.Random(f"{device.id}-seed")
        now = datetime.now(tz=timezone.utc)
        samples: list[tuple[datetime, dict[str, Any]]] = []

        cumulative_offset = 0
        for idx in range(6):
            interval = rng.randint(profile.interval_seconds[0], profile.interval_seconds[1])
            cumulative_offset += interval
            timestamp = now - timedelta(seconds=cumulative_offset)
            payload = profile.generator(rng, timestamp, idx)
            payload["category"] = profile.slug
            samples.append((timestamp, payload))

        try:
            reading_service.seed_sample_readings(device=device, samples=samples)
        except Exception as exc:  # pragma: no cover - zabezpieczenie przed zatrzymaniem rejestracji urządzenia
            self.logger.log(
                actor_type="system",
                actor_id=device.id,
                event_type="reading_seed",
                status=SecurityEventStatus.error,
                detail=f"Nie udało się wygenerować danych symulacyjnych: {exc}",
            )
