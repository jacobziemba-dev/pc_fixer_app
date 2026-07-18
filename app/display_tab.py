from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QMessageBox,
)

from app import system_info as sysinfo
from app.job_queue import get_job_queue
from app.ui_kit import section_panel


class DisplayLoadWorker(QThread):
    finished_with_data = Signal(list, dict, dict, str)

    def run(self):
        try:
            devices = sysinfo.get_display_devices()
            modes = {}
            rates = {}
            for device in devices:
                modes[device.name] = sysinfo.get_current_display_mode(device.name)
                rates[device.name] = sysinfo.get_supported_refresh_rates(device.name)
            self.finished_with_data.emit(devices, modes, rates, "")
        except Exception as exc:
            self.finished_with_data.emit([], {}, {}, str(exc))


class ApplyRefreshWorker(QThread):
    finished_with_result = Signal(object)

    def __init__(self, device_name, hz):
        super().__init__()
        self._device_name = device_name
        self._hz = hz

    def run(self):
        try:
            result = sysinfo.set_display_refresh_rate(self._device_name, self._hz)
        except Exception as exc:
            result = sysinfo.DisplayChangeResult(False, -999, f"Display change failed: {exc}")
        self.finished_with_result.emit(result)


class DisplayTab(QWidget):
    def __init__(self):
        super().__init__()
        outer = QVBoxLayout(self)

        header_layout = QHBoxLayout()
        title = QLabel("Display Refresh Rate")
        title.setProperty("role", "heading")
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.setProperty("variant", "secondary")
        self.refresh_btn.clicked.connect(self.load)
        header_layout.addWidget(title)
        header_layout.addStretch(1)
        header_layout.addWidget(self.refresh_btn)
        outer.addLayout(header_layout)

        subtitle = QLabel(
            "Change only the refresh rate for the selected monitor. Resolution, scaling, HDR, "
            "color format, and bit depth are left untouched."
        )
        subtitle.setProperty("role", "caption")
        subtitle.setWordWrap(True)
        outer.addWidget(subtitle)

        selector_group, selector_layout = section_panel("CHOOSE MONITOR TO CHANGE")
        selector_label = QLabel("Pick which connected display gets the refresh-rate change.")
        selector_label.setProperty("role", "caption")
        selector_label.setWordWrap(True)
        self.monitor_combo = QComboBox()
        self.monitor_combo.currentIndexChanged.connect(self._on_monitor_changed)
        selector_layout.addWidget(selector_label)
        selector_layout.addWidget(self.monitor_combo)
        outer.addWidget(selector_group)

        info_group, info_layout = section_panel("CURRENT DISPLAY MODE")
        self.name_label = QLabel("--")
        self.device_label = QLabel("--")
        self.device_label.setProperty("role", "caption")
        self.resolution_label = QLabel("Resolution: --")
        self.refresh_label = QLabel("Refresh rate: --")
        self.bit_depth_label = QLabel("Bit depth: --")
        for label in (
            self.name_label,
            self.device_label,
            self.resolution_label,
            self.refresh_label,
            self.bit_depth_label,
        ):
            label.setWordWrap(True)
            info_layout.addWidget(label)
        outer.addWidget(info_group)

        change_group, change_body = section_panel("CHOOSE A REFRESH RATE")
        change_layout = QHBoxLayout()
        change_layout.setSpacing(8)
        self.rate_combo = QComboBox()
        self.apply_btn = QPushButton("Apply Refresh Rate")
        self.apply_btn.clicked.connect(self.confirm_and_apply)
        self.revert_btn = QPushButton("Revert Last Change")
        self.revert_btn.setProperty("variant", "secondary")
        self.revert_btn.setEnabled(False)
        self.revert_btn.clicked.connect(self.confirm_and_revert)
        change_layout.addWidget(self.rate_combo, 1)
        change_layout.addWidget(self.apply_btn)
        change_layout.addWidget(self.revert_btn)
        change_body.addLayout(change_layout)
        outer.addWidget(change_group)

        self.status_label = QLabel("Loading display details...")
        self.status_label.setProperty("role", "caption")
        self.status_label.setWordWrap(True)
        outer.addWidget(self.status_label)
        outer.addStretch(1)

        self._devices = []
        self._modes = {}
        self._rates = {}
        self._previous_change = None
        self._pending_previous = None
        self._pending_action = ""
        self._post_load_status = ""
        self._reload_after_apply = False
        self.load()

    def load(self):
        worker = DisplayLoadWorker()
        get_job_queue().submit(
            scope="display",
            title="Loading connected displays...",
            worker=worker,
            result_signal="finished_with_data",
            on_started=self._on_load_started,
            on_result=self._on_loaded,
            on_finished=self._on_display_worker_finished,
            on_rejected=lambda message: self.status_label.setText(message),
        )

    def _on_load_started(self):
        self.refresh_btn.setEnabled(False)
        self.apply_btn.setEnabled(False)
        self.revert_btn.setEnabled(False)
        self.status_label.setText("Loading connected displays...")

    def _on_display_worker_finished(self):
        self.refresh_btn.setEnabled(True)
        self.revert_btn.setEnabled(bool(self._previous_change))
        self._on_monitor_changed()
        if self._reload_after_apply:
            self._reload_after_apply = False
            self.load()

    def _on_loaded(self, devices, modes, rates, error):
        self._devices = devices
        self._modes = modes
        self._rates = rates

        self.monitor_combo.blockSignals(True)
        self.monitor_combo.clear()
        for display_number, device in enumerate(devices, start=1):
            self.monitor_combo.addItem(
                self._monitor_choice_label(display_number, device, modes.get(device.name)),
                device.name,
            )
        self.monitor_combo.blockSignals(False)

        if error:
            self.status_label.setText(f"Could not load display information: {error}")
        elif not devices:
            self.status_label.setText("No attached desktop displays were found.")
        elif self._post_load_status:
            self.status_label.setText(self._post_load_status)
            self._post_load_status = ""
        else:
            self.status_label.setText("Choose a monitor, then choose a supported refresh rate.")

        self._on_monitor_changed()

    def _selected_device_name(self):
        index = self.monitor_combo.currentIndex()
        if index < 0:
            return ""
        return self.monitor_combo.itemData(index)

    def _selected_device(self):
        name = self._selected_device_name()
        return next((device for device in self._devices if device.name == name), None)

    def _on_monitor_changed(self):
        device = self._selected_device()
        self.rate_combo.clear()

        if not device:
            self.name_label.setText("--")
            self.device_label.setText("--")
            self.resolution_label.setText("Resolution: --")
            self.refresh_label.setText("Refresh rate: --")
            self.bit_depth_label.setText("Bit depth: --")
            self.apply_btn.setEnabled(False)
            return

        mode = self._modes.get(device.name)
        rates = self._rates.get(device.name, [])
        for hz in rates:
            self.rate_combo.addItem(f"{hz} Hz", hz)

        display_number = self.monitor_combo.currentIndex() + 1
        primary = "Primary monitor" if device.is_primary else "Secondary monitor"
        self.name_label.setText(f"Display {display_number}: {device.label}")
        adapter = f" on {device.adapter_label}" if device.adapter_label else ""
        self.device_label.setText(f"{primary}{adapter} - {device.name}")
        if mode:
            self.resolution_label.setText(f"Resolution: {mode.width} x {mode.height}")
            self.refresh_label.setText(f"Refresh rate: {mode.refresh_hz} Hz")
            self.bit_depth_label.setText(f"Bit depth: {mode.bit_depth}-bit")
            match_index = self.rate_combo.findData(mode.refresh_hz)
            if match_index >= 0:
                self.rate_combo.setCurrentIndex(match_index)
        else:
            self.resolution_label.setText("Resolution: Unknown")
            self.refresh_label.setText("Refresh rate: Unknown")
            self.bit_depth_label.setText("Bit depth: Unknown")

        self.apply_btn.setEnabled(bool(rates and mode))

    def confirm_and_apply(self):
        device = self._selected_device()
        current = self._modes.get(device.name) if device else None
        target_hz = self.rate_combo.currentData()
        if not device or not current or target_hz is None:
            return
        if int(target_hz) == int(current.refresh_hz):
            self.status_label.setText("That refresh rate is already active.")
            return

        reply = QMessageBox.question(
            self,
            "Confirm Refresh Rate",
            f"Change {device.label} from {current.refresh_hz} Hz to {target_hz} Hz?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        self._start_apply(device.name, int(target_hz), current.refresh_hz, "apply")

    def confirm_and_revert(self):
        if not self._previous_change:
            return
        device_name, previous_hz, label = self._previous_change
        reply = QMessageBox.question(
            self,
            "Confirm Revert",
            f"Revert {label} to {previous_hz} Hz?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        current = self._modes.get(device_name)
        current_hz = current.refresh_hz if current else None
        self._start_apply(device_name, int(previous_hz), current_hz, "revert")

    def _start_apply(self, device_name, target_hz, previous_hz, action):
        self._pending_previous = (device_name, previous_hz, self._label_for_device(device_name))
        self._pending_action = action
        worker = ApplyRefreshWorker(device_name, target_hz)
        get_job_queue().submit(
            scope="display",
            title=f"Changing refresh rate to {target_hz} Hz...",
            worker=worker,
            result_signal="finished_with_result",
            on_started=lambda: self._on_apply_started(target_hz),
            on_result=self._on_applied,
            on_finished=self._on_display_worker_finished,
            on_rejected=lambda message: self.status_label.setText(message),
        )

    def _on_apply_started(self, target_hz):
        self.apply_btn.setEnabled(False)
        self.revert_btn.setEnabled(False)
        self.refresh_btn.setEnabled(False)
        self.status_label.setText(f"Changing refresh rate to {target_hz} Hz...")

    def _on_applied(self, result):
        if result.success:
            if self._pending_action == "apply":
                self._previous_change = self._pending_previous
            elif self._pending_action == "revert":
                self._previous_change = None
            self.revert_btn.setEnabled(bool(self._previous_change))
            self._post_load_status = result.message
            self._reload_after_apply = True
            return

        self.revert_btn.setEnabled(bool(self._previous_change))
        self.status_label.setText(result.message)
        self._on_monitor_changed()

    def _label_for_device(self, device_name):
        device = next((item for item in self._devices if item.name == device_name), None)
        return device.label if device else device_name

    def _monitor_choice_label(self, display_number, device, mode):
        primary = "Primary" if device.is_primary else "Secondary"
        if mode:
            details = f"{mode.width} x {mode.height} @ {mode.refresh_hz} Hz"
        else:
            details = "Current mode unknown"
        adapter = f" - {device.adapter_label}" if device.adapter_label else ""
        return f"Display {display_number} - {device.label} - {primary} - {details}{adapter}"
