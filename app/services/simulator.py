"""Background simulator emitting synthetic telemetry for devices."""

from __future__ import annotations

import random
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Dict

from app.core.config import Settings
from app.db.models import Device, DeviceStatus
from app.db.session import get_session
from app.services.device_profiles import DEVICE_CATEGORIES, DeviceCategoryProfile, get_category_or_raise
from app.services.reading_service import ReadingService


class TelemetrySimulator:
    """Starts a daemon thread that generates category aware telemetry."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._next_emit: Dict[str, datetime] = {}
        self._sequence: Dict[str, int] = {}
        self._random_cache: Dict[str, random.Random] = {}

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        if not self.settings.telemetry_simulation_enabled:
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, name="telemetry-simulator", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if not self._thread:
            return
        self._stop_event.set()
        self._thread.join(timeout=5)
        self._thread = None
        self._next_emit.clear()
        self._sequence.clear()
        self._random_cache.clear()

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                self._tick()
            except Exception:  # pragma: no cover - defensive guard
                time.sleep(1)
            time.sleep(1)

    def _tick(self) -> None:
        now = datetime.now(tz=timezone.utc)
        with get_session() as db:
            reading_service = ReadingService(db, self.settings)
            devices: list[Device] = (
                db.query(Device)
                .filter(Device.status == DeviceStatus.active)
                .all()
            )
            active_ids = {device.id for device in devices}
            for cached_id in list(self._next_emit.keys()):
                if cached_id not in active_ids:
                    self._next_emit.pop(cached_id, None)
                    self._sequence.pop(cached_id, None)
                    self._random_cache.pop(cached_id, None)

            for device in devices:
                profile = self._resolve_profile(device)
                next_emit = self._next_emit.get(device.id)
                if not next_emit or next_emit <= now:
                    rng = self._random_cache.setdefault(device.id, random.Random(f"{device.id}-sim"))
                    sequence = self._sequence.get(device.id, 0)
                    timestamp = now
                    payload = profile.generator(rng, timestamp, sequence)
                    payload["category"] = profile.slug
                    reading_service.create_reading(
                        device=device,
                        payload=payload,
                        device_timestamp=timestamp,
                        received_at=timestamp,
                        force=True,
                        mark_simulated=True,
                    )
                    self._sequence[device.id] = sequence + 1
                    interval = rng.randint(profile.interval_seconds[0], profile.interval_seconds[1])
                    self._next_emit[device.id] = timestamp + timedelta(seconds=interval)

    @staticmethod
    def _resolve_profile(device: Device) -> DeviceCategoryProfile:
        try:
            return get_category_or_raise(device.category)
        except ValueError:
            return DEVICE_CATEGORIES["weather_station"]
