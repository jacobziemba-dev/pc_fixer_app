from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QLineEdit, QSplitter,
    QMessageBox, QAbstractItemView,
)
from PySide6.QtCore import Qt, QThread, Signal

from app import system_info as sysinfo
from app import toolbox
from app.job_queue import get_job_queue
from app.toolbox_widgets import ToolWorker, set_status_label


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

        startup_group = QGroupBox("Programs That Launch at Startup")
        startup_layout = QVBoxLayout(startup_group)
        actions = QHBoxLayout()
        self.disable_btn = QPushButton("Disable Selected")
        self.disable_btn.setProperty("variant", "danger")
        self.disable_btn.clicked.connect(lambda: self._confirm_toggle(False))
        self.enable_btn = QPushButton("Enable Selected")
        self.enable_btn.clicked.connect(lambda: self._confirm_toggle(True))
        actions.addWidget(self.disable_btn)
        actions.addWidget(self.enable_btn)
        actions.addStretch(1)
        startup_layout.addLayout(actions)
        self.startup_table = QTableWidget(0, 4)
        self.startup_table.setHorizontalHeaderLabels(["Name", "Command / Location", "Source", "State"])
        self.startup_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.startup_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.startup_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.startup_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.startup_table.verticalHeader().setVisible(False)
        self.startup_table.setAlternatingRowColors(True)
        self.startup_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.startup_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.startup_table.setSelectionMode(QAbstractItemView.SingleSelection)
        startup_layout.addWidget(self.startup_table)

        programs_group = QGroupBox("Installed Programs")
        programs_layout = QVBoxLayout(programs_group)
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Filter by name or publisher...")
        self.search_box.textChanged.connect(self._apply_filter)
        programs_layout.addWidget(self.search_box)
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
        programs_layout.addWidget(self.programs_table)

        splitter.addWidget(startup_group)
        splitter.addWidget(programs_group)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        outer.addWidget(splitter, 1)

        self._all_programs = []
        self._startup_items = []
        self._reload_after_action = False
        self.load()

    def _set_busy(self, busy):
        for button in (self.refresh_btn, self.disable_btn, self.enable_btn):
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
        self.startup_table.setSortingEnabled(False)
        self.startup_table.setRowCount(len(items))
        for row, item in enumerate(items):
            self.startup_table.setItem(row, 0, QTableWidgetItem(item["name"]))
            self.startup_table.setItem(row, 1, QTableWidgetItem(str(item.get("command", ""))))
            self.startup_table.setItem(row, 2, QTableWidgetItem(item.get("source", "")))
            state = "Enabled" if item.get("enabled", True) else "Disabled"
            self.startup_table.setItem(row, 3, QTableWidgetItem(state))

    def _selected_startup_item(self):
        row = self.startup_table.currentRow()
        if row < 0 or row >= len(self._startup_items):
            return None
        return self._startup_items[row]

    def _confirm_toggle(self, enabled):
        item = self._selected_startup_item()
        if not item:
            set_status_label(self.status_label, "Select a startup item first.", False)
            return
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
