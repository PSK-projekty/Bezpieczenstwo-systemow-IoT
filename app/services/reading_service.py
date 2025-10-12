"""Obsługa zapisu i odczytu danych urządzeń."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Iterable

from fastapi import HTTPException, status
from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import Device, Reading, SecurityEventStatus, User, UserRole
from app.db.session import get_session
from app.schemas.reading import ReadingMetaResponse
from app.services.logging_service import SecurityLogger


class ReadingService:
    """Logika obsługi odczytów urządzeń."""

    def __init__(self, db: Session, settings: Settings):
        self.db = db
        self.settings = settings
        self.logger = SecurityLogger(get_session)

    def _ensure_owner(self, device: Device, requester: User) -> None:
        if requester.role != UserRole.admin and device.owner_id != requester.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Brak dostępu do odczytów urządzenia.")

    def _payload_size(self, payload: dict) -> int:
        body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
        return len(body.encode("utf-8"))

    def _is_simulated(self, reading: Reading) -> bool:
        payload = reading.payload
        return isinstance(payload, dict) and payload.get("__simulated__") is True

    def _readings_query(
        self,
        *,
        device: Device,
        limit: int | None,
        since: datetime | None,
        until: datetime | None,
    ) -> Select:
        stmt = select(Reading).where(Reading.device_id == device.id)
        if since:
            stmt = stmt.where(Reading.received_at >= since)
        if until:
            stmt = stmt.where(Reading.received_at <= until)
        stmt = stmt.order_by(Reading.received_at.desc())
        if limit is not None:
            stmt = stmt.limit(limit)
        return stmt

    def create_reading(
        self,
        *,
        device: Device,
        payload: dict,
        device_timestamp: datetime | None,
        received_at: datetime | None = None,
        force: bool = False,
        mark_simulated: bool = False,
    ) -> Reading:
        """Dodaje nowy odczyt po sprawdzeniu limitów."""
        size = self._payload_size(payload)
        if size > self.settings.data_payload_limit_bytes:
            self.logger.log(
                actor_type="device",
                actor_id=device.id,
                event_type="reading_reject",
                status=SecurityEventStatus.denied,
                detail="Ładunek przekracza limit.",
            )
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"Ładunek przekracza {self.settings.data_payload_limit_bytes} bajtów.",
            )
        now = received_at or datetime.now(tz=timezone.utc)
        if not force:
            last = device.last_reading_at
            if last and last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)
            if last and (now - last).total_seconds() < self.settings.min_seconds_between_readings:
                last_reading = (
                    self.db.query(Reading)
                    .filter(Reading.device_id == device.id)
                    .order_by(Reading.received_at.desc())
                    .first()
                )
                if not last_reading or not self._is_simulated(last_reading):
                    retry_after = self.settings.min_seconds_between_readings
                    self.logger.log(
                        actor_type="device",
                        actor_id=device.id,
                        event_type="reading_rate_limit",
                        status=SecurityEventStatus.denied,
                        detail="Przekroczony limit częstotliwości.",
                    )
                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail=f"Limit częstotliwości przekroczony. Spróbuj ponownie po {retry_after} s.",
                    )

        final_payload = dict(payload)
        if mark_simulated:
            final_payload["__simulated__"] = True

        reading = Reading(
            device_id=device.id,
            device_timestamp=device_timestamp,
            received_at=now,
            payload=final_payload,
            payload_size=size,
        )
        device.last_reading_at = now
        self.db.add(reading)
        self.db.commit()
        self.db.refresh(reading)
        self.logger.log(
            actor_type="device",
            actor_id=device.id,
            event_type="reading_accept",
            status=SecurityEventStatus.success,
        )
        return reading

    def list_readings(
        self,
        *,
        device: Device,
        requester: User,
        limit: int,
        since: datetime | None,
        until: datetime | None,
        include_simulated: bool,
    ) -> list[Reading]:
        """Zwraca odczyty urządzenia z kontrolą dostępu."""
        self._ensure_owner(device, requester)
        stmt = self._readings_query(device=device, limit=limit, since=since, until=until)
        readings = list(self.db.execute(stmt).scalars().all())
        if include_simulated:
            return readings
        return [reading for reading in readings if not self._is_simulated(reading)]

    def seed_sample_readings(
        self,
        *,
        device: Device,
        samples: Iterable[tuple[datetime, dict[str, Any]]],
    ) -> None:
        """Wstrzykuje przykładowe odczyty z pominięciem limitów dla nowego urządzenia."""
        resolved_samples: list[tuple[datetime, dict[str, Any]]] = []
        for received_at, payload in samples:
            ts = received_at
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            payload = dict(payload)
            payload["__simulated__"] = True
            resolved_samples.append((ts, payload))

        if not resolved_samples:
            return

        resolved_samples.sort(key=lambda item: item[0])
        readings: list[Reading] = []
        last_received = None

        for received_at, payload in resolved_samples:
            size = self._payload_size(payload)
            reading = Reading(
                device_id=device.id,
                device_timestamp=received_at,
                received_at=received_at,
                payload=payload,
                payload_size=size,
            )
            readings.append(reading)
            last_received = received_at

        self.db.add_all(readings)
        device.last_reading_at = last_received
        self.db.commit()

        for reading in readings:
            self.db.refresh(reading)

        self.logger.log(
            actor_type="system",
            actor_id=device.id,
            event_type="reading_seed",
            status=SecurityEventStatus.success,
            detail=f"Wygenerowano {len(readings)} przykładowych odczytów.",
        )

    def readings_meta(
        self,
        *,
        device: Device,
        requester: User,
        since: datetime | None,
        until: datetime | None,
        include_simulated: bool,
    ) -> ReadingMetaResponse:
        """Zwraca metadane odczytów (z możliwością pominięcia symulacji)."""
        self._ensure_owner(device, requester)
        stmt = self._readings_query(device=device, limit=None, since=since, until=until)
        readings = list(self.db.execute(stmt).scalars().all())
        if not include_simulated:
            readings = [reading for reading in readings if not self._is_simulated(reading)]

        total = len(readings)
        latest = readings[0].received_at if readings else None
        oldest = readings[-1].received_at if readings else None
        return ReadingMetaResponse(
            total_readings=total,
            latest_received_at=latest,
            oldest_received_at=oldest,
        )
