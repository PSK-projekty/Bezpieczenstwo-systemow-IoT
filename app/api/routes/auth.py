from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_app_settings, get_current_user, get_db
from app.core.config import Settings
from app.db.models import User
from app.schemas.auth import LoginRequest, LogoutRequest, RefreshRequest, RegisterRequest, TokenPairResponse, UserResponse
from app.services.auth_service import AuthService


router = APIRouter(prefix="/auth", tags=["autoryzacja"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register_user(
    payload: RegisterRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
) -> UserResponse:
    """Rejestruje nowego użytkownika końcowego."""
    service = AuthService(db, settings)
    return service.register_user(email=payload.email, password=payload.password)


@router.post("/login", response_model=TokenPairResponse)
def login_user(
    payload: LoginRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
) -> TokenPairResponse:
    """Logowanie i wydanie tokenów."""
    service = AuthService(db, settings)
    return service.login(email=payload.email, password=payload.password)


@router.post("/refresh", response_model=TokenPairResponse)
def refresh_tokens(
    payload: RefreshRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
) -> TokenPairResponse:
    """Odświeża token dostępu na podstawie ważnego tokenu odświeżania."""
    service = AuthService(db, settings)
    return service.refresh(refresh_token=payload.refresh_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout_user(
    payload: LogoutRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
) -> None:
    """Unieważnia podany token odświeżania."""
    service = AuthService(db, settings)
    service.logout(refresh_token=payload.refresh_token, user=current_user)
