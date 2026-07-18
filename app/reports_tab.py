from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QTextEdit,
)

from app import toolbox, tool_history
from app.toolbox_widgets import ToolRunner, result_text, set_status_label
from app.ui_kit import build_context_row, clear_layout, empty_row, rows_card, section_panel


class ReportsTab(QWidget):
    status_changed = Signal(str)

    def __init__(self):
        super().__init__()

        outer = QVBoxLayout(self)
        header = QHBoxLayout()
        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        title = QLabel("Reports & History")
        title.setProperty("role", "heading")
        title_col.addWidget(title)
        subtitle = QLabel("Export a local diagnostic report and review recent tool results.")
        subtitle.setProperty("role", "caption")
        subtitle.setWordWrap(True)
        title_col.addWidget(subtitle)
        header.addLayout(title_col)
        header.addStretch(1)
        self.refresh_btn = QPushButton("Refresh History")
        self.refresh_btn.setProperty("variant", "secondary")
        self.refresh_btn.clicked.connect(self._refresh_history)
        self.export_btn = QPushButton("Export PC Report")
        self.export_btn.clicked.connect(lambda: self._run_tool(toolbox.export_pc_report))
        self.clear_btn = QPushButton("Clear History")
        self.clear_btn.setProperty("variant", "secondary")
        self.clear_btn.clicked.connect(self._clear_history)
        header.addWidget(self.refresh_btn, 0, Qt.AlignTop)
        header.addWidget(self.export_btn, 0, Qt.AlignTop)
        header.addWidget(self.clear_btn, 0, Qt.AlignTop)
        outer.addLayout(header)

        self.status_label = QLabel("No report exported yet.")
        self.status_label.setProperty("role", "caption")
        self.status_label.setWordWrap(True)
        outer.addWidget(self.status_label)
        self._runner = ToolRunner(
            "reports-tools",
            self._set_busy,
            self.status_label,
            self.status_changed,
            "Exporting report...",
        )

        history_panel, history_body = section_panel("HISTORY")
        history_scroll = QScrollArea()
        history_scroll.setWidgetResizable(True)
        history_scroll.setFrameShape(QFrame.NoFrame)
        history_card, self.history_rows = rows_card()
        history_scroll.setWidget(history_card)
        history_body.addWidget(history_scroll, 1)
        details_title = QLabel("Details")
        details_title.setProperty("role", "caption")
        history_body.addWidget(details_title)
        self.details = QTextEdit()
        self.details.setReadOnly(True)
        history_body.addWidget(self.details, 1)
        outer.addWidget(history_panel, 1)

        self._refresh_history()

    def _run_tool(self, fn, *args):
        self._runner.start(fn, args, self._on_result)

    def _set_busy(self, busy):
        self.export_btn.setEnabled(not busy)
        self.clear_btn.setEnabled(not busy)

    def _on_result(self, result):
        set_status_label(self.status_label, result.summary, result.success)
        self.status_changed.emit(result.summary)
        self.details.setPlainText(result_text(result))
        self._refresh_history()

    def _refresh_history(self):
        entries = tool_history.entries()
        clear_layout(self.history_rows)
        if not entries:
            self.history_rows.addWidget(empty_row("No tool history yet."))
            return
        for entry in entries:
            status = QLabel("")
            status.setProperty("role", "status-dot")
            status.setProperty("state", "good" if entry.success else "warn")
            status.setFixedSize(10, 10)
            meta = entry.timestamp.strftime("%H:%M:%S")
            row = build_context_row(
                entry.title,
                entry.summary,
                meta,
                trailing=status,
                on_click=lambda entry=entry: self._show_history_entry(entry),
            )
            self.history_rows.addWidget(row)

    def _clear_history(self):
        tool_history.clear()
        self._refresh_history()
        self.details.clear()
        set_status_label(self.status_label, "History cleared.")

    def _show_history_entry(self, entry):
        lines = [entry.summary]
        lines.extend(entry.details)
        if entry.errors:
            lines.append("Errors:")
            lines.extend(entry.errors)
        self.details.setPlainText("\n".join(lines))
