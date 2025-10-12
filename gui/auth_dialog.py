"""Okno logowania / rejestracji."""

from __future__ import annotations

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QCursor, QFont
from PyQt5.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QGridLayout,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    QVBoxLayout,
    QWidget,
)

from .api_client import ApiClient, ApiError


class AuthDialog(QDialog):
    """Dialog logowania i rejestracji inspirowany projektem referencyjnym."""

    def __init__(self, api_client: ApiClient, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.api_client = api_client
        self.mode: str = "login"
        self._busy = False

        self.setWindowTitle("Panel logowania – System IoT")
        self.setModal(True)
        self.setMinimumSize(820, 520)
        self.setAttribute(Qt.WA_StyledBackground, True)

        self._apply_styles()
        self._build_ui()

    def _apply_styles(self) -> None:
        """Globalny arkusz stylów dla dialogu."""
        self.setStyleSheet(
            """
            QDialog {
                background-color: #0f172a;
                background-image: qlineargradient(
                    x1:0, y1:0, x2:1, y2:1,
                    stop:0 #0f172a,
                    stop:1 #1e293b
                );
                color: #0f172a;
                font-family: 'Segoe UI', 'Arial', sans-serif;
                font-size: 14px;
            }
            #card {
                background-color: #f8fafc;
                border-radius: 18px;
            }
            #sidePanel {
                background-image: qlineargradient(
                    x1:0, y1:0, x2:1, y2:1,
                    stop:0 #2563eb,
                    stop:1 #0891b2
                );
                border-top-left-radius: 18px;
                border-bottom-left-radius: 18px;
            }
            #sidePanel QLabel {
                color: #f8fafc;
            }
            #badgeLabel {
                background-color: rgba(15, 23, 42, 0.55);
                border-radius: 12px;
                padding: 6px 12px;
                font-size: 12px;
                letter-spacing: 0.12em;
                text-transform: uppercase;
            }
            #sideTitle {
                font-size: 22px;
                font-weight: 600;
                line-height: 1.2;
            }
            QLabel[role="feature"] {
                color: rgba(248, 250, 252, 0.9);
                font-size: 13px;
            }
            #formPanel {
                border-top-right-radius: 18px;
                border-bottom-right-radius: 18px;
            }
            #formTitle {
                font-size: 26px;
                font-weight: 600;
                color: #0f172a;
            }
            #formSubtitle {
                color: #64748b;
                font-size: 13px;
                margin-bottom: 4px;
            }
            QLabel#fieldLabel {
                font-weight: 600;
                color: #1e293b;
            }
            QLineEdit {
                background-color: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 12px;
                padding: 10px 14px;
                selection-background-color: #2563eb;
            }
            QLineEdit:focus {
                border: 1px solid #2563eb;
            }
            QPushButton#primaryButton {
                background-color: #2563eb;
                color: #f8fafc;
                border: none;
                border-radius: 12px;
                padding: 12px;
                font-weight: 600;
                letter-spacing: 0.02em;
            }
            QPushButton#primaryButton:hover {
                background-color: #1d4ed8;
            }
            QPushButton#primaryButton:pressed {
                background-color: #1e40af;
            }
            QPushButton#primaryButton:disabled {
                background-color: #94a3b8;
            }
            QPushButton#linkButton {
                color: #2563eb;
                background-color: transparent;
                border: none;
                font-weight: 500;
            }
            QPushButton#linkButton:hover {
                text-decoration: underline;
            }
            QLabel#errorLabel {
                color: #dc2626;
                background-color: rgba(220, 38, 38, 0.08);
                border-radius: 10px;
                padding: 10px 14px;
            }
            QLabel#footerLabel {
                color: #94a3b8;
                font-size: 12px;
            }
            """
        )

    def _build_ui(self) -> None:
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(48, 48, 48, 48)
        outer_layout.setSpacing(0)

        card = QFrame()
        card.setObjectName("card")
        card.setMinimumWidth(780)
        card_layout = QHBoxLayout(card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(52)
        shadow.setOffset(0, 24)
        shadow.setColor(QColor(15, 23, 42, 120))
        card.setGraphicsEffect(shadow)

        outer_layout.addStretch(1)
        outer_layout.addWidget(card, 0, Qt.AlignCenter)
        outer_layout.addStretch(1)

        side_panel = QFrame()
        side_panel.setObjectName("sidePanel")
        side_panel.setFixedWidth(320)
        side_layout = QVBoxLayout(side_panel)
        side_layout.setContentsMargins(36, 48, 36, 48)
        side_layout.setSpacing(18)

        badge = QLabel("Bezpieczeństwo")
        badge.setAlignment(Qt.AlignCenter)
        badge.setObjectName("badgeLabel")

        side_title = QLabel("System IoT klasy enterprise")
        side_title.setObjectName("sideTitle")
        side_title.setWordWrap(True)

        side_description = QLabel(
            "Zadbaj o stabilność sieci urządzeń i reaguj na incydenty zanim staną się krytyczne."
        )
        side_description.setWordWrap(True)
        side_description.setProperty("role", "feature")

        features = [
            "Monitorowanie 24/7 z inteligentnymi alertami.",
            "Automatyczna rotacja tokenów i kluczy.",
            "Jednolite zarządzanie zespołami i uprawnieniami.",
        ]

        side_layout.addWidget(badge, alignment=Qt.AlignLeft)
        side_layout.addSpacing(12)
        side_layout.addWidget(side_title)
        side_layout.addWidget(side_description)

        for feature in features:
            feature_label = QLabel(f"• {feature}")
            feature_label.setWordWrap(True)
            feature_label.setProperty("role", "feature")
            side_layout.addWidget(feature_label)

        side_layout.addSpacerItem(QSpacerItem(20, 20, QSizePolicy.Minimum, QSizePolicy.Expanding))

        side_footer = QLabel("Bezpieczna konsola do zarządzania flotą IoT.")
        side_footer.setWordWrap(True)
        side_footer.setProperty("role", "feature")
        side_footer.setAlignment(Qt.AlignLeft | Qt.AlignBottom)
        side_layout.addWidget(side_footer)

        form_panel = QFrame()
        form_panel.setObjectName("formPanel")
        form_layout = QVBoxLayout(form_panel)
        form_layout.setContentsMargins(48, 48, 48, 48)
        form_layout.setSpacing(18)

        self.title_label = QLabel("Witaj ponownie 👋")
        self.title_label.setObjectName("formTitle")

        self.subtitle_label = QLabel(
            "Zaloguj się, aby kontynuować pracę w konsoli bezpieczeństwa."
        )
        self.subtitle_label.setObjectName("formSubtitle")
        self.subtitle_label.setWordWrap(True)

        form_layout.addWidget(self.title_label)
        form_layout.addWidget(self.subtitle_label)

        self.error_label = QLabel("")
        self.error_label.setObjectName("errorLabel")
        self.error_label.hide()
        form_layout.addWidget(self.error_label)

        form_grid = QGridLayout()
        form_grid.setVerticalSpacing(14)
        form_grid.setHorizontalSpacing(16)

        email_label = QLabel("Adres e-mail")
        email_label.setObjectName("fieldLabel")
        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("jan.nowak@example.com")
        self.email_input.setClearButtonEnabled(True)

        password_label = QLabel("Hasło")
        password_label.setObjectName("fieldLabel")
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Wprowadź co najmniej 8 znaków")
        self.password_input.setEchoMode(QLineEdit.Password)

        form_grid.addWidget(email_label, 0, 0)
        form_grid.addWidget(self.email_input, 1, 0)
        form_grid.addWidget(password_label, 2, 0)
        form_grid.addWidget(self.password_input, 3, 0)

        form_layout.addLayout(form_grid)

        self.submit_button = QPushButton("Zaloguj się")
        self.submit_button.setObjectName("primaryButton")
        self.submit_button.setMinimumHeight(48)
        self.submit_button.setDefault(True)
        self.submit_button.clicked.connect(self._handle_submit)

        self.toggle_button = QPushButton("Nie masz konta? Zarejestruj się")
        self.toggle_button.setObjectName("linkButton")
        self.toggle_button.setCursor(QCursor(Qt.PointingHandCursor))
        self.toggle_button.clicked.connect(self._toggle_mode)

        form_layout.addWidget(self.submit_button)
        form_layout.addWidget(self.toggle_button, alignment=Qt.AlignCenter)

        footer = QLabel("Tokeny dostępu odświeżamy automatycznie w trakcie pracy aplikacji.")
        footer.setObjectName("footerLabel")
        footer.setWordWrap(True)
        footer.setAlignment(Qt.AlignLeft)

        form_layout.addStretch(1)
        form_layout.addWidget(footer)

        card_layout.addWidget(side_panel)
        card_layout.addWidget(form_panel, 1)

        # Spójny font bazowy dla pól edycyjnych.
        font = QFont("Segoe UI", 10)
        self.email_input.setFont(font)
        self.password_input.setFont(font)

    def _toggle_mode(self) -> None:
        self.mode = "register" if self.mode == "login" else "login"
        if self.mode == "login":
            self.submit_button.setText("Zaloguj się")
            self.toggle_button.setText("Nie masz konta? Zarejestruj się")
            self.title_label.setText("Witaj ponownie 👋")
            self.subtitle_label.setText(
                "Zaloguj się, aby kontynuować pracę w konsoli bezpieczeństwa."
            )
        else:
            self.submit_button.setText("Utwórz konto i zaloguj")
            self.toggle_button.setText("Masz już konto? Wróć do logowania")
            self.title_label.setText("Dołącz do systemu 🔐")
            self.subtitle_label.setText(
                "Utwórz konto, aby monitorować i chronić swoje urządzenia IoT."
            )
        self.error_label.hide()
        self.error_label.clear()
        self.password_input.clear()

    def _handle_submit(self) -> None:
        email = self.email_input.text().strip()
        password = self.password_input.text()

        if not email or not password:
            self._show_error("Uzupełnij adres e-mail oraz hasło.")
            return
        if len(password) < 8:
            self._show_error("Hasło powinno zawierać co najmniej 8 znaków.")
            return

        self._set_busy(True)
        try:
            if self.mode == "login":
                self.api_client.login(email, password)
            else:
                self.api_client.register(email, password)
                self.api_client.login(email, password)
                QMessageBox.information(
                    self,
                    "Rejestracja zakończona",
                    "Utworzono konto i zalogowano użytkownika.",
                )
        except ApiError as exc:
            self._show_error(exc.detail or "Operacja nie powiodła się.")
            return
        finally:
            self._set_busy(False)

        self.accept()

    def _show_error(self, message: str) -> None:
        self.error_label.setText(message)
        self.error_label.show()

    def _set_busy(self, busy: bool) -> None:
        self.submit_button.setEnabled(not busy)
        QApplication.processEvents()
        if busy and not self._busy:
            QApplication.setOverrideCursor(QCursor(Qt.WaitCursor))
            self._busy = True
        elif not busy and self._busy:
            QApplication.restoreOverrideCursor()
            self._busy = False
