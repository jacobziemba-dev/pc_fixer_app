import psutil

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QMessageBox, QComboBox,
)

from app import toolbox
from app.toolbox_widgets import ToolRunner, result_text, set_status_label
from app.ui_kit import section_panel


class NetworkTab(QWidget):
    status_changed = Signal(str)

    def __init__(self):
        super().__init__()

        outer = QVBoxLayout(self)
        header = QHBoxLayout()
        title = QLabel("Network")
        title.setProperty("role", "heading")
        self.refresh_adapters_btn = QPushButton("Refresh Adapters")
        self.refresh_adapters_btn.setProperty("variant", "secondary")
        self.refresh_adapters_btn.clicked.connect(self._load_adapters)
        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(self.refresh_adapters_btn)
        outer.addLayout(header)

        subtitle = QLabel(
            "Check connectivity and run confirmed network fixes. Adapter restarts may briefly disconnect you."
        )
        subtitle.setProperty("role", "caption")
        subtitle.setWordWrap(True)
        outer.addWidget(subtitle)

        checks, checks_body = section_panel("CONNECTIVITY")
        checks_layout = QHBoxLayout()
        checks_layout.setSpacing(8)
        self.check_btn = QPushButton("Check Network Health")
        self.check_btn.clicked.connect(lambda: self._run_tool(toolbox.check_network_health))
        self.flush_btn = QPushButton("Flush DNS Cache")
        self.flush_btn.setProperty("variant", "secondary")
        self.flush_btn.clicked.connect(self._confirm_flush_dns)
        self.renew_ip_btn = QPushButton("Renew IP")
        self.renew_ip_btn.setProperty("variant", "secondary")
        self.renew_ip_btn.clicked.connect(self._confirm_renew_ip)
        self.winsock_btn = QPushButton("Reset Winsock")
        self.winsock_btn.setProperty("variant", "danger")
        self.winsock_btn.clicked.connect(self._confirm_reset_winsock)
        checks_layout.addWidget(self.check_btn)
        checks_layout.addWidget(self.flush_btn)
        checks_layout.addWidget(self.renew_ip_btn)
        checks_layout.addWidget(self.winsock_btn)
        checks_layout.addStretch(1)
        checks_body.addLayout(checks_layout)
        outer.addWidget(checks)

        adapters, adapters_body = section_panel("ADAPTERS")
        adapters_layout = QHBoxLayout()
        adapters_layout.setSpacing(8)
        self.adapter_combo = QComboBox()
        self.restart_btn = QPushButton("Restart Adapter")
        self.restart_btn.setProperty("variant", "danger")
        self.restart_btn.clicked.connect(self._confirm_restart_adapter)
        adapters_layout.addWidget(self.adapter_combo, 1)
        adapters_layout.addWidget(self.restart_btn)
        adapters_body.addLayout(adapters_layout)
        outer.addWidget(adapters)

        self.status_label = QLabel("Choose a network tool to begin.")
        self.status_label.setProperty("role", "caption")
        self.status_label.setWordWrap(True)
        outer.addWidget(self.status_label)
        self._runner = ToolRunner(
            "network-tools",
            self._set_busy,
            self.status_label,
            self.status_changed,
            "Running network tool...",
        )

        self.output = QTextEdit()
        self.output.setReadOnly(True)
        outer.addWidget(self.output, 1)

        self._load_adapters()

    def _load_adapters(self):
        self.adapter_combo.clear()
        for name, stats in psutil.net_if_stats().items():
            label = f"{name} ({'up' if stats.isup else 'down'})"
            self.adapter_combo.addItem(label, name)
        self.restart_btn.setEnabled(self.adapter_combo.count() > 0)

    def _set_busy(self, busy):
        for button in (
            self.refresh_adapters_btn, self.check_btn, self.flush_btn,
            self.renew_ip_btn, self.winsock_btn, self.restart_btn,
        ):
            button.setEnabled(not busy)

    def _run_tool(self, fn, *args):
        self._runner.start(fn, args, self._on_result)

    def _on_result(self, result):
        set_status_label(self.status_label, result.summary, result.success)
        self.status_changed.emit(result.summary)
        self.output.setPlainText(result_text(result))
        self._load_adapters()

    def _confirm_flush_dns(self):
        reply = QMessageBox.question(
            self,
            "Confirm DNS Flush",
            "Flush the Windows DNS resolver cache?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self._run_tool(toolbox.flush_dns_cache)

    def _confirm_restart_adapter(self):
        adapter = self.adapter_combo.currentData()
        if not adapter:
            return
        reply = QMessageBox.question(
            self,
            "Confirm Adapter Restart",
            f"Restart network adapter {adapter}? This may briefly disconnect your network.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self._run_tool(toolbox.restart_network_adapter, adapter)

    def _confirm_renew_ip(self):
        reply = QMessageBox.question(
            self,
            "Confirm Renew IP",
            "Release and renew the Windows IP address? This may briefly disconnect your network.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self._run_tool(toolbox.renew_ip_address)

    def _confirm_reset_winsock(self):
        reply = QMessageBox.question(
            self,
            "Confirm Winsock Reset",
            "Reset the Windows Winsock catalog?\n\n"
            "This can repair broken networking but often requires a reboot afterward.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self._run_tool(toolbox.reset_winsock)
