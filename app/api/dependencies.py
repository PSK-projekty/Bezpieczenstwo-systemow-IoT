from collections.abc import Generator

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer, OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.security import TokenValidationError, decode_token
from app.db.models import Device, DeviceStatus, User, UserRole
from app.db.session import SessionLocal


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")
device_scheme = HTTPBearer(auto_error=False)


def get_db() -> Generator[Session, None, None]:
    """Zwraca sesję bazy danych dla żądania."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_app_settings() -> Settings:
    """Dostarcza ustawienia aplikacji."""
    return get_settings()


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
) -> User:
    """Zapewnia zalogowanego użytkownika."""
    try:
        payload = decode_token(token, expected_type="user_access", settings=settings)
    except TokenValidationError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Brak identyfikatora użytkownika w tokenie.")
    user = db.get(User, int(user_id))
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Użytkownik nie istnieje.")
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    """Wymusza rolę administratora."""
    if user.role != UserRole.admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Brak uprawnień administratora.")
    return user


def get_device_from_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(device_scheme),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
) -> Device:
    """Weryfikuje token urządzenia i zwraca jego rekord."""
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Brak tokenu urządzenia.")
    try:
        payload = decode_token(credentials.credentials, expected_type="device_access", settings=settings)
    except TokenValidationError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    device_id = payload.get("sub")
    token_version = payload.get("token_version")
    if device_id is None or token_version is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Nieprawidłowy token urządzenia.")
    device = db.get(Device, device_id)
    if device is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Urządzenie nie istnieje.")
    if device.status != DeviceStatus.active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Urządzenie jest zablokowane.")
    if device.token_version != int(token_version):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token urządzenia jest unieważniony.")
    return device
