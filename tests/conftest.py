from collections.abc import Generator
import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import Session, sessionmaker

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))


os.environ.setdefault("QT_API", "pyqt5")

from app.api.dependencies import get_app_settings, get_db
from app.core.config import Settings
from app.db import session as db_session
from app.db.base import Base
from app.main import create_app


@pytest.fixture
def test_settings() -> Settings:
    """Nadpisane ustawienia z deterministycznymi sekretami."""
    return Settings(
        app_name="Test IoT",
        environment="test",
        database_url="sqlite:///:memory:",
        jwt_secret_key="test-secret",
        jwt_refresh_secret_key="test-refresh",
        jwt_device_secret_key="test-device",
        access_token_exp_minutes=60,
        refresh_token_exp_minutes=60 * 24,
        device_token_exp_minutes=60,
        telemetry_simulation_enabled=False,
        api_cors_origins=["*"],
    )


@pytest.fixture
def client(test_settings: Settings) -> Generator[TestClient, None, None]:
    """Udostępnia klienta API z bazą w pamięci."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False, class_=Session)

    Base.metadata.create_all(bind=engine)

    original_engine = db_session.engine
    original_session_local = db_session.SessionLocal

    db_session.engine = engine
    db_session.SessionLocal = TestingSessionLocal

    app = create_app()

    def override_get_db() -> Generator[Session, None, None]:
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_app_settings] = lambda: test_settings

    with TestClient(app) as test_client:
        yield test_client

    db_session.SessionLocal = original_session_local
    db_session.engine = original_engine
