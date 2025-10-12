from http import HTTPStatus

from fastapi.testclient import TestClient


def register_and_login(client: TestClient, email: str, password: str) -> dict[str, str]:
    """Pomocniczo rejestruje i loguje użytkownika, zwracając tokeny."""
    client.post("/auth/register", json={"email": email, "password": password})
    response = client.post("/auth/login", json={"email": email, "password": password})
    assert response.status_code == HTTPStatus.OK
    return response.json()


def auth_headers(token: str) -> dict[str, str]:
    """Buduje nagłówki Autoryzacji."""
    return {"Authorization": f"Bearer {token}"}
