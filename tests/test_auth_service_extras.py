from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException, status
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import hash_secret
from app.db.base import Base
from app.db.models import RefreshToken, User, UserRole
from app.services.auth_service import AuthService


@pytest.fixture
def auth_service(test_settings):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSession = sessionmaker(
        bind=engine,
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
        class_=Session,
    )
    Base.metadata.create_all(bind=engine)
    session = TestingSession()
    service = AuthService(session, test_settings)
    try:
        yield service, session
    finally:
        session.close()
        engine.dispose()


def _add_user(session: Session, email: str, role: UserRole = UserRole.user) -> User:
    user = User(email=email, password_hash=hash_secret("Secret123!"), role=role)
    session.add(user)
    session.commit()
    return user


def test_refresh_revokes_expired_token(auth_service) -> None:
    service, session = auth_service
    user = _add_user(session, "alice@example.com")
    tokens = service.create_token_pair(user=user)

    entry = session.execute(select(RefreshToken)).scalar_one()
    entry.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    session.commit()

    with pytest.raises(HTTPException) as exc:
        service.refresh(refresh_token=tokens.refresh_token)

    assert exc.value.status_code == status.HTTP_401_UNAUTHORIZED
    session.refresh(entry)
    assert entry.revoked is True


def test_refresh_rejects_when_hash_mismatch(auth_service) -> None:
    service, session = auth_service
    user = _add_user(session, "bob@example.com")
    tokens = service.create_token_pair(user=user)

    entry = session.execute(select(RefreshToken)).scalar_one()
    entry.token_hash = hash_secret("other-token")
    session.commit()

    with pytest.raises(HTTPException) as exc:
        service.refresh(refresh_token=tokens.refresh_token)

    assert exc.value.status_code == status.HTTP_401_UNAUTHORIZED
    session.refresh(entry)
    assert entry.revoked is True


def test_logout_blocks_token_from_other_user(auth_service) -> None:
    service, session = auth_service
    owner = _add_user(session, "carol@example.com")
    other = _add_user(session, "dave@example.com")
    tokens = service.create_token_pair(user=owner)

    with pytest.raises(HTTPException) as exc:
        service.logout(refresh_token=tokens.refresh_token, user=other)

    assert exc.value.status_code == status.HTTP_403_FORBIDDEN


def test_ensure_admin_exists_idempotent(auth_service) -> None:
    service, session = auth_service

    service.ensure_admin_exists()
    first_count = session.execute(select(User).where(User.role == UserRole.admin)).all()

    service.ensure_admin_exists()
    second_count = session.execute(select(User).where(User.role == UserRole.admin)).all()

    assert len(first_count) == 1
    assert len(second_count) == 1
