from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, QPushButton,
    QTextEdit, QMessageBox, QComboBox,
)

from app import toolbox
from app.toolbox_widgets import ToolWorker, result_text, set_status_label


class HealthTab(QWidget):
    status_changed = Signal(str)

    def __init__(self):
        super().__init__()
        self._worker = None

        outer = QVBoxLayout(self)
        header = QHBoxLayout()
        title = QLabel("Health Checks")
        title.setProperty("role", "heading")
        header.addWidget(title)
        header.addStretch(1)
        outer.addLayout(header)

        subtitle = QLabel(
            "Read system health signals and run confirmed repair helpers. "
            "Changing actions ask before they run."
        )
        subtitle.setProperty("role", "caption")
        subtitle.setWordWrap(True)
        outer.addWidget(subtitle)

        checks = QGroupBox("Read-only Checks")
        checks_layout = QHBoxLayout(checks)
        self.update_btn = QPushButton("Windows Update")
        self.disk_btn = QPushButton("Disk Health")
        self.events_btn = QPushButton("Event Logs")
        self.security_btn = QPushButton("Security")
        self.startup_btn = QPushButton("Startup Impact")
        for button, fn in (
            (self.update_btn, toolbox.check_windows_updates),
            (self.disk_btn, toolbox.check_disk_health),
            (self.events_btn, toolbox.scan_event_log_errors),
            (self.security_btn, toolbox.check_windows_security),
            (self.startup_btn, toolbox.review_startup_impact),
        ):
            button.clicked.connect(lambda checked=False, fn=fn: self._run_tool(fn))
            checks_layout.addWidget(button)
        checks_layout.addStretch(1)
        outer.addWidget(checks)

        power = QGroupBox("Power Plan")
        power_layout = QHBoxLayout(power)
        self.power_check_btn = QPushButton("Check Power Plan")
        self.power_check_btn.setProperty("variant", "secondary")
        self.power_check_btn.clicked.connect(lambda: self._run_tool(toolbox.check_power_plan))
        self.power_combo = QComboBox()
        self.power_combo.addItem("Balanced", "balanced")
        self.power_combo.addItem("High Performance", "high_performance")
        self.power_combo.addItem("Power Saver", "power_saver")
        self.power_apply_btn = QPushButton("Set Plan")
        self.power_apply_btn.clicked.connect(self._confirm_power_plan)
        power_layout.addWidget(self.power_check_btn)
        power_layout.addWidget(self.power_combo, 1)
        power_layout.addWidget(self.power_apply_btn)
        outer.addWidget(power)

        restore = QGroupBox("Safety")
        restore_layout = QHBoxLayout(restore)
        self.restore_btn = QPushButton("Create Restore Point")
        self.restore_btn.setProperty("variant", "secondary")
        self.restore_btn.clicked.connect(self._confirm_restore_point)
        restore_layout.addWidget(self.restore_btn)
        restore_layout.addStretch(1)
        outer.addWidget(restore)

        self.status_label = QLabel("Choose a health check to begin.")
        self.status_label.setProperty("role", "caption")
        self.status_label.setWordWrap(True)
        outer.addWidget(self.status_label)

        self.output = QTextEdit()
        self.output.setReadOnly(True)
        outer.addWidget(self.output, 1)

    def _set_busy(self, busy):
        for button in (
            self.update_btn, self.disk_btn, self.events_btn, self.security_btn,
            self.startup_btn, self.power_check_btn, self.power_apply_btn, self.restore_btn,
        ):
            button.setEnabled(not busy)

    def _run_tool(self, fn, *args):
        if self._worker is not None and self._worker.isRunning():
            return
        self._set_busy(True)
        set_status_label(self.status_label, "Running health tool...")
        self.status_changed.emit("Running health tool...")
        self._worker = ToolWorker(fn, *args)
        self._worker.finished_with_result.connect(self._on_result)
        self._worker.finished.connect(self._clear_worker)
        self._worker.finished.connect(self._worker.deleteLater)
        self._worker.start()

    def _clear_worker(self):
        self._worker = None
        self._set_busy(False)

    def _on_result(self, result):
        set_status_label(self.status_label, result.summary, result.success)
        self.status_changed.emit(result.summary)
        self.output.setPlainText(result_text(result))

    def _confirm_power_plan(self):
        label = self.power_combo.currentText()
        key = self.power_combo.currentData()
        reply = QMessageBox.question(
            self,
            "Confirm Power Plan Change",
            f"Switch the active Windows power plan to {label}?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self._run_tool(toolbox.set_power_plan, key)

    def _confirm_restore_point(self):
        reply = QMessageBox.question(
            self,
            "Confirm Restore Point",
            "Create a Windows restore point named PC Fix restore point?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self._run_tool(toolbox.create_restore_point)
