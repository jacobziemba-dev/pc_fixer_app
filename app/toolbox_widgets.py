from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import QLabel, QTableWidget, QTableWidgetItem

from app import tool_history


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
