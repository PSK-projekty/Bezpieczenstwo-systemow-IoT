import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Literal
from uuid import uuid4

from jose import JWTError, jwt
from passlib.context import CryptContext

from .config import Settings, get_settings


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class TokenValidationError(Exception):
    """Wyjątek sygnalizujący problem z tokenem."""


def hash_secret(value: str) -> str:
    """Zwraca skrót hasła lub sekretu."""
    return pwd_context.hash(value)


def verify_secret(value: str, hashed: str) -> bool:
    """Porównuje wartość z zapisanym skrótem."""
    return pwd_context.verify(value, hashed)


def _create_token(
    data: dict[str, Any],
    *,
    expires_minutes: int,
    secret_key: str,
    algorithm: str,
) -> str:
    """Buduje podpisany token JWT z metadanymi."""
    to_encode = data.copy()
    now = datetime.now(tz=timezone.utc)
    expire = now + timedelta(minutes=expires_minutes)
    to_encode.update({"exp": expire, "iat": now, "jti": uuid4().hex})
    return jwt.encode(to_encode, secret_key, algorithm=algorithm)


def create_user_access_token(data: dict[str, Any], settings: Settings | None = None) -> str:
    """Generuje token dostępu dla użytkownika."""
    settings = settings or get_settings()
    return _create_token(
        data=dict(data, token_type="user_access"),
        expires_minutes=settings.access_token_exp_minutes,
        secret_key=settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def create_user_refresh_token(data: dict[str, Any], settings: Settings | None = None) -> str:
    """Generuje token odświeżania dla użytkownika."""
    settings = settings or get_settings()
    return _create_token(
        data=dict(data, token_type="user_refresh"),
        expires_minutes=settings.refresh_token_exp_minutes,
        secret_key=settings.jwt_refresh_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def create_device_access_token(data: dict[str, Any], settings: Settings | None = None) -> str:
    """Generuje token dostępu dla urządzenia."""
    settings = settings or get_settings()
    return _create_token(
        data=dict(data, token_type="device_access"),
        expires_minutes=settings.device_token_exp_minutes,
        secret_key=settings.jwt_device_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def decode_token(
    token: str,
    *,
    expected_type: Literal["user_access", "user_refresh", "device_access"],
    settings: Settings | None = None,
) -> dict[str, Any]:
    """Weryfikuje i dekoduje token JWT."""
    settings = settings or get_settings()
    secrets_map = {
        "user_access": settings.jwt_secret_key,
        "user_refresh": settings.jwt_refresh_secret_key,
        "device_access": settings.jwt_device_secret_key,
    }
    secret_key = secrets_map[expected_type]
    try:
        payload = jwt.decode(token, secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise TokenValidationError("Token jest nieprawidłowy lub wygasł.") from exc
    if payload.get("token_type") != expected_type:
        raise TokenValidationError("Token pochodzi z niewłaściwej ścieżki autoryzacji.")
    return payload


def generate_device_secret() -> str:
    """Generuje jednorazowy sekret dla urządzenia."""
    return secrets.token_urlsafe(32)
