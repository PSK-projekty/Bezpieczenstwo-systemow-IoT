from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.db.models import UserRole


class RegisterRequest(BaseModel):
    """Dane do utworzenia konta użytkownika."""

    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    """Dane logowania użytkownika."""

    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class TokenPairResponse(BaseModel):
    """Odpowiedź z tokenami po logowaniu lub odświeżeniu."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in_minutes: int


class RefreshRequest(BaseModel):
    """Żądanie odświeżenia tokenu."""

    refresh_token: str


class LogoutRequest(BaseModel):
    """Żądanie wylogowania z unieważnieniem tokenu."""

    refresh_token: str


class UserResponse(BaseModel):
    """Widok danych użytkownika."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    role: UserRole
    created_at: datetime


class UserCreateAdminRequest(BaseModel):
    """Dane do utworzenia konta przez administratora."""

    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    role: UserRole = UserRole.user


class UserUpdateAdminRequest(BaseModel):
    """Pola do aktualizacji użytkownika."""

    email: EmailStr | None = None
    password: str | None = Field(default=None, min_length=8, max_length=128)
    role: UserRole | None = None
