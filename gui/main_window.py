"""Glowne okno aplikacji PyQt5."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QStatusBar,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .api_client import ApiClient, ApiError

DEFAULT_LEGEND_TEXT = "Legenda: wybierz urzadzenie, aby zobaczyc opis parametrow kategorii."

CATEGORY_LEGENDS: dict[str, dict[str, Any]] = {
    "weather_station": {
        "label": "Stacja pogodowa",
        "items": [
            ("Status", "Tryb pracy czujnika (np. outdoor)."),
            ("temperature_c", "Temperatura powietrza w stopniach Celsjusza."),
            ("humidity_pct", "Wilgotnosc wzgledna w procentach."),
            ("wind_speed_ms", "Predkosc wiatru mierzona w metrach na sekunde."),
            ("pressure_hpa", "Cisnienie atmosferyczne w hektopaskalach."),
            ("rainfall_mm", "Opad zanotowany od ostatniego odczytu w milimetrach."),
            ("uv_index", "Indeks natezenia promieniowania UV."),
        ],
    },
    "indoor_thermometer": {
        "label": "Termometr wewnetrzny",
        "items": [
            ("Status", "Pozycja urzadzenia (np. indoor)."),
            ("temperature_c", "Temperatura otoczenia w stopniach Celsjusza."),
            ("humidity_pct", "Wilgotnosc powietrza w procentach."),
            ("comfort_index", "Wskaznik komfortu liczony na podstawie temperatury i wilgotnosci."),
        ],
    },
    "ip_camera": {
        "label": "Kamera IP",
        "items": [
            ("Status", "Stan detekcji ruchu (idle lub motion_detected)."),
            ("bitrate_mbps", "Srednia przeplywnosc strumienia w megabitach na sekunde."),
            ("latency_ms", "Opoznienie polaczenia w milisekundach."),
            ("packet_loss_pct", "Procent utraconych pakietow sieciowych."),
        ],
    },
    "air_quality": {
        "label": "Czujnik jakosci powietrza",
        "items": [
            ("Status", "Ogólna ocena jakosci powietrza (np. good)."),
            ("pm2_5", "Stezenie pylu zawieszonego PM2.5 w mikrogramach na metr szescienny."),
            ("pm10", "Stezenie pylu PM10 w mikrogramach na metr szescienny."),
            ("co2_ppm", "Stezenie CO2 w czesciach na milion."),
            ("voc_ppb", "Stezenie lotnych zwiazkow organicznych w czesciach na miliard."),
        ],
    },
    "smart_lock": {
        "label": "Zamek inteligentny",
        "items": [
            ("Status", "Aktualny stan zamka (locked lub unlocked)."),
            ("battery_pct", "Przewidywany poziom baterii w procentach."),
            ("jam_detected", "Informacja o wykryciu próby sabotazu."),
            ("last_action", "Szczegoly ostatniej akcji (uzytkownik, metoda, czas)."),
        ],
    },
}


class MessageMixin(QWidget):
    """Mieszanka zapewniajaca obsluge komunikatow i kursora zajetosci."""

    message_emitted = pyqtSignal(str, str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._busy_depth = 0

    def emit_message(self, level: str, text: str) -> None:
        self.message_emitted.emit(level, text)

    def busy_cursor(self, enable: bool) -> None:
        if enable:
            if self._busy_depth == 0:
                QApplication.setOverrideCursor(Qt.WaitCursor)
            self._busy_depth += 1
        else:
            if self._busy_depth > 0:
                self._busy_depth -= 1
                if self._busy_depth == 0:
                    QApplication.restoreOverrideCursor()


class DeviceCreateDialog(QDialog):
    """Dialog wyboru kategorii urzadzenia."""

    def __init__(self, categories: list[dict[str, Any]], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Dodaj urzadzenie")
        self.setModal(True)
        self.resize(640, 420)
        self._categories = categories
        self._selected: dict[str, Any] | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        self.setStyleSheet(
            """
            QDialog {
                background-color: #e2e8f0;
                font-family: "Segoe UI", Arial, sans-serif;
                color: #0f172a;
            }
            QListWidget#categoryList {
                background-color: #f1f5f9;
                border: 1px solid #cbd5f5;
                border-radius: 16px;
                padding: 12px 8px;
            }
            QListWidget#categoryList::item {
                padding: 10px 12px;
                margin: 2px 0;
                border-radius: 10px;
            }
            QListWidget#categoryList::item:selected {
                background-color: #2563eb;
                color: #ffffff;
            }
            QWidget#detailsCard {
                background-color: #ffffff;
                border: 1px solid #cbd5f5;
                border-radius: 18px;
            }
            QLabel#dialogSubtitle {
                color: #475569;
            }
            QLabel#categoryBadge {
                padding: 6px 12px;
                border-radius: 12px;
                background-color: #e0e7ff;
                color: #1e3a8a;
                font-weight: 600;
                max-width: 220px;
            }
            QTextEdit#payloadPreview {
                background-color: #f8fafc;
                border: 1px solid #cbd5f5;
                border-radius: 14px;
                padding: 10px;
            }
            QLineEdit {
                background-color: #f8fafc;
                border: 1px solid #cbd5f5;
                border-radius: 14px;
                padding: 10px 12px;
            }
            QPushButton {
                border-radius: 16px;
                padding: 10px 18px;
                font-weight: 600;
            }
            QPushButton#cancelButton {
                background-color: #f1f5f9;
                color: #1e293b;
                border: 1px solid #cbd5f5;
            }
            QPushButton#cancelButton:hover {
                background-color: #e2e8f0;
            }
            QPushButton#primaryButton {
                background-color: #2563eb;
                color: #f8fafc;
                border: none;
            }
            QPushButton#primaryButton:hover {
                background-color: #1d4ed8;
            }
            QPushButton#primaryButton:disabled {
                background-color: #cbd5f5;
                color: #94a3b8;
            }
            """
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(20)

        self.list_widget = QListWidget()
        self.list_widget.setObjectName("categoryList")
        self.list_widget.setFixedWidth(220)
        for category in self._categories:
            item = QListWidgetItem(category["name"])
            item.setData(Qt.UserRole, category)
            self.list_widget.addItem(item)
        self.list_widget.currentItemChanged.connect(self._on_selected)
        layout.addWidget(self.list_widget)

        self.details = QWidget()
        self.details.setObjectName("detailsCard")
        details_layout = QVBoxLayout(self.details)
        details_layout.setContentsMargins(28, 28, 28, 28)
        details_layout.setSpacing(18)

        self.title_label = QLabel("Wybierz kategorie")
        self.title_label.setFont(QFont("Segoe UI Semibold", 14))
        details_layout.addWidget(self.title_label)

        self.description_label = QLabel("Zaznacz kategorie po lewej stronie, aby zobaczyc szczegoly.")
        self.description_label.setObjectName("dialogSubtitle")
        self.description_label.setWordWrap(True)
        details_layout.addWidget(self.description_label)

        self.slug_badge = QLabel(" ")
        self.slug_badge.setObjectName("categoryBadge")
        self.slug_badge.hide()
        details_layout.addWidget(self.slug_badge)

        self.sample_payload = QTextEdit()
        self.sample_payload.setObjectName("payloadPreview")
        self.sample_payload.setReadOnly(True)
        self.sample_payload.setFixedHeight(150)
        details_layout.addWidget(self.sample_payload)

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(10)
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("np. Stacja pogodowa na dachu")
        form.addRow("Nazwa urzadzenia", self.name_input)
        details_layout.addLayout(form)
        details_layout.addStretch(1)

        button_row = QHBoxLayout()
        button_row.setSpacing(12)
        button_row.addStretch(1)
        cancel_btn = QPushButton("Anuluj")
        cancel_btn.setObjectName("cancelButton")
        cancel_btn.clicked.connect(self.reject)
        create_btn = QPushButton("Utworz")
        create_btn.setObjectName("primaryButton")
        create_btn.clicked.connect(self._accept)
        button_row.addWidget(cancel_btn)
        button_row.addWidget(create_btn)
        details_layout.addLayout(button_row)

        layout.addWidget(self.details, stretch=1)

        if self.list_widget.count() > 0:
            self.list_widget.setCurrentRow(0)

    def _on_selected(self, current: QListWidgetItem | None, previous: QListWidgetItem | None) -> None:
        if not current:
            return
        category = current.data(Qt.UserRole)
        self._selected = category
        self.title_label.setText(category["name"])
        self.description_label.setText(category["description"])
        slug = category.get("slug") or ""
        if slug:
            self.slug_badge.setText(slug.replace("_", " ").title())
            self.slug_badge.show()
        else:
            self.slug_badge.hide()
        pretty_payload = json.dumps(category["sample_payload"], indent=2, ensure_ascii=False)
        self.sample_payload.setPlainText(pretty_payload)
        self.name_input.setText(category["default_name"])

    def _accept(self) -> None:
        if not self._selected:
            QMessageBox.warning(self, "Wymagany wybor", "Najpierw wybierz kategorie urzadzenia.")
            return
        if not self.name_input.text().strip():
            QMessageBox.warning(self, "Brak nazwy", "Wpisz nazwe urzadzenia.")
            return
        self.accept()

    def payload(self) -> tuple[str, str] | None:
        if not self._selected:
            return None
        return self.name_input.text().strip(), self._selected["slug"]

class DevicesPage(MessageMixin):
    """Widok zarzadzania urzadzeniami oraz danymi telemetrycznymi."""

    def __init__(self, api_client: ApiClient, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.api_client = api_client
        self.categories: list[dict[str, Any]] = []
        self.devices: list[dict[str, Any]] = []
        self.current_device_id: str | None = None
        self._build_ui()
        self._load_categories()
        self.refresh_devices()

    def _build_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(16)

        header = QLabel("Urzadzenia")
        header.setFont(QFont("Segoe UI Semibold", 18))
        main_layout.addWidget(header)

        top_area = QHBoxLayout()
        top_area.setSpacing(20)
        main_layout.addLayout(top_area)

        self.device_list = QListWidget()
        self.device_list.setMinimumWidth(260)
        self.device_list.setStyleSheet(
            """
            QListWidget {
                background-color: #ffffff;
                border: 1px solid #cbd5f5;
                border-radius: 12px;
                padding: 6px;
            }
            QListWidget::item {
                padding: 8px 10px;
                border-radius: 8px;
            }
            QListWidget::item:selected {
                background-color: #2563eb;
                color: #ffffff;
            }
            """
        )
        self.device_list.currentItemChanged.connect(self._on_device_selected)

        list_zone = QVBoxLayout()
        list_zone.addWidget(self.device_list)

        button_bar = QGridLayout()
        button_bar.setHorizontalSpacing(10)
        button_bar.setVerticalSpacing(10)

        self.add_button = QPushButton("Dodaj urzadzenie")
        self.add_button.setCursor(Qt.PointingHandCursor)
        self.add_button.clicked.connect(self._create_device)
        self.refresh_button = QPushButton("Odswiez")
        self.refresh_button.setCursor(Qt.PointingHandCursor)
        self.refresh_button.clicked.connect(self.refresh_devices)
        self.delete_button = QPushButton("Usun urzadzenie")
        self.delete_button.setCursor(Qt.PointingHandCursor)
        self.delete_button.clicked.connect(self._delete_device)
        self.rotate_button = QPushButton("Rotuj sekret")
        self.rotate_button.setCursor(Qt.PointingHandCursor)
        self.rotate_button.clicked.connect(self._rotate_secret)

        for btn in (self.add_button, self.refresh_button, self.delete_button, self.rotate_button):
            btn.setStyleSheet(
                """
                QPushButton {
                    background-color: #2563eb;
                    color: #f8fafc;
                    border: none;
                    border-radius: 10px;
                    padding: 8px 12px;
                }
                QPushButton:hover {
                    background-color: #1d4ed8;
                }
                QPushButton:disabled {
                    background-color: #cbd5f5;
                    color: #7c8dae;
                }
                """
            )

        button_bar.addWidget(self.add_button, 0, 0)
        button_bar.addWidget(self.refresh_button, 0, 1)
        button_bar.addWidget(self.delete_button, 1, 0)
        button_bar.addWidget(self.rotate_button, 1, 1)
        list_zone.addLayout(button_bar)

        top_area.addLayout(list_zone, stretch=0)

        details_layout = QVBoxLayout()
        details_layout.setSpacing(12)
        top_area.addLayout(details_layout, stretch=1)

        self.name_label = QLabel("Wybierz urzadzenie, aby zobaczyc szczegoly.")
        self.name_label.setFont(QFont("Segoe UI Semibold", 14))
        details_layout.addWidget(self.name_label)

        info_grid = QGridLayout()
        info_grid.setHorizontalSpacing(16)
        info_grid.setVerticalSpacing(6)
        self.category_label = QLabel("Kategoria: -")
        self.owner_label = QLabel("Wlasciciel: -")
        self.created_label = QLabel("Utworzono: -")
        self.last_reading_label = QLabel("Ostatni odczyt: -")
        for label in (self.category_label, self.owner_label, self.created_label, self.last_reading_label):
            label.setStyleSheet("color: #1f2937;")
        info_grid.addWidget(self.category_label, 0, 0)
        info_grid.addWidget(self.owner_label, 0, 1)
        info_grid.addWidget(self.created_label, 1, 0)
        info_grid.addWidget(self.last_reading_label, 1, 1)
        details_layout.addLayout(info_grid)

        filters = QHBoxLayout()
        filters.setSpacing(10)
        self.limit_input = QSpinBox()
        self.limit_input.setRange(1, 500)
        self.limit_input.setValue(100)
        self.limit_input.setStyleSheet("QSpinBox { border: 1px solid #cbd5f5; border-radius: 8px; padding: 4px 8px; }")
        filters.addWidget(QLabel("Limit"))
        filters.addWidget(self.limit_input)
        self.since_input = QLineEdit()
        self.since_input.setPlaceholderText("od (ISO 8601)")
        self.since_input.setStyleSheet("QLineEdit { border: 1px solid #cbd5f5; border-radius: 8px; padding: 6px 10px; }")
        filters.addWidget(self.since_input)
        self.until_input = QLineEdit()
        self.until_input.setPlaceholderText("do (ISO 8601)")
        self.until_input.setStyleSheet("QLineEdit { border: 1px solid #cbd5f5; border-radius: 8px; padding: 6px 10px; }")
        filters.addWidget(self.until_input)
        self.filter_button = QPushButton("Filtruj")
        self.filter_button.setCursor(Qt.PointingHandCursor)
        self.filter_button.setStyleSheet(
            "QPushButton { background-color: #2563eb; color: #f8fafc; border-radius: 10px; padding: 8px 12px; }"
            "QPushButton:hover { background-color: #1d4ed8; }"
        )
        self.filter_button.clicked.connect(self._reload_current_readings)
        filters.addWidget(self.filter_button)
        self.export_button = QPushButton("Eksportuj CSV")
        self.export_button.setCursor(Qt.PointingHandCursor)
        self.export_button.setStyleSheet(
            "QPushButton { background-color: #2563eb; color: #f8fafc; border-radius: 10px; padding: 8px 12px; }"
            "QPushButton:hover { background-color: #1d4ed8; }"
        )
        self.export_button.clicked.connect(self._export_readings)
        filters.addWidget(self.export_button)
        self.export_txt_button = QPushButton("Eksportuj TXT")
        self.export_txt_button.setCursor(Qt.PointingHandCursor)
        self.export_txt_button.setStyleSheet(
            "QPushButton { background-color: #2563eb; color: #f8fafc; border-radius: 10px; padding: 8px 12px; }"
            "QPushButton:hover { background-color: #1d4ed8; }"
        )
        self.export_txt_button.clicked.connect(self._export_readings_txt)
        filters.addWidget(self.export_txt_button)
        filters.addStretch(1)
        details_layout.addLayout(filters)

        self.readings_table = QTableWidget(0, 0)
        self.readings_table.horizontalHeader().setStretchLastSection(True)
        self.readings_table.verticalHeader().setVisible(False)
        self.readings_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.readings_table.setAlternatingRowColors(True)
        self.readings_table.setStyleSheet(
            """
            QTableWidget {
                background-color: #ffffff;
                alternate-background-color: #f8fafc;
                gridline-color: #cbd5e1;
                color: #0f172a;
            }
            QHeaderView::section {
                background-color: #e2e8f0;
                font-weight: 600;
                padding: 6px;
                border: none;
            }
            """
        )
        details_layout.addWidget(self.readings_table, stretch=1)

        self.meta_total = QLabel("Lacznie odczytow: -")
        self.meta_total.setStyleSheet("color: #334155; font-weight: 600;")
        details_layout.addWidget(self.meta_total, alignment=Qt.AlignRight)

        self.table_hint = QLabel(
            "Kolumny stale: Odebrano (czas zapisu), Znacznik urzadzenia (czas z czujnika), "
            "opcjonalny Status oraz metryki specyficzne dla kategorii."
        )
        self.table_hint.setStyleSheet("color: #475569; font-size: 12px;")
        self.table_hint.setWordWrap(True)
        details_layout.addWidget(self.table_hint)

        self.legend_title = QLabel("Legenda kategorii")
        self.legend_title.setStyleSheet("color: #1f2937; font-weight: 600;")
        details_layout.addWidget(self.legend_title)

        self.legend_body = QLabel(DEFAULT_LEGEND_TEXT)
        self.legend_body.setWordWrap(True)
        self.legend_body.setStyleSheet(
            "color: #475569; font-size: 12px; background-color: #f1f5f9; border: 1px solid #cbd5e1; "
            "border-radius: 8px; padding: 10px;"
        )
        details_layout.addWidget(self.legend_body)

        main_layout.addStretch(1)
    def _load_categories(self) -> None:
        self.busy_cursor(True)
        try:
            self.categories = self.api_client.get_device_categories()
        except ApiError as exc:
            self.emit_message("error", exc.detail)
        finally:
            self.busy_cursor(False)

    def refresh_devices(self) -> None:
        self.busy_cursor(True)
        try:
            self.devices = self.api_client.get_devices()
            self.device_list.clear()
            for device in self.devices:
                entry = QListWidgetItem(f"{device['name']} - {device['status']}")
                entry.setData(Qt.UserRole, device)
                self.device_list.addItem(entry)
            if self.devices:
                self.device_list.setCurrentRow(0)
            else:
                self._clear_details()
            self.emit_message("info", f"Pobrano {len(self.devices)} urzadzen.")
        except ApiError as exc:
            self.emit_message("error", exc.detail)
        finally:
            self.busy_cursor(False)

    def _on_device_selected(self, current: QListWidgetItem | None, previous: QListWidgetItem | None) -> None:
        if not current:
            self._clear_details()
            return
        device = current.data(Qt.UserRole)
        self.current_device_id = device["id"]
        self._update_labels(device)
        self._reload_current_readings()

    def _clear_details(self) -> None:
        self.current_device_id = None
        self.name_label.setText("Wybierz urzadzenie, aby zobaczyc szczegoly.")
        self.category_label.setText("Kategoria: -")
        self.owner_label.setText("Wlasciciel: -")
        self.created_label.setText("Utworzono: -")
        self.last_reading_label.setText("Ostatni odczyt: -")
        self.readings_table.setRowCount(0)
        self.meta_total.setText("Lacznie odczytow: -")
        self._render_category_legend(None)

    def _update_labels(self, device: dict[str, Any]) -> None:
        detail = device
        try:
            detail = self.api_client.get_device(device["id"])
        except ApiError:
            pass
        self.name_label.setText(detail.get("name", device.get("name", "-")))
        category = next((c for c in self.categories if c["slug"] == detail.get("category")), None)
        self.category_label.setText(
            f"Kategoria: {category['name'] if category else detail.get('category', '-')}"
        )
        self.owner_label.setText("Wlasciciel: Ty")
        self.created_label.setText(f"Utworzono: {detail.get('created_at', '-')}")
        self.last_reading_label.setText(f"Ostatni odczyt: {detail.get('last_reading_at', '-')}")
        self._render_category_legend(detail.get("category"))

    def _render_category_legend(self, category_slug: str | None) -> None:
        if not category_slug:
            self.legend_title.setText("Legenda kategorii")
            self.legend_body.setText(DEFAULT_LEGEND_TEXT)
            return
        legend = CATEGORY_LEGENDS.get(str(category_slug))
        if not legend:
            self.legend_title.setText(f"Legenda: {category_slug}")
            self.legend_body.setText(
                "Brak zdefiniowanej legendy. Kolumny prezentuja surowe metryki przekazane przez urzadzenie."
            )
            return
        self.legend_title.setText(f"Legenda: {legend.get('label', category_slug)}")
        items = legend.get("items") or []
        if not items:
            self.legend_body.setText("Brak dodatkowych opisow metryk dla tej kategorii.")
            return
        lines = [f"<b>{name}</b> - {description}" for name, description in items]
        self.legend_body.setText("<br>".join(lines))

    def _reload_current_readings(self) -> None:
        if not self.current_device_id:
            return
        limit = self.limit_input.value()
        since = self.since_input.text().strip() or None
        until = self.until_input.text().strip() or None

        self.busy_cursor(True)
        try:
            readings = self.api_client.get_readings(
                self.current_device_id,
                limit=limit,
                since=since,
                until=until,
                include_simulated=True,
            )
            meta = self.api_client.get_readings_meta(
                self.current_device_id,
                since=since,
                until=until,
                include_simulated=True,
            )
        except ApiError as exc:
            self.busy_cursor(False)
            self.emit_message("error", exc.detail)
            return

        # Określ dynamiczne kolumny na podstawie widocznych metryk
        status_present = False
        metrics_keys: set[str] = set()
        normalized_payloads: list[dict[str, Any]] = []

        for reading in readings:
            payload = reading.get("payload") or {}
            if isinstance(payload, str):
                try:
                    payload = json.loads(payload)
                except json.JSONDecodeError:
                    payload = {}
            if isinstance(payload, dict):
                normalized_payloads.append(payload)
                if payload.get("status") is not None:
                    status_present = True
                metrics = payload.get("metrics")
                if isinstance(metrics, dict):
                    metrics_keys.update(metrics.keys())
            else:
                normalized_payloads.append({})

        metrics_keys_sorted = sorted(metrics_keys)

        headers = ["Odebrano", "Znacznik urzadzenia"]
        if status_present:
            headers.append("Status")
        headers.extend(metrics_keys_sorted)

        self.readings_table.setColumnCount(len(headers))
        self.readings_table.setHorizontalHeaderLabels(headers)

        self.readings_table.setRowCount(len(readings))
        for row, reading in enumerate(readings):
            payload = normalized_payloads[row]
            metrics = payload.get("metrics") if isinstance(payload, dict) else {}
            if not isinstance(metrics, dict):
                metrics = {}

            column = 0
            self.readings_table.setItem(row, column, QTableWidgetItem(self._fmt_ts(reading.get("received_at"))))
            column += 1
            self.readings_table.setItem(row, column, QTableWidgetItem(self._fmt_ts(reading.get("device_timestamp"))))
            column += 1

            if status_present:
                status_value = payload.get("status", "-") if isinstance(payload, dict) else "-"
                self.readings_table.setItem(row, column, QTableWidgetItem(str(status_value)))
                column += 1

            for key in metrics_keys_sorted:
                value = metrics.get(key, "-")
                if isinstance(value, (int, float)):
                    if isinstance(value, int):
                        formatted = str(value)
                    else:
                        formatted = f"{value:.2f}"
                else:
                    formatted = str(value)
                self.readings_table.setItem(row, column, QTableWidgetItem(formatted))
                column += 1

        self.meta_total.setText(
            f"Lacznie odczytow: {meta.get('total_readings', '-')} (ostatni: {self._fmt_ts(meta.get('latest_received_at'))})"
        )
        self.busy_cursor(False)

    @staticmethod
    def _fmt_ts(value: str | None) -> str:
        if not value:
            return "-"
        return value.replace("T", " ").replace("Z", "")

    def _create_device(self) -> None:
        if not self.categories:
            QMessageBox.warning(self, "Brak kategorii", "Serwer nie udostepnil listy kategorii urzadzen.")
            return
        dialog = DeviceCreateDialog(self.categories, self)
        if dialog.exec_() != QDialog.Accepted:
            return
        payload = dialog.payload()
        if not payload:
            return
        name, category = payload
        self.busy_cursor(True)
        try:
            response = self.api_client.create_device(name, category)
            self.emit_message("success", "Utworzono urzadzenie.")
            QMessageBox.information(
                self,
                "Sekret urzadzenia",
                f"Identyfikator: {response.get('device_id')}\nJednorazowy sekret: {response.get('device_secret')}"
            )
            self.refresh_devices()
        except ApiError as exc:
            self.emit_message("error", exc.detail)
        finally:
            self.busy_cursor(False)

    def _rotate_secret(self) -> None:
        if not self.current_device_id:
            return
        confirm = QMessageBox.question(
            self,
            "Rotacja sekretu",
            "Aktualne tokeny urzadzenia przestana dzialac. Kontynuowac?",
        )
        if confirm != QMessageBox.Yes:
            return
        self.busy_cursor(True)
        try:
            result = self.api_client.rotate_device_secret(self.current_device_id)
            self.emit_message("success", "Zrotowano sekret urzadzenia.")
            QMessageBox.information(
                self,
                "Nowy sekret",
                f"Identyfikator: {result.get('device_id')}\nNowy sekret: {result.get('device_secret')}"
            )
        except ApiError as exc:
            self.emit_message("error", exc.detail)
        finally:
            self.busy_cursor(False)

    def _delete_device(self) -> None:
        if not self.current_device_id:
            return
        confirm = QMessageBox.question(
            self,
            "Usun urzadzenie",
            "Operacja jest nieodwracalna. Czy na pewno chcesz usunac urzadzenie?",
        )
        if confirm != QMessageBox.Yes:
            return
        self.busy_cursor(True)
        try:
            self.api_client.delete_device(self.current_device_id)
            self.emit_message("success", "Usunieto urzadzenie.")
            self.refresh_devices()
        except ApiError as exc:
            self.emit_message("error", exc.detail)
        finally:
            self.busy_cursor(False)

    def _export_readings(self) -> None:
        if not self.current_device_id:
            return
        default_name = f"urzadzenie_{self.current_device_id}.csv"
        target, _ = QFileDialog.getSaveFileName(self, "Eksportuj dane urzadzenia", default_name, "CSV (*.csv)")
        if not target:
            return
        self.busy_cursor(True)
        try:
            readings = self.api_client.get_readings(
                self.current_device_id,
                limit=self.limit_input.value(),
                since=self.since_input.text().strip() or None,
                until=self.until_input.text().strip() or None,
                include_simulated=True,
            )
        except ApiError as exc:
            self.busy_cursor(False)
            self.emit_message("error", exc.detail)
            return

        try:
            with Path(target).open("w", encoding="utf-8", newline="") as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(["id", "received_at", "device_timestamp", "payload", "payload_size"])
                for reading in readings:
                    writer.writerow(
                        [
                            reading.get("id"),
                            reading.get("received_at"),
                            reading.get("device_timestamp"),
                            json.dumps(reading.get("payload"), ensure_ascii=False),
                            reading.get("payload_size"),
                        ]
                    )
            self.emit_message("success", f"Wyeksportowano {len(readings)} wierszy.")
        except OSError as exc:
            self.emit_message("error", f"Nie udalo sie zapisac pliku: {exc}")
        finally:
            self.busy_cursor(False)

    def _export_readings_txt(self) -> None:
        if not self.current_device_id:
            return
        default_name = f"urzadzenie_{self.current_device_id}.txt"
        target, _ = QFileDialog.getSaveFileName(self, "Zapisz raport tekstowy", default_name, "Plik tekstowy (*.txt)")
        if not target:
            return
        self.busy_cursor(True)
        try:
            readings = self.api_client.get_readings(
                self.current_device_id,
                limit=self.limit_input.value(),
                since=self.since_input.text().strip() or None,
                until=self.until_input.text().strip() or None,
                include_simulated=True,
            )
        except ApiError as exc:
            self.busy_cursor(False)
            self.emit_message("error", exc.detail)
            return

        lines: list[str] = []
        for index, reading in enumerate(readings, start=1):
            lines.append(f"Odczyt #{index}")
            lines.append(f"Odebrano: {reading.get('received_at')}")
            lines.append(f"Znacznik urzadzenia: {reading.get('device_timestamp')}")
            lines.append(f"Rozmiar payload: {reading.get('payload_size')}")
            payload = reading.get("payload")
            if isinstance(payload, (dict, list)):
                formatted = json.dumps(payload, ensure_ascii=False, indent=2)
                lines.append("Payload:")
                lines.append(formatted)
            else:
                lines.append(f"Payload: {payload}")
            lines.append("-" * 40)
        try:
            with Path(target).open("w", encoding="utf-8") as txtfile:
                txtfile.write("\n".join(lines) if lines else "Brak danych do zapisania.")
            self.emit_message("success", f"Zapisano raport TXT ({len(readings)} wpisow).")
        except OSError as exc:
            self.emit_message("error", f"Nie udalo sie zapisac pliku: {exc}")
        finally:
            self.busy_cursor(False)
class UsersPage(MessageMixin):
    """Panel zarzadzania uzytkownikami (tylko dla administratora)."""

    def __init__(self, api_client: ApiClient, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.api_client = api_client
        self.users: list[dict[str, Any]] = []
        self._build_ui()
        self.refresh_users()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        header = QLabel("Uzytkownicy")
        header.setFont(QFont("Segoe UI Semibold", 18))
        layout.addWidget(header)

        button_row = QHBoxLayout()
        button_row.setSpacing(10)
        layout.addLayout(button_row)

        self.add_button = QPushButton("Dodaj uzytkownika")
        self.add_button.setCursor(Qt.PointingHandCursor)
        self.add_button.clicked.connect(self._create_user)
        self.edit_button = QPushButton("Edytuj uzytkownika")
        self.edit_button.setCursor(Qt.PointingHandCursor)
        self.edit_button.clicked.connect(self._edit_user)
        self.delete_button = QPushButton("Usun uzytkownika")
        self.delete_button.setCursor(Qt.PointingHandCursor)
        self.delete_button.clicked.connect(self._delete_user)
        self.refresh_button = QPushButton("Odswiez")
        self.refresh_button.setCursor(Qt.PointingHandCursor)
        self.refresh_button.clicked.connect(self.refresh_users)

        for btn in (self.add_button, self.edit_button, self.delete_button, self.refresh_button):
            btn.setStyleSheet(
                """
                QPushButton {
                    background-color: #2563eb;
                    color: #f8fafc;
                    border: none;
                    border-radius: 10px;
                    padding: 8px 12px;
                }
                QPushButton:hover {
                    background-color: #1d4ed8;
                }
                """
            )
            button_row.addWidget(btn)

        button_row.addStretch(1)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["ID", "E-mail", "Rola", "Utworzono"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet(
            """
            QTableWidget {
                background-color: #ffffff;
                alternate-background-color: #f8fafc;
                gridline-color: #cbd5e1;
                color: #0f172a;
            }
            QHeaderView::section {
                background-color: #e2e8f0;
                font-weight: 600;
                padding: 6px;
                border: none;
            }
            """
        )
        layout.addWidget(self.table, stretch=1)

        self.table_hint = QLabel(
            "Kolumny: ID - identyfikator konta, E-mail - login, Rola - poziom uprawnien, Utworzono - data dodania."
        )
        self.table_hint.setStyleSheet("color: #475569; font-size: 12px;")
        layout.addWidget(self.table_hint)

    def refresh_users(self) -> None:
        self.busy_cursor(True)
        try:
            self.users = self.api_client.list_users()
            self.table.setRowCount(len(self.users))
            for row, user in enumerate(self.users):
                self.table.setItem(row, 0, QTableWidgetItem(str(user.get("id"))))
                self.table.setItem(row, 1, QTableWidgetItem(user.get("email")))
                self.table.setItem(row, 2, QTableWidgetItem(user.get("role")))
                self.table.setItem(row, 3, QTableWidgetItem(user.get("created_at", "")))
            self.emit_message("info", f"Pobrano {len(self.users)} uzytkownikow.")
        except ApiError as exc:
            self.emit_message("error", exc.detail)
        finally:
            self.busy_cursor(False)

    def _selected_user(self) -> dict[str, Any] | None:
        row = self.table.currentRow()
        if row < 0 or row >= len(self.users):
            return None
        return self.users[row]

    def _create_user(self) -> None:
        dialog = UserDialog(parent=self)
        if dialog.exec_() != QDialog.Accepted:
            return
        email, password, role = dialog.payload()
        self.busy_cursor(True)
        try:
            self.api_client.create_user(email, password or "HasloTymczasowe1!", role)
            self.emit_message("success", "Dodano uzytkownika.")
            self.refresh_users()
        except ApiError as exc:
            self.emit_message("error", exc.detail)
        finally:
            self.busy_cursor(False)

    def _edit_user(self) -> None:
        user = self._selected_user()
        if not user:
            QMessageBox.information(self, "Edycja uzytkownika", "Wybierz rekord w tabeli.")
            return
        dialog = UserDialog(existing=user, parent=self)
        if dialog.exec_() != QDialog.Accepted:
            return
        email, password, role = dialog.payload()
        payload: dict[str, Any] = {"email": email, "role": role}
        if password:
            payload["password"] = password
        self.busy_cursor(True)
        try:
            self.api_client.update_user(user_id=user["id"], **payload)
            self.emit_message("success", "Zaktualizowano dane uzytkownika.")
            self.refresh_users()
        except ApiError as exc:
            self.emit_message("error", exc.detail)
        finally:
            self.busy_cursor(False)

    def _delete_user(self) -> None:
        user = self._selected_user()
        if not user:
            QMessageBox.information(self, "Usuwanie uzytkownika", "Wybierz rekord w tabeli.")
            return
        confirm = QMessageBox.question(
            self,
            "Usun uzytkownika",
            f"Czy na pewno usunac konto {user['email']}?",
        )
        if confirm != QMessageBox.Yes:
            return
        self.busy_cursor(True)
        try:
            self.api_client.delete_user(user_id=user["id"])
            self.emit_message("success", "Usunieto uzytkownika.")
            self.refresh_users()
        except ApiError as exc:
            self.emit_message("error", exc.detail)
        finally:
            self.busy_cursor(False)


class UserDialog(QDialog):
    """Pomocniczy dialog do tworzenia i edycji kont."""

    def __init__(self, existing: dict[str, Any] | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._existing = existing
        self.setWindowTitle("Edytuj uzytkownika" if existing else "Nowy uzytkownik")
        self.resize(420, 200)
        layout = QVBoxLayout(self)

        form = QFormLayout()
        self.email_input = QLineEdit(existing["email"] if existing else "")
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setPlaceholderText(
            "Pozostaw puste, aby nie zmieniac hasla" if existing else "Haslo poczatkowe"
        )
        self.role_combo = QComboBox()
        self.role_combo.addItems(["user", "admin"])
        if existing:
            idx = self.role_combo.findText(existing.get("role", "user"))
            if idx >= 0:
                self.role_combo.setCurrentIndex(idx)
        form.addRow("E-mail", self.email_input)
        form.addRow("Haslo", self.password_input)
        form.addRow("Rola", self.role_combo)
        layout.addLayout(form)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel = QPushButton("Anuluj")
        cancel.clicked.connect(self.reject)
        ok = QPushButton("Zapisz")
        ok.clicked.connect(self._accept)
        buttons.addWidget(cancel)
        buttons.addWidget(ok)
        layout.addLayout(buttons)

    def _accept(self) -> None:
        if not self.email_input.text().strip():
            QMessageBox.warning(self, "Adres e-mail", "Wpisz adres e-mail.")
            return
        if not self._existing and not self.password_input.text().strip():
            QMessageBox.warning(self, "Haslo", "Wpisz haslo poczatkowe.")
            return
        self.accept()

    def payload(self) -> tuple[str, str | None, str]:
        email = self.email_input.text().strip()
        password = self.password_input.text().strip() or None
        role = self.role_combo.currentText()
        return email, password, role
class SecurityEventsPage(MessageMixin):
    """Tabela zdarzen bezpieczenstwa."""

    def __init__(self, api_client: ApiClient, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.api_client = api_client
        self._build_ui()
        self.refresh_events()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        header = QLabel("Logi bezpieczenstwa")
        header.setFont(QFont("Segoe UI Semibold", 18))
        layout.addWidget(header)

        top_row = QHBoxLayout()
        top_row.setSpacing(10)
        self.scenario_combo = QComboBox()
        self.scenario_combo.addItem("Blad JWT (podpis nieprawidlowy)", "jwt_invalid")
        self.scenario_combo.addItem("Brak autoryzacji", "missing_authorization")
        self.scenario_combo.addItem("Odmowa dla urzadzenia", "device_forbidden")
        self.scenario_combo.setStyleSheet(
            "QComboBox { border: 1px solid #cbd5f5; border-radius: 8px; padding: 6px 10px; }"
        )
        self.note_input = QLineEdit()
        self.note_input.setPlaceholderText("Opcjonalna notatka")
        self.note_input.setStyleSheet(
            "QLineEdit { border: 1px solid #cbd5f5; border-radius: 8px; padding: 6px 10px; }"
        )
        self.simulate_button = QPushButton("Symuluj zdarzenie")
        self.simulate_button.setCursor(Qt.PointingHandCursor)
        self.simulate_button.setStyleSheet(
            "QPushButton { background-color: #2563eb; color: #f8fafc; border-radius: 10px; padding: 8px 12px; }"
            "QPushButton:hover { background-color: #1d4ed8; }"
        )
        self.simulate_button.clicked.connect(self._simulate_event)
        top_row.addWidget(QLabel("Symulacja"))
        top_row.addWidget(self.scenario_combo)
        top_row.addWidget(self.note_input)
        top_row.addWidget(self.simulate_button)
        top_row.addStretch(1)
        self.refresh_button = QPushButton("Odswiez")
        self.refresh_button.setCursor(Qt.PointingHandCursor)
        self.refresh_button.setStyleSheet(
            "QPushButton { background-color: #2563eb; color: #f8fafc; border-radius: 10px; padding: 8px 12px; }"
            "QPushButton:hover { background-color: #1d4ed8; }"
        )
        self.refresh_button.clicked.connect(self.refresh_events)
        top_row.addWidget(self.refresh_button)
        layout.addLayout(top_row)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Czas", "Aktor", "Id aktora", "Zdarzenie", "Status"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet(
            """
            QTableWidget {
                background-color: #ffffff;
                alternate-background-color: #f8fafc;
                gridline-color: #cbd5e1;
                color: #0f172a;
            }
            QHeaderView::section {
                background-color: #e2e8f0;
                font-weight: 600;
                padding: 6px;
                border: none;
            }
            """
        )
        layout.addWidget(self.table, stretch=1)

        hint = QLabel(
            "Kolumny: Czas - moment zdarzenia, Aktor - typ uczestnika, Id aktora - identyfikator, "
            "Zdarzenie - wykonana czynnosci, Status - wynik (success/denied/error)."
        )
        hint.setStyleSheet("color: #475569; font-size: 12px;")
        layout.addWidget(hint)

    def refresh_events(self) -> None:
        self.busy_cursor(True)
        try:
            events = self.api_client.get_security_events()
            self.table.setRowCount(len(events))
            for row, event in enumerate(events):
                self.table.setItem(row, 0, QTableWidgetItem(str(event.get("created_at"))))
                self.table.setItem(row, 1, QTableWidgetItem(str(event.get("actor_type"))))
                self.table.setItem(row, 2, QTableWidgetItem(str(event.get("actor_id") or "-")))
                self.table.setItem(row, 3, QTableWidgetItem(str(event.get("event_type"))))
                self.table.setItem(row, 4, QTableWidgetItem(str(event.get("status"))))
            self.emit_message("info", f"Pobrano {len(events)} zdarzen bezpieczenstwa.")
        except ApiError as exc:
            self.emit_message("error", exc.detail)
        finally:
            self.busy_cursor(False)

    def _simulate_event(self) -> None:
        scenario = self.scenario_combo.currentData()
        note = self.note_input.text().strip() or None
        self.busy_cursor(True)
        try:
            result = self.api_client.simulate_security_event(scenario=scenario, note=note)
            detail = result.get("detail", "Dodano zdarzenie.")
            self.emit_message("success", detail)
            self.note_input.clear()
            self.refresh_events()
        except ApiError as exc:
            self.emit_message("error", exc.detail)
        finally:
            self.busy_cursor(False)
class MainWindow(QMainWindow):
    """Glowne okno z zakladkami funkcjonalnymi."""

    def __init__(self, api_client: ApiClient) -> None:
        super().__init__()
        self.api_client = api_client
        self.setWindowTitle("Konsola bezpieczenstwa IoT")
        self.resize(1280, 768)
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self._build_ui()

    def _build_ui(self) -> None:
        central = QWidget()
        central.setObjectName("mainSurface")
        central.setStyleSheet(
            """
            QWidget#mainSurface {
                background-color: #e2e8f0;
                font-family: "Segoe UI", Arial, sans-serif;
                color: #0f172a;
            }
            """
        )
        layout = QVBoxLayout(central)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(18)

        header = QHBoxLayout()
        session = self.api_client.user_session
        user_label = QLabel(
            f"Zalogowano jako {session.email} "
            f"({'Administrator' if session.role == 'admin' else 'Uzytkownik'})"
        )
        user_label.setStyleSheet("color: #1f2937; font-weight: 600;")
        header.addWidget(user_label)
        header.addStretch(1)
        logout_button = QPushButton("Wyloguj")
        logout_button.setCursor(Qt.PointingHandCursor)
        logout_button.setStyleSheet(
            "QPushButton { background-color: #2563eb; color: #f8fafc; border-radius: 10px; padding: 8px 14px; }"
            "QPushButton:hover { background-color: #1d4ed8; }"
        )
        logout_button.clicked.connect(self._on_logout)
        header.addWidget(logout_button)
        layout.addLayout(header)

        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(
            """
            QTabWidget::pane {
                border: none;
                background: #f8fafc;
                border-radius: 18px;
            }
            QTabBar::tab {
                background: #cbd5f5;
                color: #1f2937;
                padding: 10px 20px;
                margin-right: 4px;
                border-top-left-radius: 12px;
                border-top-right-radius: 12px;
            }
            QTabBar::tab:selected {
                background: #2563eb;
                color: #ffffff;
            }
            """
        )
        layout.addWidget(self.tabs, stretch=1)

        self.devices_page = DevicesPage(self.api_client)
        self.devices_page.message_emitted.connect(self._handle_message)
        self.tabs.addTab(self.devices_page, "Urzadzenia")

        if session.role == "admin":
            self.users_page = UsersPage(self.api_client)
            self.users_page.message_emitted.connect(self._handle_message)
            self.tabs.addTab(self.users_page, "Uzytkownicy")

            self.events_page = SecurityEventsPage(self.api_client)
            self.events_page.message_emitted.connect(self._handle_message)
            self.tabs.addTab(self.events_page, "Logi bezpieczenstwa")

        self.setCentralWidget(central)

    def _handle_message(self, level: str, text: str) -> None:
        if level == "error":
            QMessageBox.warning(self, "Blad", text)
        elif level == "success":
            self.status_bar.showMessage(text, 7000)
        else:
            self.status_bar.showMessage(text, 5000)

    def _on_logout(self) -> None:
        self.api_client.logout()
        QMessageBox.information(self, "Wylogowano", "Sesja zostala zakonczona.")
        QApplication.quit()


__all__ = ["MainWindow"]
