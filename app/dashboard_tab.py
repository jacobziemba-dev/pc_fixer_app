import time

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QShowEvent, QHideEvent
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox, QLabel,
    QProgressBar, QTableWidget, QTableWidgetItem, QHeaderView, QScrollArea,
)

from app import system_info as sysinfo

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


def _set_table_cell(table, row, col, text, user_data=None):
    item = table.item(row, col)
    if item is None:
        item = QTableWidgetItem(text)
        table.setItem(row, col, item)
    else:
        item.setText(text)
    if user_data is not None:
        item.setData(Qt.UserRole, user_data)


class MetricCard(QGroupBox):
    def __init__(self, title):
        super().__init__(title)
        layout = QVBoxLayout(self)
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

        cores_group = QGroupBox("CPU Cores")
        self.cores_layout = QVBoxLayout(cores_group)
        cores_scroll = QScrollArea()
        cores_scroll.setWidgetResizable(True)
        cores_inner = QWidget()
        self.cores_grid = QGridLayout(cores_inner)
        cores_scroll.setWidget(cores_inner)
        self.cores_layout.addWidget(cores_scroll)
        self._core_bars = []

        disks_group = QGroupBox("Storage Drives")
        disks_layout = QVBoxLayout(disks_group)
        self.disks_table = QTableWidget(0, 4)
        self.disks_table.setHorizontalHeaderLabels(["Drive", "Used", "Free", "Usage"])
        self.disks_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.disks_table.verticalHeader().setVisible(False)
        self.disks_table.setAlternatingRowColors(True)
        self.disks_table.setEditTriggers(QTableWidget.NoEditTriggers)
        disks_layout.addWidget(self.disks_table)

        mid_layout.addWidget(cores_group, 1)
        mid_layout.addWidget(disks_group, 1)
        outer.addLayout(mid_layout, 1)

        procs_group = QGroupBox("Top Processes")
        procs_layout = QVBoxLayout(procs_group)
        self.procs_table = QTableWidget(0, 4)
        self.procs_table.setHorizontalHeaderLabels(["PID", "Process", "CPU %", "Memory"])
        self.procs_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.procs_table.verticalHeader().setVisible(False)
        self.procs_table.setAlternatingRowColors(True)
        self.procs_table.setEditTriggers(QTableWidget.NoEditTriggers)
        procs_layout.addWidget(self.procs_table)
        outer.addWidget(procs_group, 1)

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
        self.disks_table.setRowCount(len(drives))
        for row, d in enumerate(drives):
            _set_table_cell(self.disks_table, row, 0, f"{d['device']} ({d['mountpoint']})")
            _set_table_cell(self.disks_table, row, 1, sysinfo.format_bytes(d["used"]))
            _set_table_cell(self.disks_table, row, 2, sysinfo.format_bytes(d["free"]))
            _set_table_cell(self.disks_table, row, 3, f"{d['percent']:.0f}%")

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
        self.procs_table.setRowCount(len(procs))
        for row, p in enumerate(procs):
            _set_table_cell(self.procs_table, row, 0, str(p["pid"]))
            _set_table_cell(self.procs_table, row, 1, p["name"])
            _set_table_cell(self.procs_table, row, 2, f"{p['cpu']:.1f}")
            _set_table_cell(self.procs_table, row, 3, sysinfo.format_bytes(p["mem"]))
