from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QLineEdit, QSplitter,
    QMessageBox,
)
from PySide6.QtCore import Qt, QThread, Signal

from app import system_info as sysinfo
from app import toolbox
from app.job_queue import get_job_queue
from app.toolbox_widgets import ToolWorker, set_status_label
from app.ui_kit import build_context_row, clear_layout, empty_row, rows_card, section_panel


class NumericTableWidgetItem(QTableWidgetItem):
    def __lt__(self, other):
        left = self.data(Qt.UserRole)
        right = other.data(Qt.UserRole) if other is not None else None
        if isinstance(left, (int, float)) and isinstance(right, (int, float)):
            return left < right
        return super().__lt__(other)


class StartupLoadWorker(QThread):
    finished_with_data = Signal(list, list)

    def run(self):
        startup_items = sysinfo.get_startup_items()
        programs = sysinfo.get_installed_programs()
        self.finished_with_data.emit(startup_items, programs)


class StartupTab(QWidget):
    def __init__(self):
        super().__init__()
        outer = QVBoxLayout(self)

        header_layout = QHBoxLayout()
        title = QLabel("Startup Items & Installed Programs")
        title.setProperty("role", "heading")
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.setProperty("variant", "secondary")
        self.refresh_btn.clicked.connect(self.load)
        header_layout.addWidget(title)
        header_layout.addStretch(1)
        header_layout.addWidget(self.refresh_btn)
        outer.addLayout(header_layout)

        self.status_label = QLabel(
            "Disable or enable allowlisted startup items after confirmation. "
            "Installed programs remain read-only."
        )
        self.status_label.setProperty("role", "caption")
        self.status_label.setWordWrap(True)
        outer.addWidget(self.status_label)

        splitter = QSplitter(Qt.Vertical)

        startup_panel, startup_body = section_panel("PROGRAMS THAT LAUNCH AT STARTUP")
        startup_card, self.startup_rows = rows_card()
        startup_body.addWidget(startup_card)

        programs_panel, programs_body = section_panel("INSTALLED PROGRAMS")
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Filter by name or publisher...")
        self.search_box.textChanged.connect(self._apply_filter)
        programs_body.addWidget(self.search_box)
        self.programs_table = QTableWidget(0, 4)
        self.programs_table.setHorizontalHeaderLabels(["Name", "Version", "Publisher", "Size"])
        self.programs_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.programs_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.programs_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.programs_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.programs_table.verticalHeader().setVisible(False)
        self.programs_table.setAlternatingRowColors(True)
        self.programs_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.programs_table.setSortingEnabled(True)
        programs_body.addWidget(self.programs_table)

        splitter.addWidget(startup_panel)
        splitter.addWidget(programs_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        outer.addWidget(splitter, 1)

        self._all_programs = []
        self._startup_items = []
        self._startup_action_buttons = []
        self._reload_after_action = False
        self.load()

    def _set_busy(self, busy):
        self.refresh_btn.setEnabled(not busy)
        for button in self._startup_action_buttons:
            button.setEnabled(not busy)

    def load(self):
        worker = StartupLoadWorker()
        get_job_queue().submit(
            scope="startup-tools",
            title="Loading startup items...",
            worker=worker,
            result_signal="finished_with_data",
            on_started=self._on_load_started,
            on_result=self._on_loaded,
            on_finished=self._on_job_finished,
            on_rejected=lambda message: set_status_label(self.status_label, message, False),
        )

    def _on_job_finished(self):
        self._set_busy(False)
        if self._reload_after_action:
            self._reload_after_action = False
            self.load()

    def _on_load_started(self):
        self._set_busy(True)
        set_status_label(self.status_label, "Loading startup items and installed programs...")

    def _on_loaded(self, startup_items, programs):
        self._startup_items = startup_items
        self._populate_startup_items(startup_items)
        self._all_programs = programs
        self._render_programs(self._all_programs)
        set_status_label(
            self.status_label,
            "Select a startup item to enable or disable. Installed programs are read-only.",
            True,
        )

    def _populate_startup_items(self, items):
        clear_layout(self.startup_rows)
        self._startup_action_buttons = []
        if not items:
            self.startup_rows.addWidget(empty_row("No startup items found."))
            return
        for item in items:
            enabled = item.get("enabled", True)
            state = "Enabled" if enabled else "Disabled"
            action_btn = QPushButton("Disable" if enabled else "Enable")
            action_btn.setProperty("variant", "card-danger" if enabled else "action-confirm")
            action_btn.clicked.connect(
                lambda checked=False, item=item, enabled=enabled: self._confirm_toggle(item, not enabled)
            )
            secondary = f"{item.get('command', '')} · {item.get('source', '')}"
            row = build_context_row(item["name"], secondary, state, trailing=action_btn)
            self.startup_rows.addWidget(row)
            self._startup_action_buttons.append(action_btn)

    def _confirm_toggle(self, item, enabled):
        verb = "enable" if enabled else "disable"
        reply = QMessageBox.question(
            self,
            "Confirm Startup Change",
            f"{verb.capitalize()} startup item \"{item['name']}\" from {item.get('source', '')}?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        worker = ToolWorker(
            toolbox.set_startup_item_enabled,
            item["name"],
            item.get("source", ""),
            enabled,
            item.get("command", ""),
        )
        get_job_queue().submit(
            scope="startup-tools",
            title="Updating startup item...",
            worker=worker,
            result_signal="finished_with_result",
            on_started=lambda: self._set_busy(True),
            on_result=self._on_toggle_result,
            on_finished=self._on_job_finished,
            on_rejected=lambda message: set_status_label(self.status_label, message, False),
        )

    def _on_toggle_result(self, result):
        set_status_label(self.status_label, result.summary, result.success)
        self._reload_after_action = bool(result.success)

    def _render_programs(self, programs):
        self.programs_table.setSortingEnabled(False)
        self.programs_table.setRowCount(len(programs))
        for row, p in enumerate(programs):
            self.programs_table.setItem(row, 0, QTableWidgetItem(p["name"]))
            self.programs_table.setItem(row, 1, QTableWidgetItem(str(p["version"])))
            self.programs_table.setItem(row, 2, QTableWidgetItem(str(p["publisher"])))
            size_item = NumericTableWidgetItem(sysinfo.format_bytes(p["size_bytes"]) if p["size_bytes"] else "")
            size_item.setData(Qt.UserRole, p["size_bytes"])
            self.programs_table.setItem(row, 3, size_item)
        self.programs_table.setSortingEnabled(True)

    def _apply_filter(self, text):
        text = text.lower().strip()
        if not text:
            self._render_programs(self._all_programs)
            return
        filtered = [
            p for p in self._all_programs
            if text in p["name"].lower() or text in str(p["publisher"]).lower()
        ]
        self._render_programs(filtered)
