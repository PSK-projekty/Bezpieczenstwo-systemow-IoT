from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.security import (
    TokenValidationError,
    create_user_access_token,
    create_user_refresh_token,
    decode_token,
    hash_secret,
    verify_secret,
)
from app.db.models import RefreshToken, SecurityEventStatus, User, UserRole
from app.db.session import get_session
from app.schemas.auth import TokenPairResponse, UserResponse
from app.services.logging_service import SecurityLogger


class AuthService:
    """Obsługa rejestracji, logowania i zarządzania tokenami użytkowników."""

    def __init__(self, db: Session, settings: Settings):
        self.db = db
        self.settings = settings
        self.logger = SecurityLogger(get_session)

    def register_user(self, *, email: str, password: str) -> UserResponse:
        """Tworzy nowe konto użytkownika."""
        existing = self.db.execute(select(User).where(User.email == email.lower())).scalar_one_or_none()
        if existing:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Użytkownik już istnieje.")
        user = User(email=email.lower(), password_hash=hash_secret(password))
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        self.logger.log(
            actor_type="user",
            actor_id=str(user.id),
            event_type="register",
            status=SecurityEventStatus.success,
            detail="Nowe konto.",
        )
        return UserResponse.model_validate(user)

    def authenticate_user(self, *, email: str, password: str) -> User:
        """Weryfikuje dane logowania."""
        user = self.db.execute(select(User).where(User.email == email.lower())).scalar_one_or_none()
        if not user:
            self.logger.log(
                actor_type="user",
                actor_id=None,
                event_type="login",
                status=SecurityEventStatus.denied,
                detail="Nieznany adres e-mail.",
            )
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Nieprawidłowe dane logowania.")
        if not verify_secret(password, user.password_hash):
            self.logger.log(
                actor_type="user",
                actor_id=str(user.id),
                event_type="login",
                status=SecurityEventStatus.denied,
                detail="Błędne hasło.",
            )
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Nieprawidłowe dane logowania.")
        return user

    def create_token_pair(self, *, user: User) -> TokenPairResponse:
        """Buduje zestaw tokenów i zapisuje refresh w bazie."""
        access_payload = {"sub": str(user.id), "role": user.role.value}
        refresh_payload = {"sub": str(user.id)}

        access_token = create_user_access_token(access_payload, self.settings)
        refresh_token = create_user_refresh_token(refresh_payload, self.settings)

        decoded_refresh = decode_token(refresh_token, expected_type="user_refresh", settings=self.settings)

        refresh_entry = RefreshToken(
            user_id=user.id,
            token_jti=decoded_refresh["jti"],
            token_hash=hash_secret(refresh_token),
            expires_at=datetime.fromtimestamp(decoded_refresh["exp"], tz=timezone.utc),
        )
        self.db.add(refresh_entry)
        self.db.commit()

        self.logger.log(
            actor_type="user",
            actor_id=str(user.id),
            event_type="login",
            status=SecurityEventStatus.success,
            detail="Logowanie poprawne.",
        )

        return TokenPairResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in_minutes=self.settings.access_token_exp_minutes,
        )

    def login(self, *, email: str, password: str) -> TokenPairResponse:
        """Pełny przebieg logowania."""
        user = self.authenticate_user(email=email, password=password)
        return self.create_token_pair(user=user)

    def refresh(self, *, refresh_token: str) -> TokenPairResponse:
        """Odświeża token dostępu i rotuje token odświeżania."""
        try:
            payload = decode_token(refresh_token, expected_type="user_refresh", settings=self.settings)
        except TokenValidationError as exc:
            self.logger.log(
                actor_type="user",
                actor_id=None,
                event_type="refresh",
                status=SecurityEventStatus.denied,
                detail=str(exc),
            )
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

        user_id = int(payload["sub"])
        token_jti = payload["jti"]

        entry = (
            self.db.execute(
                select(RefreshToken).where(
                    RefreshToken.user_id == user_id,
                    RefreshToken.token_jti == token_jti,
                    RefreshToken.revoked.is_(False),
                )
            )
            .scalars()
            .first()
        )
        if not entry:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token odświeżania jest nieaktywny.")
        expires_at = entry.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at < datetime.now(tz=timezone.utc):
            entry.revoked = True
            self.db.commit()
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token odświeżania wygasł.")
        if not verify_secret(refresh_token, entry.token_hash):
            entry.revoked = True
            self.db.commit()
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token odświeżania odrzucony.")

        # Unieważniamy dotychczasowy wpis i tworzymy nowy.
        entry.revoked = True
        user = self.db.get(User, user_id)
        if not user:
            self.db.commit()
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Użytkownik nie istnieje.")
        new_tokens = self.create_token_pair(user=user)
        self.logger.log(
            actor_type="user",
            actor_id=str(user.id),
            event_type="refresh",
            status=SecurityEventStatus.success,
        )
        return new_tokens

    def logout(self, *, refresh_token: str, user: User) -> None:
        """Unieważnia wskazany token odświeżania."""
        try:
            payload = decode_token(refresh_token, expected_type="user_refresh", settings=self.settings)
        except TokenValidationError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        if int(payload["sub"]) != user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Token nie należy do użytkownika.")
        token_jti = payload["jti"]
        entry = (
            self.db.execute(
                select(RefreshToken).where(
                    RefreshToken.user_id == user.id,
                    RefreshToken.token_jti == token_jti,
                )
            )
            .scalars()
            .first()
        )
        if entry:
            entry.revoked = True
            self.db.commit()
            self.logger.log(
                actor_type="user",
                actor_id=str(user.id),
                event_type="logout",
                status=SecurityEventStatus.success,
            )
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Token został już wylogowany.")

    def ensure_admin_exists(self) -> None:
        """Tworzy konto administratora, gdy nie istnieje."""
        admin_exists = self.db.execute(select(User).where(User.role == UserRole.admin)).first()
        if admin_exists:
            return
        admin = User(
            email="admin@example.com",
            password_hash=hash_secret("Admin123!"),
            role=UserRole.admin,
        )
        self.db.add(admin)
        self.db.commit()
