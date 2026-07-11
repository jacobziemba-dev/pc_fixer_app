from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, QPushButton,
    QTableWidget, QHeaderView, QTextEdit,
)

from app import toolbox, tool_history
from app.toolbox_widgets import ToolWorker, populate_history_table, result_text, set_status_label


class ReportsTab(QWidget):
    status_changed = Signal(str)

    def __init__(self):
        super().__init__()
        self._worker = None

        outer = QVBoxLayout(self)
        header = QHBoxLayout()
        title = QLabel("Reports & History")
        title.setProperty("role", "heading")
        self.refresh_btn = QPushButton("Refresh History")
        self.refresh_btn.setProperty("variant", "secondary")
        self.refresh_btn.clicked.connect(self._refresh_history)
        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(self.refresh_btn)
        outer.addLayout(header)

        subtitle = QLabel("Export a local diagnostic report and review recent tool results.")
        subtitle.setProperty("role", "caption")
        subtitle.setWordWrap(True)
        outer.addWidget(subtitle)

        actions = QGroupBox("Report")
        actions_layout = QHBoxLayout(actions)
        self.export_btn = QPushButton("Export PC Report")
        self.export_btn.clicked.connect(lambda: self._run_tool(toolbox.export_pc_report))
        self.clear_btn = QPushButton("Clear History")
        self.clear_btn.setProperty("variant", "secondary")
        self.clear_btn.clicked.connect(self._clear_history)
        actions_layout.addWidget(self.export_btn)
        actions_layout.addWidget(self.clear_btn)
        actions_layout.addStretch(1)
        outer.addWidget(actions)

        self.status_label = QLabel("No report exported yet.")
        self.status_label.setProperty("role", "caption")
        self.status_label.setWordWrap(True)
        outer.addWidget(self.status_label)

        self.history_table = QTableWidget(0, 4)
        self.history_table.setHorizontalHeaderLabels(["Time", "Tool", "State", "Summary"])
        self.history_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.history_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.history_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.history_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.history_table.verticalHeader().setVisible(False)
        self.history_table.setAlternatingRowColors(True)
        self.history_table.itemSelectionChanged.connect(self._show_selected_history)
        outer.addWidget(self.history_table, 1)

        self.details = QTextEdit()
        self.details.setReadOnly(True)
        outer.addWidget(self.details, 1)

        self._refresh_history()

    def _run_tool(self, fn, *args):
        if self._worker is not None and self._worker.isRunning():
            return
        self.export_btn.setEnabled(False)
        set_status_label(self.status_label, "Exporting report...")
        self.status_changed.emit("Exporting report...")
        self._worker = ToolWorker(fn, *args)
        self._worker.finished_with_result.connect(self._on_result)
        self._worker.finished.connect(self._clear_worker)
        self._worker.finished.connect(self._worker.deleteLater)
        self._worker.start()

    def _clear_worker(self):
        self._worker = None
        self.export_btn.setEnabled(True)

    def _on_result(self, result):
        set_status_label(self.status_label, result.summary, result.success)
        self.status_changed.emit(result.summary)
        self.details.setPlainText(result_text(result))
        self._refresh_history()

    def _refresh_history(self):
        populate_history_table(self.history_table)

    def _clear_history(self):
        tool_history.clear()
        self._refresh_history()
        self.details.clear()
        set_status_label(self.status_label, "History cleared.")

    def _show_selected_history(self):
        row = self.history_table.currentRow()
        items = tool_history.entries()
        if row < 0 or row >= len(items):
            return
        entry = items[row]
        lines = [entry.summary]
        lines.extend(entry.details)
        if entry.errors:
            lines.append("Errors:")
            lines.extend(entry.errors)
        self.details.setPlainText("\n".join(lines))
