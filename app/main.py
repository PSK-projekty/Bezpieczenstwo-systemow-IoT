from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.routes import admin, auth, device_data, devices, health
from app.core.config import Settings, get_settings
from app.db.base import Base
from app.db.session import engine, get_session
from app.services.auth_service import AuthService
from app.services.simulator import TelemetrySimulator


_simulator: TelemetrySimulator | None = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Inicjalizacja zasobów podczas startu aplikacji."""
    Base.metadata.create_all(bind=engine)
    _ensure_device_category_column()
    settings = get_settings()
    with get_session() as db:
        _bootstrap_admin(db, settings)
    global _simulator  # noqa: PLW0603 - kontrolowany global
    _simulator = TelemetrySimulator(settings)
    _simulator.start()
    try:
        yield
    finally:
        if _simulator:
            _simulator.stop()
            _simulator = None


def _ensure_device_category_column() -> None:
    """Dodaje kolumnę category do tabeli devices, jeśli jej brakuje (proste pseudo-migracje)."""
    with engine.connect() as connection:
        result = connection.execute(text("PRAGMA table_info(devices)"))
        columns = {row[1] for row in result}
        if "category" not in columns:
            connection.execute(text("ALTER TABLE devices ADD COLUMN category VARCHAR(50) DEFAULT 'custom'"))
            connection.commit()


def _bootstrap_admin(db: Session, settings: Settings) -> None:
    """Tworzy konto administratora, jeśli brakuje."""
    AuthService(db, settings).ensure_admin_exists()


def create_app() -> FastAPI:
    """Buduje instancję FastAPI."""
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version="1.0.0",
        lifespan=lifespan,
        openapi_url="/openapi.json",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.api_cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(devices.router)
    app.include_router(device_data.router)
    app.include_router(admin.router)

    return app


app = create_app()
