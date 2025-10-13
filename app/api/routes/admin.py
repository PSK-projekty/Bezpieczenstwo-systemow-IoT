"""Administrative endpoints (security log and user management)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_app_settings, get_db, require_admin
from app.core.config import Settings
from app.db.models import SecurityEvent, SecurityEventStatus, User, UserRole
from app.schemas.auth import (
    UserCreateAdminRequest,
    UserResponse,
    UserUpdateAdminRequest,
)
from app.schemas.event import (
    SecurityEventResponse,
    SecuritySimulationRequest,
    SecuritySimulationScenario,
)
from app.services.user_service import UserService


router = APIRouter(prefix="/admin", tags=["administration"])


def _user_service(db: Session, settings: Settings) -> UserService:
    return UserService(db, settings)


SIMULATION_BLUEPRINTS: dict[SecuritySimulationScenario, dict[str, str | SecurityEventStatus]] = {
    SecuritySimulationScenario.jwt_invalid: {
        "event_type": "auth_jwt_invalid",
        "status": SecurityEventStatus.error,
        "detail": "Symulowany blad: token JWT odrzucony (zly podpis).",
    },
    SecuritySimulationScenario.missing_authorization: {
        "event_type": "auth_missing",
        "status": SecurityEventStatus.denied,
        "detail": "Symulowany blad: brak naglowka Authorization.",
    },
    SecuritySimulationScenario.device_forbidden: {
        "event_type": "device_action_denied",
        "status": SecurityEventStatus.denied,
        "detail": "Symulowany blad: urzadzenie odrzucone z powodu braku uprawnien.",
    },
}


@router.get("/security-events", response_model=list[SecurityEventResponse])
def list_security_events(
    limit: int = Query(default=100, gt=0, le=500),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
    _: User = Depends(require_admin),
) -> list[SecurityEventResponse]:
    """Return latest security events for administrators."""
    stmt = (
        db.query(SecurityEvent)
        .order_by(SecurityEvent.created_at.desc())
        .limit(limit)
    )
    events = stmt.all()
    return [SecurityEventResponse.model_validate(event) for event in events]


@router.post(
    "/security-events/simulate",
    response_model=SecurityEventResponse,
    status_code=status.HTTP_201_CREATED,
)
def simulate_security_event(
    payload: SecuritySimulationRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
    admin: User = Depends(require_admin),
) -> SecurityEventResponse:
    """Create a synthetic security event for demo and testing purposes."""
    blueprint = SIMULATION_BLUEPRINTS[payload.scenario]
    detail = blueprint["detail"]
    if payload.note:
        detail = f"{detail} Notatka: {payload.note}."
    event = SecurityEvent(
        actor_type="admin_tool",
        actor_id=str(admin.id),
        event_type=str(blueprint["event_type"]),
        status=blueprint["status"],  # type: ignore[arg-type]
        detail=detail,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return SecurityEventResponse.model_validate(event)


@router.get("/users", response_model=list[UserResponse])
def list_users(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
    admin: User = Depends(require_admin),
) -> list[UserResponse]:
    """Return user list (admin only)."""
    service = _user_service(db, settings)
    users = service.list_users()
    return [UserResponse.model_validate(user) for user in users]


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreateAdminRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
    admin: User = Depends(require_admin),
) -> UserResponse:
    """Create a new user account."""
    role = payload.role if isinstance(payload.role, UserRole) else UserRole(payload.role)
    service = _user_service(db, settings)
    user = service.create_user(email=payload.email, password=payload.password, role=role, acting_admin=admin)
    return UserResponse.model_validate(user)


@router.put("/users/{user_id}", response_model=UserResponse)
def update_user(
    user_id: int,
    payload: UserUpdateAdminRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
    admin: User = Depends(require_admin),
) -> UserResponse:
    """Update user properties."""
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    role = None
    if payload.role is not None:
        role = payload.role if isinstance(payload.role, UserRole) else UserRole(payload.role)
    service = _user_service(db, settings)
    updated = service.update_user(
        user=user,
        acting_admin=admin,
        email=payload.email,
        password=payload.password,
        role=role,
    )
    return UserResponse.model_validate(updated)


@router.delete(
    "/users/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
    admin: User = Depends(require_admin),
) -> Response:
    """Delete a user account."""
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    service = _user_service(db, settings)
    service.delete_user(user=user, acting_admin=admin)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
