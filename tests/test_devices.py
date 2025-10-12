from http import HTTPStatus

from fastapi.testclient import TestClient

from app.db.models import DeviceStatus

from .utils import auth_headers, register_and_login


def test_device_categories_endpoint(client: TestClient) -> None:
    response = client.get("/devices/categories")
    assert response.status_code == HTTPStatus.OK
    categories = response.json()
    slugs = {item["slug"] for item in categories}
    assert {"weather_station", "indoor_thermometer", "ip_camera", "air_quality", "smart_lock"}.issubset(slugs)


def test_device_lifecycle_and_readings(client: TestClient) -> None:
    """Scenariusz dodania urządzenia, autoryzacji i przesłania danych."""
    creds = register_and_login(client, "user1@example.com", "HasloBezpieczne1!")
    headers = auth_headers(creds["access_token"])

    created = client.post(
        "/devices",
        headers=headers,
        json={"name": "Czujnik Temperatury", "category": "weather_station"},
    )
    assert created.status_code == HTTPStatus.CREATED
    secret_payload = created.json()
    device_id = secret_payload["device_id"]
    device_secret = secret_payload["device_secret"]
    assert secret_payload["category"] == "weather_station"

    devices = client.get("/devices", headers=headers)
    assert devices.status_code == HTTPStatus.OK
    assert len(devices.json()) == 1

    detail = client.get(f"/devices/{device_id}", headers=headers)
    assert detail.status_code == HTTPStatus.OK
    assert detail.json()["id"] == device_id

    token_resp = client.post("/device/token", json={"device_id": device_id, "device_secret": device_secret})
    assert token_resp.status_code == HTTPStatus.OK
    device_token = token_resp.json()["access_token"]

    reading = client.post(
        "/device/readings",
        headers={"Authorization": f"Bearer {device_token}"},
        json={"payload": {"temperature": 21.5}, "device_timestamp": None},
    )
    assert reading.status_code == HTTPStatus.CREATED

    readings = client.get(f"/devices/{device_id}/readings", headers=headers)
    assert readings.status_code == HTTPStatus.OK
    data = readings.json()
    assert len(data) == 1
    assert data[0]["payload"]["temperature"] == 21.5

    meta = client.get(f"/devices/{device_id}/readings/meta", headers=headers)
    assert meta.status_code == HTTPStatus.OK
    assert meta.json()["total_readings"] == 1

    rotate = client.post(f"/devices/{device_id}/rotate-secret", headers=headers)
    assert rotate.status_code == HTTPStatus.OK
    new_secret = rotate.json()["device_secret"]

    # Stary token powinien przestać działać po rotacji sekretu.
    reuse_old = client.post(
        "/device/readings",
        headers={"Authorization": f"Bearer {device_token}"},
        json={"payload": {"temperature": 22.0}},
    )
    assert reuse_old.status_code == HTTPStatus.UNAUTHORIZED

    new_token_resp = client.post("/device/token", json={"device_id": device_id, "device_secret": new_secret})
    assert new_token_resp.status_code == HTTPStatus.OK
    new_token = new_token_resp.json()["access_token"]

    second = client.post(
        "/device/readings",
        headers={"Authorization": f"Bearer {new_token}"},
        json={"payload": {"temperature": 23.0}},
    )
    assert second.status_code == HTTPStatus.CREATED


def test_rate_limit_and_payload_limit(client: TestClient) -> None:
    """Weryfikuje ograniczenia rozmiaru i częstotliwości."""
    creds = register_and_login(client, "user2@example.com", "HasloBezpieczne2!")
    headers = auth_headers(creds["access_token"])

    device = client.post(
        "/devices",
        headers=headers,
        json={"name": "Pomiar wilgotności", "category": "air_quality"},
    )
    device_id = device.json()["device_id"]
    device_secret = device.json()["device_secret"]

    token_resp = client.post("/device/token", json={"device_id": device_id, "device_secret": device_secret})
    device_token = token_resp.json()["access_token"]

    oversized_payload = {"payload": {"dane": "x" * 3000}}
    too_big = client.post(
        "/device/readings",
        headers={"Authorization": f"Bearer {device_token}"},
        json=oversized_payload,
    )
    assert too_big.status_code == HTTPStatus.REQUEST_ENTITY_TOO_LARGE

    first = client.post(
        "/device/readings",
        headers={"Authorization": f"Bearer {device_token}"},
        json={"payload": {"value": 1}},
    )
    assert first.status_code == HTTPStatus.CREATED

    second = client.post(
        "/device/readings",
        headers={"Authorization": f"Bearer {device_token}"},
        json={"payload": {"value": 2}},
    )
    assert second.status_code == HTTPStatus.TOO_MANY_REQUESTS


def test_device_update_and_delete(client: TestClient) -> None:
    creds = register_and_login(client, "user3@example.com", "HasloBezpieczne3!")
    headers = auth_headers(creds["access_token"])

    created = client.post(
        "/devices",
        headers=headers,
        json={"name": "Kamera frontowa", "category": "ip_camera"},
    )
    device_id = created.json()["device_id"]

    update_resp = client.put(
        f"/devices/{device_id}",
        headers=headers,
        json={"name": "Kamera garażowa", "category": "smart_lock", "status": DeviceStatus.active.value},
    )
    assert update_resp.status_code == HTTPStatus.OK
    assert update_resp.json()["name"] == "Kamera garażowa"
    assert update_resp.json()["category"] == "smart_lock"

    delete_resp = client.delete(f"/devices/{device_id}", headers=headers)
    assert delete_resp.status_code == HTTPStatus.OK
    payload = delete_resp.json()
    assert payload["status"] == DeviceStatus.deleted.value

    devices = client.get("/devices", headers=headers)
    assert devices.status_code == HTTPStatus.OK
    assert devices.json() == []

    detail_missing = client.get(f"/devices/{device_id}", headers=headers)
    assert detail_missing.status_code == HTTPStatus.NOT_FOUND
