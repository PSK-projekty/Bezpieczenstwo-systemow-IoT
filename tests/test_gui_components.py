from types import SimpleNamespace

import pytest
from PyQt5.QtWidgets import QMessageBox

from gui.auth_dialog import AuthDialog
from gui.main_window import DeviceCreateDialog


@pytest.fixture
def sample_categories() -> list[dict]:
    return [
        {
            "name": "Weather station",
            "description": "Outdoor readings every 5 minutes.",
            "sample_payload": {"status": "outdoor", "metrics": {"temperature_c": 21.5}},
            "default_name": "Stacja dach",
            "slug": "weather_station",
        },
        {
            "name": "Smart lock",
            "description": "Controls door access.",
            "sample_payload": {"status": "locked", "metrics": {"battery_pct": 98}},
            "default_name": "Wejscie frontowe",
            "slug": "smart_lock",
        },
    ]


def test_device_create_dialog_updates_details(qtbot, sample_categories) -> None:
    dialog = DeviceCreateDialog(sample_categories, None)
    qtbot.addWidget(dialog)

    dialog.list_widget.setCurrentRow(1)
    qtbot.waitUntil(lambda: dialog.title_label.text() == "Smart lock", timeout=1000)

    assert "Controls door access" in dialog.description_label.text()
    qtbot.waitUntil(lambda: not dialog.slug_badge.isHidden(), timeout=1000)
    assert dialog.slug_badge.text() == "Smart Lock"
    assert dialog.name_input.text() == "Wejscie frontowe"

    name, slug = dialog.payload()
    assert slug == "smart_lock"
    assert name == "Wejscie frontowe"


def test_device_create_dialog_validation_requires_name(qtbot, sample_categories, monkeypatch) -> None:
    dialog = DeviceCreateDialog(sample_categories, None)
    qtbot.addWidget(dialog)
    warnings: list[str] = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: warnings.append(args[2]))  # type: ignore[index]

    dialog.list_widget.setCurrentRow(0)
    dialog.name_input.clear()
    dialog._selected = sample_categories[0]
    dialog._accept()

    assert warnings
    assert "nazw" in warnings[0].lower()

    accepted = {}
    dialog.accept = lambda: accepted.setdefault("ok", True)
    dialog.name_input.setText("Nowa stacja")
    dialog._accept()
    assert accepted.get("ok")


class _DummyApiClient:
    def __init__(self) -> None:
        self.login_called: list[tuple[str, str]] = []
        self.register_called: list[tuple[str, str]] = []

    def login(self, email: str, password: str) -> None:
        self.login_called.append((email, password))

    def register(self, email: str, password: str) -> None:
        self.register_called.append((email, password))


def test_auth_dialog_error_states(qtbot, monkeypatch) -> None:
    api = _DummyApiClient()
    dialog = AuthDialog(api)
    qtbot.addWidget(dialog)
    monkeypatch.setattr(QMessageBox, "information", lambda *args, **kwargs: None)

    dialog.email_input.clear()
    dialog.password_input.clear()
    dialog._handle_submit()
    qtbot.waitUntil(lambda: not dialog.error_container.isHidden(), timeout=1000)
    assert dialog.email_input.property("invalid") is True
    assert dialog.password_input.property("invalid") is True
    assert not api.login_called

    dialog.email_input.setText("user@example.com")
    dialog.password_input.setText("short")
    dialog._handle_submit()
    qtbot.waitUntil(lambda: not dialog.error_container.isHidden(), timeout=1000)
    assert "8" in dialog.error_label.text()

    dialog.password_input.setText("CorrectHorseBatteryStaple")
    assert dialog.error_container.isHidden()
    assert dialog.email_input.property("invalid") is False
    assert dialog.password_input.property("invalid") is False

    dialog._toggle_mode()
    dialog.email_input.setText("new@example.com")
    dialog.password_input.setText("Password123!")
    dialog._handle_submit()

    assert api.register_called == [("new@example.com", "Password123!")]
    assert not dialog.error_container.isVisible()
