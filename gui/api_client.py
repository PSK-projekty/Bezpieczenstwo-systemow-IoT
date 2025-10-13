"""Client responsible for talking to the FastAPI backend."""

from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass
from typing import Any, Literal

import requests
from requests import Response, Session
from requests.exceptions import RequestException


class ApiError(Exception):
    """Raised when the HTTP layer reports an error."""

    def __init__(self, status_code: int, message: str, detail: str | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.detail = detail or message


def _decode_token_payload(token: str) -> dict[str, Any]:
    """Decode JWT payload without signature verification (for UX hints)."""
    try:
        payload_part = token.split(".")[1]
    except IndexError:
        return {}
    padding = "=" * (-len(payload_part) % 4)
    try:
        data = base64.urlsafe_b64decode(payload_part + padding)
        return json.loads(data.decode("utf-8"))
    except Exception:  # pragma: no cover - defensive
        return {}


@dataclass
class UserSession:
    email: str
    role: Literal["user", "admin"]


class ApiClient:
    """Thin wrapper around requests.Session with automatic token management."""

    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = base_url or os.getenv("IOT_BACKEND_URL", "http://127.0.0.1:8000")
        self.session: Session = requests.Session()
        self.access_token: str | None = None
        self.refresh_token: str | None = None
        self.user_session: UserSession | None = None

    # region helpers ----------------------------------------------------------------
    def _handle_response(self, response: Response) -> Any:
        if response.status_code >= 400:
            detail: str
            try:
                data = response.json()
                detail = data.get("detail", response.text)
            except ValueError:
                detail = response.text or "Serwer zwrócił błąd."
            raise ApiError(response.status_code, detail)
        if response.status_code == 204 or not response.content:
            return None
        try:
            return response.json()
        except ValueError:
            return response.text

    def _refresh_tokens(self) -> bool:
        if not self.refresh_token:
            return False
        try:
            response = self.session.post(
                f"{self.base_url}/auth/refresh",
                json={"refresh_token": self.refresh_token},
                headers={"Accept": "application/json"},
                timeout=10,
            )
            if response.status_code != 200:
                self.clear_session()
                return False
            data = response.json()
            self._store_tokens(data)
            return True
        except RequestException:
            self.clear_session()
            return False

    def _store_tokens(self, tokens: dict[str, Any]) -> None:
        self.access_token = tokens.get("access_token")
        self.refresh_token = tokens.get("refresh_token")
        payload = _decode_token_payload(self.access_token or "")
        role = payload.get("role", "user")
        if self.user_session:
            self.user_session.role = "admin" if role == "admin" else "user"

    def _request(
        self,
        method: str,
        path: str,
        *,
        auth: bool = True,
        timeout: int = 20,
        **kwargs: Any,
    ) -> Any:
        url = f"{self.base_url}{path}"
        headers = kwargs.pop("headers", {}) or {}
        headers["Accept"] = "application/json"
        if kwargs.get("json") is not None:
            headers.setdefault("Content-Type", "application/json")

        if auth:
            if not self.access_token:
                raise ApiError(401, "Brak aktywnej sesji użytkownika.")
            headers["Authorization"] = f"Bearer {self.access_token}"

        try:
            response = self.session.request(method, url, headers=headers, timeout=timeout, **kwargs)
            if response.status_code == 401 and auth and self._refresh_tokens():
                headers["Authorization"] = f"Bearer {self.access_token}"
                response = self.session.request(method, url, headers=headers, timeout=timeout, **kwargs)
        except RequestException as exc:
            raise ApiError(0, "Brak połączenia z serwerem API.") from exc

        return self._handle_response(response)

    # endregion ---------------------------------------------------------------------

    # region authentication ----------------------------------------------------------
    def register(self, email: str, password: str) -> None:
        self._request(
            "POST",
            "/auth/register",
            auth=False,
            json={"email": email, "password": password},
        )

    def login(self, email: str, password: str) -> UserSession:
        data = self._request(
            "POST",
            "/auth/login",
            auth=False,
            json={"email": email, "password": password},
        )
        if not isinstance(data, dict):
            raise ApiError(500, "Nieprawidłowa odpowiedź serwera podczas logowania.")
        self._store_tokens(data)
        payload = _decode_token_payload(self.access_token or "")
        role = "admin" if payload.get("role") == "admin" else "user"
        self.user_session = UserSession(email=email, role=role)
        return self.user_session

    def logout(self) -> None:
        if not self.refresh_token:
            self.clear_session()
            return
        try:
            self._request("POST", "/auth/logout", json={"refresh_token": self.refresh_token})
        finally:
            self.clear_session()

    def clear_session(self) -> None:
        self.access_token = None
        self.refresh_token = None
        self.user_session = None

    # endregion ---------------------------------------------------------------------

    # region devices ----------------------------------------------------------------
    def get_device_categories(self) -> list[dict[str, Any]]:
        data = self._request("GET", "/devices/categories")
        if not isinstance(data, list):
            raise ApiError(500, "Nie udało się pobrać kategorii urządzeń.")
        return data

    def get_devices(self) -> list[dict[str, Any]]:
        data = self._request("GET", "/devices")
        if not isinstance(data, list):
            raise ApiError(500, "Nieprawidłowa struktura listy urządzeń.")
        return data

    def create_device(self, name: str, category: str) -> dict[str, Any]:
        payload = {"name": name, "category": category}
        data = self._request("POST", "/devices", json=payload)
        if not isinstance(data, dict):
            raise ApiError(500, "Nie udało się utworzyć urządzenia.")
        return data

    def update_device(self, device_id: str, **fields: Any) -> dict[str, Any]:
        payload = {k: v for k, v in fields.items() if v is not None}
        data = self._request("PUT", f"/devices/{device_id}", json=payload)
        if not isinstance(data, dict):
            raise ApiError(500, "Nie udało się zaktualizować urządzenia.")
        return data

    def delete_device(self, device_id: str) -> dict[str, Any] | None:
        return self._request("DELETE", f"/devices/{device_id}")

    def get_device(self, device_id: str) -> dict[str, Any]:
        data = self._request("GET", f"/devices/{device_id}")
        if not isinstance(data, dict):
            raise ApiError(500, "Nie udało się pobrać szczegółów urządzenia.")
        return data

    def rotate_device_secret(self, device_id: str) -> dict[str, Any]:
        data = self._request("POST", f"/devices/{device_id}/rotate-secret")
        if not isinstance(data, dict):
            raise ApiError(500, "Nie udało się zrotować sekretu urządzenia.")
        return data

    def deactivate_device(self, device_id: str) -> dict[str, Any]:
        data = self._request("POST", f"/devices/{device_id}/deactivate")
        if not isinstance(data, dict):
            raise ApiError(500, "Nie udało się zablokować urządzenia.")
        return data

    def invalidate_device_tokens(self, device_id: str) -> dict[str, Any]:
        data = self._request("POST", f"/devices/{device_id}/invalidate-tokens")
        if not isinstance(data, dict):
            raise ApiError(500, "Nie udało się unieważnić tokenów urządzenia.")
        return data

    def get_readings(
        self,
        device_id: str,
        *,
        limit: int = 100,
        since: str | None = None,
        until: str | None = None,
        include_simulated: bool = False,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"limit": limit, "include_simulated": str(include_simulated).lower()}
        if since:
            params["since"] = since
        if until:
            params["until"] = until
        data = self._request("GET", f"/devices/{device_id}/readings", params=params)
        if not isinstance(data, list):
            raise ApiError(500, "Nieprawidłowa lista odczytów.")
        return data

    def get_readings_meta(
        self,
        device_id: str,
        *,
        since: str | None = None,
        until: str | None = None,
        include_simulated: bool = False,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"include_simulated": str(include_simulated).lower()}
        if since:
            params["since"] = since
        if until:
            params["until"] = until
        data = self._request("GET", f"/devices/{device_id}/readings/meta", params=params)
        if not isinstance(data, dict):
            raise ApiError(500, "Nie udało się pobrać metadanych odczytów.")
        return data

    # endregion ---------------------------------------------------------------------

    # region admin ------------------------------------------------------------------
    def get_security_events(self, limit: int = 100) -> list[dict[str, Any]]:
        data = self._request("GET", f"/admin/security-events?limit={limit}")
        if not isinstance(data, list):
            raise ApiError(500, "Nieprawidłowa lista zdarzeń bezpieczeństwa.")
        return data

    def list_users(self) -> list[dict[str, Any]]:
        data = self._request("GET", "/admin/users")
        if not isinstance(data, list):
            raise ApiError(500, "Nieprawidłowa lista użytkowników.")
        return data

    def create_user(self, email: str, password: str, role: str) -> dict[str, Any]:
        payload = {"email": email, "password": password, "role": role}
        data = self._request("POST", "/admin/users", json=payload)
        if not isinstance(data, dict):
            raise ApiError(500, "Nie udało się utworzyć użytkownika.")
        return data

    def update_user(self, user_id: int, **fields: Any) -> dict[str, Any]:
        payload = {k: v for k, v in fields.items() if v is not None}
        data = self._request("PUT", f"/admin/users/{user_id}", json=payload)
        if not isinstance(data, dict):
            raise ApiError(500, "Nie udało się zaktualizować użytkownika.")
        return data

    def delete_user(self, user_id: int) -> None:
        self._request("DELETE", f"/admin/users/{user_id}")

    def simulate_security_event(self, scenario: str, note: str | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {"scenario": scenario}
        if note:
            payload["note"] = note
        data = self._request("POST", "/admin/security-events/simulate", json=payload)
        if not isinstance(data, dict):
            raise ApiError(500, "Nie udalo sie utworzyc symulowanego zdarzenia.")
        return data

    # endregion ---------------------------------------------------------------------
