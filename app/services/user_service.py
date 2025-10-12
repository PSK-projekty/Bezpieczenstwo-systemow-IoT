"""Administrative service dealing with user CRUD operations."""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.security import hash_secret
from app.db.models import SecurityEventStatus, User, UserRole
from app.db.session import get_session
from app.services.logging_service import SecurityLogger


class UserService:
    """Helpers used by admin endpoints to manage user accounts."""

    def __init__(self, db: Session, settings: Settings):
        self.db = db
        self.settings = settings
        self.logger = SecurityLogger(get_session)

    def list_users(self) -> list[User]:
        stmt = select(User).order_by(User.created_at.desc())
        return list(self.db.execute(stmt).scalars().all())

    def create_user(self, *, email: str, password: str, role: UserRole, acting_admin: User) -> User:
        existing = self.db.execute(select(User).where(User.email == email.lower())).scalar_one_or_none()
        if existing:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User already exists.")
        user = User(email=email.lower(), password_hash=hash_secret(password), role=role)
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        self.logger.log(
            actor_type="admin",
            actor_id=str(acting_admin.id),
            event_type="user_create",
            status=SecurityEventStatus.success,
            detail=f"Created account {user.email}.",
        )
        return user

    def update_user(
        self,
        *,
        user: User,
        acting_admin: User,
        email: str | None = None,
        password: str | None = None,
        role: UserRole | None = None,
    ) -> User:
        if email and email.lower() != user.email:
            exists = self.db.execute(select(User).where(User.email == email.lower(), User.id != user.id)).first()
            if exists:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="E-mail already in use.")
            user.email = email.lower()
        if password:
            user.password_hash = hash_secret(password)
        if role:
            user.role = role
        self.db.commit()
        self.db.refresh(user)
        self.logger.log(
            actor_type="admin",
            actor_id=str(acting_admin.id),
            event_type="user_update",
            status=SecurityEventStatus.success,
            detail=f"Updated account {user.email}.",
        )
        return user

    def delete_user(self, *, user: User, acting_admin: User) -> int:
        if user.id == acting_admin.id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Administrator cannot delete self.")
        user_id = user.id
        self.db.delete(user)
        self.db.commit()
        self.logger.log(
            actor_type="admin",
            actor_id=str(acting_admin.id),
            event_type="user_delete",
            status=SecurityEventStatus.success,
            detail=f"Removed account {user.email}.",
        )
        return user_id
