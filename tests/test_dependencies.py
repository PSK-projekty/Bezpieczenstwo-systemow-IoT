from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import dependencies
from app.core.security import (
    create_device_access_token,
    create_user_access_token,
    hash_secret,
)
from app.db.base import Base
from app.db.models import Device, DeviceStatus, User, UserRole


@pytest.fixture
def db_session(test_settings) -> Session:
    """In-memory session for dependency tests."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSession = sessionmaker(
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
        bind=engine,
        class_=Session,
    )
    Base.metadata.create_all(bind=engine)
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _create_user(session: Session, *, role: UserRole = UserRole.user) -> User:
    user = User(email=f"user-{role.value}@example.com", password_hash=hash_secret("Secret123!"), role=role)
    session.add(user)
    session.commit()
    return user


def _create_device(session: Session, owner: User, *, status: DeviceStatus = DeviceStatus.active, version: int = 1) -> Device:
    device = Device(
        name="Lab sensor",
        category="weather_station",
        owner_id=owner.id,
        secret_hash=hash_secret("device-secret"),
        status=status,
        token_version=version,
    )
    session.add(device)
    session.commit()
    return device


def test_get_current_user_success(db_session: Session, test_settings) -> None:
    user = _create_user(db_session, role=UserRole.admin)
    token = create_user_access_token({"sub": str(user.id), "role": user.role.value}, settings=test_settings)

    result = dependencies.get_current_user(token=token, db=db_session, settings=test_settings)

    assert result.id == user.id
    assert result.role == UserRole.admin


def test_get_current_user_missing_sub(db_session: Session, test_settings) -> None:
    token = create_user_access_token({"role": UserRole.user.value}, settings=test_settings)

    with pytest.raises(HTTPException) as exc:
        dependencies.get_current_user(token=token, db=db_session, settings=test_settings)

    assert exc.value.status_code == 401


def test_require_admin_denied() -> None:
    non_admin = SimpleNamespace(role=UserRole.user)

    with pytest.raises(HTTPException) as exc:
        dependencies.require_admin(non_admin)  # type: ignore[arg-type]

    assert exc.value.status_code == 403


def test_get_device_from_token_version_mismatch(db_session: Session, test_settings) -> None:
    owner = _create_user(db_session)
    device = _create_device(db_session, owner, version=2)
    token = create_device_access_token({"sub": device.id, "token_version": 1}, settings=test_settings)
    credentials = SimpleNamespace(credentials=token)

    with pytest.raises(HTTPException) as exc:
        dependencies.get_device_from_token(credentials=credentials, db=db_session, settings=test_settings)

    assert exc.value.status_code == 401
    assert "token" in exc.value.detail.lower()


def test_get_device_from_token_blocked_device(db_session: Session, test_settings) -> None:
    owner = _create_user(db_session)
    device = _create_device(db_session, owner, status=DeviceStatus.blocked)
    token = create_device_access_token({"sub": device.id, "token_version": device.token_version}, settings=test_settings)
    credentials = SimpleNamespace(credentials=token)

    with pytest.raises(HTTPException) as exc:
        dependencies.get_device_from_token(credentials=credentials, db=db_session, settings=test_settings)

    assert exc.value.status_code == 403


def test_get_device_from_token_missing_credentials(db_session: Session, test_settings) -> None:
    with pytest.raises(HTTPException) as exc:
        dependencies.get_device_from_token(credentials=None, db=db_session, settings=test_settings)

    assert exc.value.status_code == 401
    assert "brak tokenu" in exc.value.detail.lower()
