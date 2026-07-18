import time

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QShowEvent, QHideEvent
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QFrame, QLabel,
    QProgressBar, QScrollArea, QPushButton, QMessageBox,
)

from app import system_info as sysinfo
from app import toolbox
from app.toolbox_widgets import ToolRunner, set_status_label
from app.ui_kit import build_context_row, clear_layout, empty_row, rows_card, section_panel

_REFRESH_INTERVAL_MS = 2000


def _level_for(percent):
    if percent >= 85:
        return "danger"
    if percent >= 60:
        return "warn"
    return ""


def _set_bar_level(bar, percent):
    level = _level_for(percent)
    if bar.property("level") == level:
        return
    bar.setProperty("level", level)
    bar.style().unpolish(bar)
    bar.style().polish(bar)


class MetricCard(QFrame):
    def __init__(self, title):
        super().__init__()
        self.setProperty("role", "snapshot-panel")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 16)
        layout.setSpacing(8)
        eyebrow = QLabel(title.upper())
        eyebrow.setProperty("role", "eyebrow")
        layout.addWidget(eyebrow)
        self.value_label = QLabel("--")
        self.value_label.setProperty("role", "metric")
        self.caption_label = QLabel("")
        self.caption_label.setProperty("role", "caption")
        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setTextVisible(False)
        layout.addWidget(self.value_label)
        layout.addWidget(self.bar)
        layout.addWidget(self.caption_label)

    def update_value(self, percent, value_text, caption_text):
        self.value_label.setText(value_text)
        self.caption_label.setText(caption_text)
        self.bar.setValue(int(percent))
        _set_bar_level(self.bar, percent)


