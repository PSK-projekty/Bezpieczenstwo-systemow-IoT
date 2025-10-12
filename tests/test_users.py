from http import HTTPStatus

from fastapi import HTTPException, status
from fastapi.testclient import TestClient

from app.api.dependencies import get_app_settings
from app.db import session as db_session
from app.db.models import User, UserRole
from app.services.auth_service import AuthService
from app.core.security import hash_secret
from app.core.config import Settings

ADMIN_EMAIL = "admin-test@example.com"
ADMIN_PASSWORD = "SuperAdmin1!"


def admin_headers(client: TestClient) -> dict[str, str]:
    settings_provider = client.app.dependency_overrides.get(get_app_settings)
    settings = settings_provider() if settings_provider else Settings()

    with db_session.SessionLocal() as db:
        service = AuthService(db, settings)
        try:
            service.register_user(email=ADMIN_EMAIL, password=ADMIN_PASSWORD)
        except HTTPException as exc:
            if exc.status_code != status.HTTP_400_BAD_REQUEST:
                raise
        user = db.query(User).filter(User.email == ADMIN_EMAIL).first()
        assert user is not None
        user.password_hash = hash_secret(ADMIN_PASSWORD)
        user.role = UserRole.admin
        db.commit()
        db.refresh(user)
        assert user.id is not None
        token_pair = service.create_token_pair(user=user)
        user_id = user.id

    with db_session.SessionLocal() as verify_db:
        assert verify_db.get(User, user_id) is not None

    return {"Authorization": f"Bearer {token_pair.access_token}"}


def test_admin_user_crud(client: TestClient) -> None:
    headers = admin_headers(client)

    list_resp = client.get("/admin/users", headers=headers)
    assert list_resp.status_code == HTTPStatus.OK, list_resp.text
    existing_users = list_resp.json()
    assert any(user["email"] == ADMIN_EMAIL for user in existing_users)

    create_resp = client.post(
        "/admin/users",
        headers=headers,
        json={"email": "tech@example.com", "password": "SilneHaslo1!", "role": UserRole.user.value},
    )
    assert create_resp.status_code == HTTPStatus.CREATED, create_resp.text
    created_user = create_resp.json()
    assert created_user["email"] == "tech@example.com"

    user_id = created_user["id"]
    update_resp = client.put(
        f"/admin/users/{user_id}",
        headers=headers,
        json={"role": UserRole.admin.value},
    )
    assert update_resp.status_code == HTTPStatus.OK, update_resp.text
    assert update_resp.json()["role"] == UserRole.admin.value

    delete_resp = client.delete(f"/admin/users/{user_id}", headers=headers)
    assert delete_resp.status_code == HTTPStatus.NO_CONTENT

    list_after = client.get("/admin/users", headers=headers)
    assert list_after.status_code == HTTPStatus.OK
    user_ids = [u["id"] for u in list_after.json()]
    assert user_id not in user_ids
