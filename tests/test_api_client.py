import base64
import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from requests import Response
from requests.exceptions import RequestException

from gui.api_client import ApiClient, ApiError, _decode_token_payload, UserSession


def _make_response(status_code: int = 200, payload: dict | list | None = None, text: str = "") -> Response:
    response = Response()
    response.status_code = status_code
    if payload is not None:
        response._content = json.dumps(payload).encode("utf-8")
        response.headers["Content-Type"] = "application/json"
    else:
        response._content = text.encode("utf-8")
    return response


def _token_with_payload(payload: dict) -> str:
    encoded = base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8")).decode("utf-8").rstrip("=")
    return f"header.{encoded}.sig"


def test_decode_token_payload_handles_invalid_data() -> None:
    assert _decode_token_payload("invalid.token") == {}


def test_handle_response_raises_api_error_for_http_error() -> None:
    client = ApiClient(base_url="http://test")
    with pytest.raises(ApiError) as exc:
        client._handle_response(_make_response(500, {"detail": "oops"}))
    assert exc.value.status_code == 500
    assert "oops" in exc.value.detail


def test_handle_response_returns_text_for_plain_body() -> None:
    client = ApiClient(base_url="http://test")
    response = _make_response(200, None, text="plain-response")
    assert client._handle_response(response) == "plain-response"


def test_request_requires_access_token() -> None:
    client = ApiClient(base_url="http://test")
    with pytest.raises(ApiError):
        client._request("GET", "/devices")


def test_request_retries_after_refresh(monkeypatch) -> None:
    client = ApiClient(base_url="http://test")
    client.access_token = "expired"
    client.refresh_token = "refresh"
    first = _make_response(401, {"detail": "expired"})
    second = _make_response(200, {"ok": True})
    client.session.request = MagicMock(side_effect=[first, second])
    client._handle_response = MagicMock(return_value={"ok": True})
    client._refresh_tokens = MagicMock(return_value=True)

    result = client._request("GET", "/devices")

    assert result == {"ok": True}
    assert client.session.request.call_count == 2


def test_refresh_tokens_success(monkeypatch) -> None:
    client = ApiClient(base_url="http://test")
    client.refresh_token = "refresh"
    client.session.post = MagicMock(return_value=_make_response(200, {"access_token": "a", "refresh_token": "b"}))
    client._store_tokens = MagicMock()

    assert client._refresh_tokens() is True
    client._store_tokens.assert_called_once()


def test_refresh_tokens_failure_clears_session(monkeypatch) -> None:
    client = ApiClient(base_url="http://test")
    client.refresh_token = "refresh"
    client.session.post = MagicMock(side_effect=RequestException("down"))
    client.clear_session = MagicMock()

    assert client._refresh_tokens() is False
    client.clear_session.assert_called_once()


def test_store_tokens_updates_user_role() -> None:
    client = ApiClient(base_url="http://test")
    client.user_session = UserSession(email="user@example.com", role="user")
    token = _token_with_payload({"role": "admin"})

    client._store_tokens({"access_token": token, "refresh_token": "refresh"})

    assert client.access_token == token
    assert client.refresh_token == "refresh"
    assert client.user_session.role == "admin"


def test_login_creates_session(monkeypatch) -> None:
    client = ApiClient(base_url="http://test")
    token = _token_with_payload({"role": "admin"})
    monkeypatch.setattr(client, "_request", lambda *args, **kwargs: {"access_token": token, "refresh_token": "refresh"})

    session = client.login("admin@example.com", "Secret123!")

    assert session.email == "admin@example.com"
    assert session.role == "admin"
    assert client.access_token == token


def test_logout_without_refresh_token(monkeypatch) -> None:
    client = ApiClient(base_url="http://test")
    client.access_token = "token"
    client.logout()
    assert client.access_token is None
    assert client.user_session is None


def test_logout_with_refresh_token_calls_endpoint(monkeypatch) -> None:
    client = ApiClient(base_url="http://test")
    client.access_token = "token"
    client.refresh_token = "refresh"
    called = []
    monkeypatch.setattr(client, "_request", lambda *args, **kwargs: called.append((args, kwargs)))

    client.logout()

    assert called[0][0][1] == "/auth/logout"
    assert client.refresh_token is None


