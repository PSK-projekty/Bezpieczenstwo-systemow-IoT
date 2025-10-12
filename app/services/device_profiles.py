"""Device category profiles and telemetry generators."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Dict, Tuple

TelemetryGenerator = Callable[[random.Random, datetime, int], dict]


@dataclass(frozen=True)
class DeviceCategoryProfile:
    slug: str
    name: str
    description: str
    default_name: str
    interval_seconds: Tuple[int, int]
    sample_payload: dict
    generator: TelemetryGenerator


def _weather_station_payload(rng: random.Random, timestamp: datetime, sequence: int) -> dict:
    base_temp = 18 + 6 * math.sin(sequence / 4.0)
    payload = {
        "metrics": {
            "temperature_c": round(base_temp + rng.uniform(-1.2, 1.2), 2),
            "humidity_pct": round(50 + 20 * math.sin(sequence / 5.0) + rng.uniform(-5, 5), 1),
            "wind_speed_ms": round(abs(rng.gauss(3.5, 1.1)), 2),
            "pressure_hpa": round(1008 + rng.uniform(-6.0, 6.0), 1),
            "rainfall_mm": round(max(0.0, rng.gauss(0.4, 0.3)), 2),
            "uv_index": round(max(0.0, rng.gauss(3.5, 1.2)), 1),
        },
        "status": "outdoor",
        "timestamp": timestamp.isoformat(),
    }
    return payload


def _indoor_thermometer_payload(rng: random.Random, timestamp: datetime, sequence: int) -> dict:
    base_temp = 22.0 + math.sin(sequence / 8.0)
    humidity = 40 + 10 * math.cos(sequence / 6.0) + rng.uniform(-2, 2)
    payload = {
        "metrics": {
            "temperature_c": round(base_temp + rng.uniform(-0.6, 0.6), 2),
            "humidity_pct": round(humidity, 1),
            "comfort_index": round(0.81 * humidity + 0.01 * humidity * (base_temp - 14.3) + 46.3, 2),
        },
        "status": "indoor",
        "timestamp": timestamp.isoformat(),
    }
    return payload


def _ip_camera_payload(rng: random.Random, timestamp: datetime, sequence: int) -> dict:
    motion = rng.random() < 0.15
    payload = {
        "metrics": {
            "bitrate_mbps": round(4.5 + rng.uniform(-0.8, 1.2), 2),
            "latency_ms": round(90 + rng.uniform(-20, 30), 1),
            "packet_loss_pct": round(max(0.0, rng.gauss(0.25, 0.1)), 2),
        },
        "status": "motion_detected" if motion else "idle",
        "snapshot_taken": motion,
        "timestamp": timestamp.isoformat(),
    }
    return payload


def _air_quality_payload(rng: random.Random, timestamp: datetime, sequence: int) -> dict:
    base_pm25 = 12 + 4 * math.sin(sequence / 7.0)
    payload = {
        "metrics": {
            "pm2_5": round(max(4.0, base_pm25 + rng.uniform(-2.5, 2.5)), 1),
            "pm10": round(max(7.0, base_pm25 * 1.4 + rng.uniform(-3.5, 3.5)), 1),
            "co2_ppm": round(420 + rng.uniform(-35, 45), 0),
            "voc_ppb": round(max(150, rng.gauss(320, 60))),
        },
        "status": "good",
        "timestamp": timestamp.isoformat(),
    }
    return payload


def _smart_lock_payload(rng: random.Random, timestamp: datetime, sequence: int) -> dict:
    event = rng.random()
    status = "locked"
    last_action = None
    if event < 0.2:
        status = "unlocked"
        last_action = {
            "user": rng.choice(["Operator", "Maintenance", "Courier"]),
            "method": rng.choice(["smartphone", "pin", "nfc"]),
            "timestamp": timestamp.isoformat(),
        }
    payload = {
        "status": status,
        "battery_pct": round(max(20.0, 95.0 - sequence * rng.uniform(0.05, 0.2)), 1),
        "jam_detected": rng.random() < 0.02,
        "last_action": last_action,
        "timestamp": timestamp.isoformat(),
    }
    return payload


DEVICE_CATEGORIES: Dict[str, DeviceCategoryProfile] = {
    "weather_station": DeviceCategoryProfile(
        slug="weather_station",
        name="Weather station",
        description="Outdoor weather station with wind, rain and UV metrics.",
        default_name="Weather station",
        interval_seconds=(15, 45),
        sample_payload=_weather_station_payload(random.Random(), datetime.now(timezone.utc), 0),
        generator=_weather_station_payload,
    ),
    "indoor_thermometer": DeviceCategoryProfile(
        slug="indoor_thermometer",
        name="Indoor thermometer",
        description="Monitors temperature and humidity inside a room.",
        default_name="Living room thermometer",
        interval_seconds=(30, 90),
        sample_payload=_indoor_thermometer_payload(random.Random(), datetime.now(timezone.utc), 0),
        generator=_indoor_thermometer_payload,
    ),
    "ip_camera": DeviceCategoryProfile(
        slug="ip_camera",
        name="IP camera",
        description="Network camera with motion detection and bitrate statistics.",
        default_name="Entrance camera",
        interval_seconds=(10, 25),
        sample_payload=_ip_camera_payload(random.Random(), datetime.now(timezone.utc), 0),
        generator=_ip_camera_payload,
    ),
    "air_quality": DeviceCategoryProfile(
        slug="air_quality",
        name="Air quality sensor",
        description="Tracks particulate matter, CO2 and VOC levels indoors.",
        default_name="Office air monitor",
        interval_seconds=(45, 120),
        sample_payload=_air_quality_payload(random.Random(), datetime.now(timezone.utc), 0),
        generator=_air_quality_payload,
    ),
    "smart_lock": DeviceCategoryProfile(
        slug="smart_lock",
        name="Smart lock",
        description="Controls door access and reports tamper events and battery.",
        default_name="Entry lock",
        interval_seconds=(60, 180),
        sample_payload=_smart_lock_payload(random.Random(), datetime.now(timezone.utc), 0),
        generator=_smart_lock_payload,
    ),
}


def get_category_or_raise(slug: str) -> DeviceCategoryProfile:
    """Return category profile or raise ValueError."""
    try:
        return DEVICE_CATEGORIES[slug]
    except KeyError as exc:
        raise ValueError(f"Unknown device category: {slug}") from exc
