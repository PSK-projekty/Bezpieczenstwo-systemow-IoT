"""PyQt5 application entry point."""

from __future__ import annotations

import sys

from PyQt5.QtWidgets import QApplication, QMessageBox

from .api_client import ApiClient, ApiError
from .auth_dialog import AuthDialog
from .main_window import MainWindow


def run_app() -> None:
    """Start the desktop interface."""
    app = QApplication(sys.argv)
    app.setApplicationName("IoT Security Console")

    client = ApiClient()
    dialog = AuthDialog(client)
    if dialog.exec_() != AuthDialog.Accepted:
        sys.exit(0)

    if not client.user_session:
        QMessageBox.critical(None, "Session error", "Failed to create user session.")
        sys.exit(1)

    window = MainWindow(client)
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    try:
        run_app()
    except ApiError as exc:
        QMessageBox.critical(None, "Fatal error", exc.detail)
        sys.exit(1)
