from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import QLabel, QTableWidget, QTableWidgetItem

from app import tool_history
from app.job_queue import get_job_queue


class ToolWorker(QThread):
    finished_with_result = Signal(object)

    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self._fn = fn
        self._args = args
        self._kwargs = kwargs

    def run(self):
        result = self._fn(*self._args, **self._kwargs)
        tool_history.add_result(result)
        self.finished_with_result.emit(result)


class ToolRunner:
    """Submit one-at-a-time tab tool workers through the central app queue."""

    def __init__(self, scope, set_busy, status_label=None, status_changed=None, busy_text="Running tool..."):
        self._scope = scope
        self._set_busy = set_busy
        self._status_label = status_label
        self._status_changed = status_changed
        self._busy_text = busy_text

    def is_running(self):
        return get_job_queue().has_scope(self._scope)

    def start(self, fn, args, on_result):
        worker = ToolWorker(fn, *args)
        return bool(get_job_queue().submit(
            scope=self._scope,
            title=self._busy_text,
            worker=worker,
            result_signal="finished_with_result",
            on_result=on_result,
            on_started=self._on_started,
            on_finished=lambda: self._set_busy(False),
            on_rejected=self._on_rejected,
        ))

    def _on_started(self):
        self._set_busy(True)
        if self._status_label is not None:
            set_status_label(self._status_label, self._busy_text)
        if self._status_changed is not None:
            self._status_changed.emit(self._busy_text)

    def _on_rejected(self, message):
        if self._status_label is not None:
            set_status_label(self._status_label, message, False)
        if self._status_changed is not None:
            self._status_changed.emit(message)


def result_text(result):
    lines = [result.summary]
    lines.extend(result.details[:12])
    if result.errors:
        lines.append("Errors:")
        lines.extend(result.errors[:6])
    return "\n".join(str(line) for line in lines if str(line).strip())


def set_status_label(label: QLabel, text, success=None):
    label.setText(text)
    if success is None:
        level = ""
    else:
        level = "success" if success else "error"
    if label.property("state") != level:
        label.setProperty("state", level)
        label.style().unpolish(label)
        label.style().polish(label)


def populate_history_table(table: QTableWidget):
    items = tool_history.entries()
    table.setRowCount(len(items))
    for row, item in enumerate(items):
        table.setItem(row, 0, QTableWidgetItem(item.timestamp.strftime("%H:%M:%S")))
        table.setItem(row, 1, QTableWidgetItem(item.title))
        table.setItem(row, 2, QTableWidgetItem("OK" if item.success else "Review"))
        table.setItem(row, 3, QTableWidgetItem(item.summary))