class DashboardTab(QWidget):
    def __init__(self):
        super().__init__()
        self._last_net = sysinfo.get_network_counters()
        self._last_net_time = time.monotonic()
        sysinfo.prime_process_cpu_percent()

        outer = QVBoxLayout(self)

        cards_layout = QHBoxLayout()
        self.cpu_card = MetricCard("CPU")
        self.ram_card = MetricCard("Memory")
        self.disk_card = MetricCard("Primary Disk")
        self.net_card = MetricCard("Network")
        for card in (self.cpu_card, self.ram_card, self.disk_card, self.net_card):
            cards_layout.addWidget(card)
        outer.addLayout(cards_layout)

        mid_layout = QHBoxLayout()

        cores_panel, cores_body = section_panel("CPU CORES")
        cores_scroll = QScrollArea()
        cores_scroll.setWidgetResizable(True)
        cores_inner = QWidget()
        self.cores_grid = QGridLayout(cores_inner)
        cores_scroll.setWidget(cores_inner)
        cores_body.addWidget(cores_scroll)
        self._core_bars = []

        disks_panel, disks_body = section_panel("STORAGE DRIVES")
        disks_card, self.disks_rows = rows_card()
        disks_body.addWidget(disks_card)

        mid_layout.addWidget(cores_panel, 1)
        mid_layout.addWidget(disks_panel, 1)
        outer.addLayout(mid_layout, 1)

        procs_panel, procs_body = section_panel("TOP PROCESSES")
        procs_header = QHBoxLayout()
        self.process_status = QLabel("")
        self.process_status.setProperty("role", "caption")
        procs_header.addStretch(1)
        procs_header.addWidget(self.process_status)
        procs_body.addLayout(procs_header)
        procs_card, self.procs_rows = rows_card()
        procs_body.addWidget(procs_card)
        outer.addWidget(procs_panel, 1)

        self._process_end_buttons = []
        self._process_runner = ToolRunner(
            "dashboard-tools",
            self._set_process_busy,
            self.process_status,
            busy_text="Ending process...",
        )

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        # Timer starts in showEvent so it only runs while this tab is visible.

    def showEvent(self, event: QShowEvent):
        super().showEvent(event)
        self.refresh()
        if not self.timer.isActive():
            self.timer.start(_REFRESH_INTERVAL_MS)

    def hideEvent(self, event: QHideEvent):
        self.timer.stop()
        super().hideEvent(event)

    def refresh(self):
        self._refresh_cpu()
        self._refresh_memory()
        self._refresh_disks()
        self._refresh_network()
        self._refresh_processes()

    def _set_process_busy(self, busy):
        for button in self._process_end_buttons:
            button.setEnabled(not busy)

    def _confirm_end_process(self, pid, name):
        allowed, info = sysinfo.is_process_termination_allowed(pid, name)
        if not allowed:
            set_status_label(self.process_status, info, False)
            QMessageBox.warning(self, "Protected Process", info)
            return
        reply = QMessageBox.question(
            self,
            "Confirm End Process",
            f"End process {name} (PID {pid})?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        self._process_runner.start(toolbox.end_process, (pid,), self._on_end_process_result)

    def _on_end_process_result(self, result):
        set_status_label(self.process_status, result.summary, result.success)
        self.refresh()

    def _refresh_cpu(self):
        cpu = sysinfo.get_cpu_stats()
        freq_text = f"{cpu['freq_mhz']:.0f} MHz" if cpu["freq_mhz"] else ""
        self.cpu_card.update_value(cpu["percent"], f"{cpu['percent']:.0f}%", freq_text)

        per_core = cpu["per_core"]
        if len(self._core_bars) != len(per_core):
            for i in reversed(range(self.cores_grid.count())):
                self.cores_grid.itemAt(i).widget().deleteLater()
            self._core_bars = []
            cols = 2
            for i in range(len(per_core)):
                row_widget = QWidget()
                row_layout = QHBoxLayout(row_widget)
                row_layout.setContentsMargins(2, 2, 2, 2)
                label = QLabel(f"Core {i}")
                label.setFixedWidth(50)
                bar = QProgressBar()
                bar.setRange(0, 100)
                row_layout.addWidget(label)
                row_layout.addWidget(bar)
                self.cores_grid.addWidget(row_widget, i // cols, i % cols)
                self._core_bars.append(bar)

        for bar, value in zip(self._core_bars, per_core):
            bar.setValue(int(value))
            bar.setFormat(f"{value:.0f}%")
            bar.setTextVisible(True)
            _set_bar_level(bar, value)

    def _refresh_memory(self):
        mem = sysinfo.get_memory_stats()
        used_text = f"{sysinfo.format_bytes(mem['used'])} / {sysinfo.format_bytes(mem['total'])}"
        self.ram_card.update_value(mem["percent"], f"{mem['percent']:.0f}%", used_text)

    def _refresh_disks(self):
        drives = sysinfo.get_disk_usage()
        clear_layout(self.disks_rows)
        if not drives:
            self.disks_rows.addWidget(empty_row("No drives detected."))
        else:
            for d in drives:
                primary = f"{d['device']} ({d['mountpoint']})"
                secondary = f"{sysinfo.format_bytes(d['used'])} used / {sysinfo.format_bytes(d['free'])} free"
                meta = f"{d['percent']:.0f}%"
                self.disks_rows.addWidget(build_context_row(primary, secondary, meta))

        if drives:
            primary = next((d for d in drives if d["mountpoint"].lower().startswith("c:")), drives[0])
            caption = f"{sysinfo.format_bytes(primary['free'])} free"
            self.disk_card.update_value(primary["percent"], f"{primary['percent']:.0f}%", caption)

    def _refresh_network(self):
        now = time.monotonic()
        current = sysinfo.get_network_counters()
        elapsed = max(now - self._last_net_time, 0.001)
        sent_rate = (current["bytes_sent"] - self._last_net["bytes_sent"]) / elapsed
        recv_rate = (current["bytes_recv"] - self._last_net["bytes_recv"]) / elapsed
        self._last_net = current
        self._last_net_time = now

        total_rate = sent_rate + recv_rate
        display_percent = min(100, (total_rate / (10 * 1024 * 1024)) * 100)
        self.net_card.update_value(
            display_percent,
            f"{sysinfo.format_bytes(total_rate)}/s",
            f"↓ {sysinfo.format_bytes(recv_rate)}/s   ↑ {sysinfo.format_bytes(sent_rate)}/s",
        )

    def _refresh_processes(self):
        procs = sysinfo.get_top_processes(limit=10)
        clear_layout(self.procs_rows)
        self._process_end_buttons = []
        if not procs:
            self.procs_rows.addWidget(empty_row("No process data available."))
            return
        for p in procs:
            end_btn = QPushButton("End")
            end_btn.setProperty("variant", "card-danger")
            end_btn.clicked.connect(
                lambda checked=False, pid=p["pid"], name=p["name"]: self._confirm_end_process(pid, name)
            )
            secondary = f"PID {p['pid']} · {sysinfo.format_bytes(p['mem'])}"
            meta = f"{p['cpu']:.1f}% CPU"
            row = build_context_row(p["name"], secondary, meta, trailing=end_btn)
            self.procs_rows.addWidget(row)
            self._process_end_buttons.append(end_btn)
