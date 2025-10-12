from http import HTTPStatus

from fastapi.testclient import TestClient


def test_user_registration_login_refresh_logout(client: TestClient) -> None:
    """Sprawdza podstawowy przebieg uwierzytelniania."""
    register = client.post(
        "/auth/register",
        json={"email": "jan@example.com", "password": "TestoweHaslo1!"},
    )
    assert register.status_code == HTTPStatus.CREATED

    login = client.post(
        "/auth/login",
        json={"email": "jan@example.com", "password": "TestoweHaslo1!"},
    )
    assert login.status_code == HTTPStatus.OK
    tokens = login.json()
    assert "access_token" in tokens
    assert "refresh_token" in tokens

    refresh = client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert refresh.status_code == HTTPStatus.OK
    refreshed = refresh.json()
    assert refreshed["access_token"] != tokens["access_token"]

    logout = client.post(
        "/auth/logout",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert logout.status_code == HTTPStatus.NO_CONTENT

    reuse = client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert reuse.status_code == HTTPStatus.UNAUTHORIZED


def test_duplicate_registration_is_rejected(client: TestClient) -> None:
    """Dwukrotna rejestracja tego samego adresu powinna kończyć się błędem."""
    payload = {"email": "anna@example.com", "password": "SekretneHaslo2!"}
    first = client.post("/auth/register", json=payload)
    assert first.status_code == HTTPStatus.CREATED
    second = client.post("/auth/register", json=payload)
    assert second.status_code == HTTPStatus.BAD_REQUEST
