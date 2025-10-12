from collections.abc import Callable

from sqlalchemy.orm import Session

from app.db.models import SecurityEvent, SecurityEventStatus


class SecurityLogger:
    """Prosty logger zdarzeń bezpieczeństwa przechowywany w bazie danych."""

    def __init__(self, session_factory: Callable[[], Session]):
        self._session_factory = session_factory

    def log(
        self,
        *,
        actor_type: str,
        event_type: str,
        status: SecurityEventStatus,
        actor_id: str | None = None,
        detail: str | None = None,
    ) -> None:
        """Dodaje wpis logu, przy zachowaniu odporności na błędy."""
        try:
            with self._session_factory() as db:
                entry = SecurityEvent(
                    actor_type=actor_type,
                    actor_id=actor_id,
                    event_type=event_type,
                    status=status,
                    detail=detail,
                )
                db.add(entry)
                db.commit()
        except Exception:
            # Nie chcemy zatrzymywać głównego przebiegu w razie błędu logowania.
            pass
