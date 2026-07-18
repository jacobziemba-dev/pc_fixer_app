import re
from datetime import datetime

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QScrollArea, QPushButton,
)

from app import system_info as sysinfo
from app.ui_kit import build_context_row, clear_layout, empty_row, rows_card, section_panel


def _fmt_date(value):
    if not value:
        return "Unknown"
    match = re.match(r"/Date\((\d+)\)/", str(value))
    if match:
        try:
            return datetime.fromtimestamp(int(match.group(1)) / 1000).strftime("%Y-%m-%d")
        except (ValueError, OSError):
            return "Unknown"
    return str(value)


class HardwareWorker(QThread):
    finished_with_data = Signal(dict)

    def run(self):
        data = sysinfo.get_hardware_info()
        self.finished_with_data.emit(data)


class HardwareTab(QWidget):
    def __init__(self):
        super().__init__()
        outer = QVBoxLayout(self)

        header_layout = QHBoxLayout()
        title = QLabel("PC Setup Overview")
        title.setProperty("role", "heading")
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.setProperty("variant", "secondary")
        self.refresh_btn.clicked.connect(self.load)
        header_layout.addWidget(title)
        header_layout.addStretch(1)
        header_layout.addWidget(self.refresh_btn)
        outer.addLayout(header_layout)

        self.status_label = QLabel("Loading hardware details...")
        self.status_label.setProperty("role", "caption")
        outer.addWidget(self.status_label)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.content = QWidget()
        self.grid = QGridLayout(self.content)
        self.grid.setSpacing(12)
        scroll.setWidget(self.content)
        outer.addWidget(scroll, 1)

        self._worker = None
        self.load()

    def load(self):
        self.status_label.setText("Loading hardware details...")
        self.refresh_btn.setEnabled(False)
        self._worker = HardwareWorker()
        self._worker.finished_with_data.connect(self._on_loaded)
        self._worker.start()

    def _clear_grid(self):
        clear_layout(self.grid)

    def _make_group(self, title, rows):
        panel, body = section_panel(title.upper())
        card, card_rows = rows_card()
        if not rows:
            card_rows.addWidget(empty_row("No data available"))
        for label_text, value_text in rows:
            card_rows.addWidget(build_context_row(label_text, meta_text=value_text))
        body.addWidget(card)
        return panel

    def _on_loaded(self, data):
        self._clear_grid()
        self.status_label.setText("")
        self.refresh_btn.setEnabled(True)

        os_info = (data.get("os") or [{}])[0]
        system = (data.get("system") or [{}])[0]
        board = (data.get("board") or [{}])[0]
        bios = (data.get("bios") or [{}])[0]

        system_rows = [
            ("Manufacturer", system.get("Manufacturer") or "Unknown"),
            ("Model", system.get("Model") or "Unknown"),
            ("Motherboard", f"{board.get('Manufacturer', '')} {board.get('Product', '')}".strip() or "Unknown"),
            ("BIOS Version", bios.get("SMBIOSBIOSVersion") or "Unknown"),
            ("OS", os_info.get("Caption") or "Unknown"),
            ("OS Version", f"{os_info.get('Version', '')} ({os_info.get('OSArchitecture', '')})"),
            ("OS Installed", _fmt_date(os_info.get("InstallDate"))),
            ("Boot Time", datetime.fromtimestamp(data.get("boot_time", 0)).strftime("%Y-%m-%d %H:%M")
                if data.get("boot_time") else "Unknown"),
        ]

        cpu_rows = []
        for cpu in data.get("cpu") or []:
            cpu_rows.append(("Model", cpu.get("Name", "Unknown").strip()))
            cpu_rows.append(("Cores / Threads",
                              f"{cpu.get('NumberOfCores', '?')} cores / {cpu.get('NumberOfLogicalProcessors', '?')} threads"))
            cpu_rows.append(("Max Clock Speed", f"{cpu.get('MaxClockSpeed', '?')} MHz"))
        if not cpu_rows:
            cpu_rows.append(("Cores / Threads",
                              f"{data.get('physical_cores', '?')} cores / {data.get('logical_cores', '?')} threads"))

        gpu_rows = []
        for gpu in data.get("gpu") or []:
            name = gpu.get("Name")
            if not name:
                continue
            ram = gpu.get("AdapterRAM")
            ram_text = sysinfo.format_bytes(ram) if ram else "Unknown"
            gpu_rows.append((name, f"VRAM: {ram_text}"))
        if not gpu_rows:
            gpu_rows = [("Graphics", "No GPU information available")]

        memory_rows = []
        modules = data.get("memory_modules") or []
        if modules:
            total = sum(int(m.get("Capacity") or 0) for m in modules)
            memory_rows.append(("Total Installed", sysinfo.format_bytes(total)))
            memory_rows.append(("Modules", f"{len(modules)} stick(s)"))
            for i, m in enumerate(modules):
                cap = sysinfo.format_bytes(int(m.get("Capacity") or 0))
                speed = m.get("Speed", "?")
                slot = m.get("DeviceLocator", f"Slot {i}")
                memory_rows.append((slot, f"{cap} @ {speed} MHz"))
        else:
            memory_rows.append(("Total Installed", sysinfo.format_bytes(system.get("TotalPhysicalMemory", 0))))

        storage_rows = []
        phys_disks = data.get("physical_disks") or []
        if phys_disks:
            for d in phys_disks:
                name = d.get("FriendlyName", "Disk")
                media = d.get("MediaType", "Unknown")
                size = sysinfo.format_bytes(d.get("Size") or 0)
                health = d.get("HealthStatus", "")
                storage_rows.append((name, f"{size} - {media} - {health}"))
        else:
            for d in data.get("disk_drives") or []:
                name = d.get("Model", "Disk")
                size = sysinfo.format_bytes(d.get("Size") or 0)
                iface = d.get("InterfaceType", "")
                storage_rows.append((name, f"{size} - {iface}"))

        self.grid.addWidget(self._make_group("System", system_rows), 0, 0)
        self.grid.addWidget(self._make_group("Processor", cpu_rows), 0, 1)
        self.grid.addWidget(self._make_group("Graphics", gpu_rows), 1, 0)
        self.grid.addWidget(self._make_group("Memory", memory_rows), 1, 1)
        self.grid.addWidget(self._make_group("Storage", storage_rows), 2, 0, 1, 2)
