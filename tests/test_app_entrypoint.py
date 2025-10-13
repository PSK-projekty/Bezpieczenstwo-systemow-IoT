from types import SimpleNamespace

import pytest
import runpy
from PyQt5.QtWidgets import QDialog

import gui.app as gui_app


def test_run_app_success(monkeypatch):
    class _FakeApp:
        def setApplicationName(self, name: str) -> None:  # noqa: D401
            self.name = name

        def exec_(self) -> int:
            return 0

    class _FakeDialog:
        Accepted = QDialog.Accepted

        def __init__(self, client):
            self.client = client

        def exec_(self) -> int:
            return self.Accepted

    shown = {}

    class _FakeWindow:
        def __init__(self, client):
            self.client = client

        def show(self) -> None:
            shown["called"] = True

    client = SimpleNamespace(user_session=SimpleNamespace(email="admin@example.com", role="admin"))

    exit_codes: list[int] = []

    def fake_exit(code: int = 0) -> None:
        exit_codes.append(code)
        raise SystemExit(code)

    monkeypatch.setattr(gui_app, "QApplication", lambda argv: _FakeApp())
    monkeypatch.setattr(gui_app, "ApiClient", lambda: client)
    monkeypatch.setattr(gui_app, "AuthDialog", _FakeDialog)
    monkeypatch.setattr(gui_app, "MainWindow", _FakeWindow)
    monkeypatch.setattr(gui_app.sys, "exit", fake_exit)

    with pytest.raises(SystemExit):
        gui_app.run_app()

    assert shown["called"] is True
    assert exit_codes[-1] == 0


def test_run_app_missing_session(monkeypatch):
    critical_messages = []

    class _FakeApp:
        def setApplicationName(self, _: str) -> None:
            pass

        def exec_(self) -> int:
            return 0

    class _FakeDialog:
        Accepted = QDialog.Accepted

        def __init__(self, client):
            self.client = client

        def exec_(self) -> int:
            return self.Accepted

    client = SimpleNamespace(user_session=None)

    exit_codes: list[int] = []

    def fake_exit(code: int = 0) -> None:
        exit_codes.append(code)
        raise SystemExit(code)

    monkeypatch.setattr(gui_app, "QApplication", lambda argv: _FakeApp())
    monkeypatch.setattr(gui_app, "ApiClient", lambda: client)
    monkeypatch.setattr(gui_app, "AuthDialog", _FakeDialog)
    monkeypatch.setattr(gui_app.QMessageBox, "critical", lambda *args: critical_messages.append(args[1:3]))
    monkeypatch.setattr(gui_app.sys, "exit", fake_exit)

    with pytest.raises(SystemExit):
        gui_app.run_app()

    assert exit_codes[-1] == 1
    assert critical_messages


def test_main_guard_invokes_run_app(monkeypatch):
    called = []
    monkeypatch.setattr(gui_app, "run_app", lambda: called.append(True))

    runpy.run_module("gui.__main__", run_name="__main__")

    assert called == [True]
