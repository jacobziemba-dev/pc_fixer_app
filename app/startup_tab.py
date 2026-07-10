from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QLineEdit, QSplitter,
)
from PySide6.QtCore import Qt, QThread, Signal

from app import system_info as sysinfo


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
        self.status_label = QLabel("Read-only view - nothing here is changed automatically.")
        self.status_label.setProperty("role", "caption")
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.setProperty("variant", "secondary")
        self.refresh_btn.clicked.connect(self.load)
        header_layout.addWidget(title)
        header_layout.addStretch(1)
        header_layout.addWidget(self.refresh_btn)
        outer.addLayout(header_layout)
        outer.addWidget(self.status_label)

        splitter = QSplitter(Qt.Vertical)

        startup_group = QGroupBox("Programs That Launch at Startup")
        startup_layout = QVBoxLayout(startup_group)
        self.startup_table = QTableWidget(0, 3)
        self.startup_table.setHorizontalHeaderLabels(["Name", "Command / Location", "Source"])
        self.startup_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.startup_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.startup_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.startup_table.verticalHeader().setVisible(False)
        self.startup_table.setAlternatingRowColors(True)
        self.startup_table.setEditTriggers(QTableWidget.NoEditTriggers)
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
        self._worker = None
        self.load()

    def load(self):
        if self._worker is not None and self._worker.isRunning():
            return
        self.status_label.setText("Loading startup items and installed programs...")
        self.refresh_btn.setEnabled(False)
        self._worker = StartupLoadWorker()
        self._worker.finished_with_data.connect(self._on_loaded)
        self._worker.start()

    def _on_loaded(self, startup_items, programs):
        self._populate_startup_items(startup_items)
        self._all_programs = programs
        self._render_programs(self._all_programs)
        self.status_label.setText("Read-only view - nothing here is changed automatically.")
        self.refresh_btn.setEnabled(True)
        self._worker = None

    def _populate_startup_items(self, items):
        self.startup_table.setSortingEnabled(False)
        self.startup_table.setRowCount(len(items))
        for row, item in enumerate(items):
            self.startup_table.setItem(row, 0, QTableWidgetItem(item["name"]))
            self.startup_table.setItem(row, 1, QTableWidgetItem(item["command"]))
            self.startup_table.setItem(row, 2, QTableWidgetItem(item["source"]))

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
