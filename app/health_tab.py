from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, QPushButton,
    QTextEdit, QMessageBox, QComboBox,
)

from app import toolbox
from app.toolbox_widgets import ToolRunner, result_text, set_status_label


class HealthTab(QWidget):
    status_changed = Signal(str)

    def __init__(self):
        super().__init__()
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
        self.reboot_btn = QPushButton("Pending Reboot")
        self.battery_btn = QPushButton("Battery")
        for button, fn in (
            (self.update_btn, toolbox.check_windows_updates),
            (self.disk_btn, toolbox.check_disk_health),
            (self.events_btn, toolbox.scan_event_log_errors),
            (self.security_btn, toolbox.check_windows_security),
            (self.startup_btn, toolbox.review_startup_impact),
            (self.reboot_btn, toolbox.check_pending_reboot),
            (self.battery_btn, toolbox.check_battery_report),
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

        helpers = QGroupBox("Quick Helpers")
        helpers_layout = QHBoxLayout(helpers)
        self.restore_btn = QPushButton("Create Restore Point")
        self.restore_btn.setProperty("variant", "secondary")
        self.restore_btn.clicked.connect(self._confirm_restore_point)
        self.explorer_btn = QPushButton("Restart Explorer")
        self.explorer_btn.setProperty("variant", "secondary")
        self.explorer_btn.clicked.connect(self._confirm_restart_explorer)
        self.settings_combo = QComboBox()
        self.settings_combo.addItem("Display", "display")
        self.settings_combo.addItem("Network", "network")
        self.settings_combo.addItem("Windows Update", "windows_update")
        self.settings_combo.addItem("Apps", "apps")
        self.settings_combo.addItem("Sound", "sound")
        self.settings_btn = QPushButton("Open Settings")
        self.settings_btn.clicked.connect(self._open_settings)
        self.folder_combo = QComboBox()
        self.folder_combo.addItem("Temp", "temp")
        self.folder_combo.addItem("Downloads", "downloads")
        self.folder_combo.addItem("Startup", "startup")
        self.folder_combo.addItem("Local AppData", "local_appdata")
        self.folder_combo.addItem("Recycle Bin", "recycle_bin")
        self.folder_btn = QPushButton("Open Folder")
        self.folder_btn.clicked.connect(self._open_folder)
        helpers_layout.addWidget(self.restore_btn)
        helpers_layout.addWidget(self.explorer_btn)
        helpers_layout.addWidget(self.settings_combo, 1)
        helpers_layout.addWidget(self.settings_btn)
        helpers_layout.addWidget(self.folder_combo, 1)
        helpers_layout.addWidget(self.folder_btn)
        outer.addWidget(helpers)

        self.status_label = QLabel("Choose a health check to begin.")
        self.status_label.setProperty("role", "caption")
        self.status_label.setWordWrap(True)
        outer.addWidget(self.status_label)
        self._runner = ToolRunner(
            "health-tools",
            self._set_busy,
            self.status_label,
            self.status_changed,
            "Running health tool...",
        )

        self.output = QTextEdit()
        self.output.setReadOnly(True)
        outer.addWidget(self.output, 1)

    def _set_busy(self, busy):
        for button in (
            self.update_btn, self.disk_btn, self.events_btn, self.security_btn,
            self.startup_btn, self.reboot_btn, self.battery_btn,
            self.power_check_btn, self.power_apply_btn, self.restore_btn,
            self.explorer_btn, self.settings_btn, self.folder_btn,
        ):
            button.setEnabled(not busy)

    def _run_tool(self, fn, *args):
        self._runner.start(fn, args, self._on_result)

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

    def _confirm_restart_explorer(self):
        reply = QMessageBox.question(
            self,
            "Confirm Restart Explorer",
            "Restart Windows Explorer? The taskbar and desktop may briefly disappear.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self._run_tool(toolbox.restart_explorer)

    def _open_settings(self):
        self._run_tool(toolbox.open_windows_settings, self.settings_combo.currentData())

    def _open_folder(self):
        self._run_tool(toolbox.open_known_folder, self.folder_combo.currentData())
