from types import SimpleNamespace

import pytest
from PyQt5.QtWidgets import QDialog, QFileDialog, QMessageBox

from gui.main_window import MainWindow


class _StubApiClient:
    def __init__(self) -> None:
        self.user_session = SimpleNamespace(email="admin@example.com", role="admin")
        self.devices = [
            {"id": "dev-1", "name": "Door lock", "status": "active"},
        ]

    # device categories / devices
    def get_device_categories(self):
        return [
            {
                "name": "Smart lock",
                "slug": "smart_lock",
                "description": "Controls access.",
                "sample_payload": {"status": "locked", "metrics": {"battery_pct": 98}},
                "default_name": "Front door",
            }
        ]

    def get_devices(self):
        return self.devices

    def get_device(self, device_id: str):
        return {
            "id": device_id,
            "name": "Door lock",
            "category": "smart_lock",
            "created_at": "2024-01-01T00:00:00Z",
            "last_reading_at": "2024-01-01T01:00:00Z",
        }

    def get_readings(self, device_id: str, **_kwargs):
        return [
            {
                "id": 1,
                "received_at": "2024-01-01T00:00:00Z",
                "device_timestamp": "2024-01-01T00:00:00Z",
                "payload": {"status": "locked", "metrics": {"battery_pct": 97.5}},
                "payload_size": 128,
            },
            {
                "id": 2,
                "received_at": "2024-01-01T00:05:00Z",
                "device_timestamp": "2024-01-01T00:05:00Z",
                "payload": {"status": "locked", "metrics": {"battery_pct": 97.0}},
                "payload_size": 128,
            },
        ]

    def get_readings_meta(self, device_id: str, **_kwargs):
        return {"total_readings": 2, "latest_received_at": "2024-01-01T00:05:00Z"}

    # admin endpoints
    def list_users(self):
        return [
            {"id": 1, "email": "admin@example.com", "role": "admin", "created_at": "2024-01-01T00:00:00Z"}
        ]

    def get_security_events(self, limit: int = 100):
        return [
            {
                "created_at": "2024-01-01T00:00:00Z",
                "actor_type": "user",
                "actor_id": "1",
                "event_type": "login",
                "status": "success",
                "detail": "Accepted",
            }
        ]

    def simulate_security_event(self, scenario: str, note: str | None = None):
        return {"detail": f"{scenario}:{note or 'none'}"}

    # placeholders used by actions but not exercised
    def rotate_device_secret(self, device_id: str):
        return {"device_id": device_id, "device_secret": "secret"}

    def create_device(self, name: str, category: str):
        device_id = f"dev-{len(self.devices) + 1}"
        self.devices.append({"id": device_id, "name": name, "status": "active"})
        return {"device_id": device_id, "device_secret": "temp"}

    def delete_device(self, device_id: str):
        self.devices = [d for d in self.devices if d["id"] != device_id]
        return {}

    def create_user(self, email: str, password: str, role: str):
        return {"id": 2, "email": email, "role": role}

    def update_user(self, user_id: int, **fields):
        return {"id": user_id, **fields}

    def delete_user(self, user_id: int):
        return None


@pytest.mark.usefixtures("qtbot")
def test_main_window_builds_pages(qtbot) -> None:
    api_client = _StubApiClient()
    window = MainWindow(api_client)
    qtbot.addWidget(window)

    # Devices tab should list our stub device after initial refresh
    devices_page = window.devices_page
    assert devices_page.device_list.count() == 1
    devices_page.device_list.setCurrentRow(0)
    devices_page._reload_current_readings()
    assert devices_page.readings_table.rowCount() == 2
    assert "Lacznie odczytow" in devices_page.meta_total.text()

    # Users tab available for admin session
    users_page = window.users_page
    assert users_page.table.rowCount() == 1

    # Security events tab fetches events
    events_page = window.events_page
    assert events_page.table.rowCount() == 1
    events_page.note_input.setText("test")
    events_page._simulate_event()
    assert events_page.note_input.text() == ""


def test_devices_and_users_actions(qtbot, monkeypatch, tmp_path) -> None:
    api_client = _StubApiClient()
    window = MainWindow(api_client)
    qtbot.addWidget(window)

    devices_page = window.devices_page
    devices_page.current_device_id = "dev-1"

    # Mock device creation dialog
    class _FakeDeviceDialog:
        def __init__(self, categories, parent=None):
            self._categories = categories

        def exec_(self) -> int:
            return QDialog.Accepted

        def payload(self):
            return ("Nowe urzadzenie", "smart_lock")

    info_calls = []
    monkeypatch.setattr("gui.main_window.DeviceCreateDialog", _FakeDeviceDialog)
    monkeypatch.setattr("gui.main_window.QMessageBox.information", lambda *args, **kwargs: info_calls.append(args[1:3]))
    devices_page._create_device()
    assert any("Sekret urzadzenia" in title for title, *_ in info_calls)

    # Rotate secret / delete actions
    monkeypatch.setattr("gui.main_window.QMessageBox.question", lambda *args, **kwargs: QMessageBox.Yes)
    devices_page._rotate_secret()
    devices_page._delete_device()

    # Export flows
    export_path = tmp_path / "readings.csv"
    monkeypatch.setattr(
        "gui.main_window.QFileDialog.getSaveFileName",
        lambda *args, **kwargs: (str(export_path), "CSV"),
    )
    devices_page._export_readings()
    assert export_path.exists()

    txt_path = tmp_path / "readings.txt"
    monkeypatch.setattr(
        "gui.main_window.QFileDialog.getSaveFileName",
        lambda *args, **kwargs: (str(txt_path), "TXT"),
    )
    devices_page._export_readings_txt()
    assert txt_path.exists()

    # Users actions
    users_page = window.users_page
    users_page.table.selectRow(0)

    class _FakeUserDialog:
        def __init__(self, *args, **kwargs):
            pass

        def exec_(self) -> int:
            return QDialog.Accepted

        def payload(self):
            return "nowy@example.com", "Haslo123!", "user"

    monkeypatch.setattr("gui.main_window.UserDialog", _FakeUserDialog)
    users_page._create_user()
    users_page._edit_user()
    users_page._delete_user()