def test_register_invokes_request(monkeypatch) -> None:
    client = ApiClient(base_url="http://test")
    payloads = []
    monkeypatch.setattr(client, "_request", lambda method, path, **kwargs: payloads.append((method, path, kwargs)))

    client.register("user@example.com", "Password123!")

    method, path, kwargs = payloads[0]
    assert method == "POST" and path == "/auth/register"
    assert kwargs["auth"] is False
    assert kwargs["json"]["email"] == "user@example.com"


def test_get_devices_validates_response(monkeypatch) -> None:
    client = ApiClient(base_url="http://test")
    monkeypatch.setattr(client, "_request", lambda *args, **kwargs: {"not": "list"})

    with pytest.raises(ApiError):
        client.get_devices()


def test_get_device_categories(monkeypatch) -> None:
    client = ApiClient(base_url="http://test")
    monkeypatch.setattr(client, "_request", lambda *args, **kwargs: [{"slug": "weather"}])
    categories = client.get_device_categories()
    assert categories[0]["slug"] == "weather"


def test_get_readings_passes_parameters(monkeypatch) -> None:
    client = ApiClient(base_url="http://test")
    captured = {}

    def fake_request(method: str, path: str, **kwargs):
        captured["method"] = method
        captured["path"] = path
        captured["kwargs"] = kwargs
        return []

    monkeypatch.setattr(client, "_request", fake_request)

    client.get_readings("device-1", limit=50, since="2024-01-01T00:00:00Z", include_simulated=True)

    assert captured["path"] == "/devices/device-1/readings"
    params = captured["kwargs"]["params"]
    assert params["limit"] == 50
    assert params["include_simulated"] == "true"
    assert params["since"] == "2024-01-01T00:00:00Z"


def test_get_readings_meta(monkeypatch) -> None:
    client = ApiClient(base_url="http://test")
    monkeypatch.setattr(client, "_request", lambda *args, **kwargs: {"total": 1})
    meta = client.get_readings_meta("device-1", include_simulated=True)
    assert meta["total"] == 1


def test_simulate_security_event_sends_payload(monkeypatch) -> None:
    client = ApiClient(base_url="http://test")
    payloads = []
    monkeypatch.setattr(client, "_request", lambda method, path, **kwargs: payloads.append(kwargs["json"]) or {"ok": True})

    result = client.simulate_security_event("intrusion", note="door")

    assert payloads[0]["scenario"] == "intrusion"
    assert payloads[0]["note"] == "door"
    assert result == {"ok": True}


def test_user_management_wrappers(monkeypatch) -> None:
    client = ApiClient(base_url="http://test")
    monkeypatch.setattr(client, "_request", lambda *args, **kwargs: kwargs.get("json") or [])

    users = client.list_users()
    assert users == []

    created = client.create_user("mail", "Secret", "user")
    assert created["email"] == "mail"

    updated = client.update_user(1, role="admin", password=None)
    assert updated["role"] == "admin"

    # delete_user should not raise
    client.delete_user(1)


def test_device_management_helpers(monkeypatch) -> None:
    client = ApiClient(base_url="http://test")
    monkeypatch.setattr(client, "_request", lambda *args, **kwargs: kwargs.get("json") or {})

    device = client.create_device("Name", "smart_lock")
    assert device["name"] == "Name"

    updated = client.update_device("dev-1", name="New", status=None)
    assert updated["name"] == "New"

    # Should not raise for pass-through operations
    client.delete_device("dev-1")
    client.rotate_device_secret("dev-1")
    client.deactivate_device("dev-1")
    client.invalidate_device_tokens("dev-1")


def test_request_network_failure(monkeypatch) -> None:
    client = ApiClient(base_url="http://test")
    client.access_token = "token"
    monkeypatch.setattr(client.session, "request", MagicMock(side_effect=RequestException("offline")))

    with pytest.raises(ApiError) as exc:
        client._request("GET", "/devices")

    assert "Brak połączenia" in str(exc.value)
