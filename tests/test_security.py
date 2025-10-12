from http import HTTPStatus

from fastapi.testclient import TestClient

from .utils import auth_headers, register_and_login


def test_guest_cannot_access_protected_resources(client: TestClient) -> None:
    """Guest should reach health endpoint only."""
    health = client.get("/healthz")
    assert health.status_code == HTTPStatus.OK

    devices = client.get("/devices")
    assert devices.status_code == HTTPStatus.UNAUTHORIZED


def test_user_cannot_read_foreign_device_data(client: TestClient) -> None:
    """Device data should be protected between different users."""
    owner_tokens = register_and_login(client, "owner@example.com", "HasloDuze1!")
    owner_headers = auth_headers(owner_tokens["access_token"])

    device_resp = client.post(
        "/devices",
        headers=owner_headers,
        json={"name": "Czujnik A", "category": "weather_station"},
    )
    device_resp.raise_for_status()
    device_id = device_resp.json()["device_id"]

    other_tokens = register_and_login(client, "intruz@example.com", "HasloDuze2!")
    intruder_headers = auth_headers(other_tokens["access_token"])

    forbidden = client.get(f"/devices/{device_id}", headers=intruder_headers)
    assert forbidden.status_code == HTTPStatus.FORBIDDEN


def test_user_token_not_valid_for_device_channel(client: TestClient) -> None:
    """User token must not authorise the device channel."""
    tokens = register_and_login(client, "user-device@example.com", "HasloUserDevice1!")
    headers = auth_headers(tokens["access_token"])

    device = client.post(
        "/devices",
        headers=headers,
        json={"name": "Tester", "category": "smart_lock"},
    )
    device_id = device.json()["device_id"]
    assert device_id

    misuse = client.post(
        "/device/readings",
        headers=headers,
        json={"payload": {"value": 10}},
    )
    assert misuse.status_code == HTTPStatus.UNAUTHORIZED
