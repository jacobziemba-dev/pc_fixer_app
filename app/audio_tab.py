from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QComboBox, QCheckBox,
    QSlider, QAbstractItemView, QProgressBar,
)

from app import audio_control as audio


class AudioTab(QWidget):
    """Per-app playback routing and volume controls.

    Windows audio COM (pycaw / winappaudiorouter) must run on the Qt GUI
    thread (STA). Background QThreads crash under this stack, so load,
    routing, volume, and peak polling all happen on the main thread.
    """

    COL_APP = 0
    COL_PEAK = 1
    COL_VOLUME = 2
    COL_DEVICE = 3
    COL_MUTE = 4

    def __init__(self):
        super().__init__()
        outer = QVBoxLayout(self)

        header_layout = QHBoxLayout()
        title = QLabel("Audio Devices & App Routing")
        title.setProperty("role", "heading")
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.setProperty("variant", "secondary")
        self.refresh_btn.clicked.connect(self.load)
        header_layout.addWidget(title)
        header_layout.addStretch(1)
        header_layout.addWidget(self.refresh_btn)
        outer.addLayout(header_layout)

        subtitle = QLabel(
            "Route each app with an active audio session to any playback device. "
            "Requires Windows 10 1803+. Some apps need a short pause/play after routing. "
            "Exclusive-mode streams may show a flat peak meter."
        )
        subtitle.setProperty("role", "caption")
        subtitle.setWordWrap(True)
        outer.addWidget(subtitle)

        controls = QHBoxLayout()
        self.safe_ear_check = QCheckBox("Safe-ear guard")
        self.safe_ear_check.setToolTip(
            "When enabled, temporarily lowers an app's volume if its peak stays above 0.9."
        )
        self.safe_ear_check.toggled.connect(self._on_safe_ear_toggled)
        controls.addWidget(self.safe_ear_check)
        controls.addStretch(1)
        outer.addLayout(controls)

        table_group = QGroupBox("Active App Sessions")
        table_layout = QVBoxLayout(table_group)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["App", "Peak", "Volume", "Output device", "Mute"])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(self.COL_APP, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(self.COL_PEAK, QHeaderView.Fixed)
        self.table.horizontalHeader().setSectionResizeMode(self.COL_VOLUME, QHeaderView.Fixed)
        self.table.horizontalHeader().setSectionResizeMode(self.COL_DEVICE, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(self.COL_MUTE, QHeaderView.ResizeToContents)
        self.table.setColumnWidth(self.COL_PEAK, 120)
        self.table.setColumnWidth(self.COL_VOLUME, 140)
        table_layout.addWidget(self.table)
        outer.addWidget(table_group, 1)

        self.status_label = QLabel("Loading audio devices and sessions...")
        self.status_label.setProperty("role", "caption")
        self.status_label.setWordWrap(True)
        outer.addWidget(self.status_label)

        self._devices: list[audio.OutputDevice] = []
        self._sessions: list[audio.OutputSession] = []
        self._row_by_pid: dict[int, int] = {}
        self._user_volumes: dict[int, float] = {}
        self._normalizer = audio.PeakNormalizer()
        self._updating_ui = False
        self._visible = False
        self._routing = False

        self._peak_timer = QTimer(self)
        self._peak_timer.setInterval(200)
        self._peak_timer.timeout.connect(self._poll_peaks)

        # Defer first load so the tab paints before COM work.
        QTimer.singleShot(0, self.load)

    def showEvent(self, event):
        super().showEvent(event)
        self._visible = True
        if not self._peak_timer.isActive():
            self._peak_timer.start()

    def hideEvent(self, event):
        super().hideEvent(event)
        self._visible = False
        self._peak_timer.stop()

    def load(self):
        self.refresh_btn.setEnabled(False)
        self.status_label.setText("Loading audio devices and sessions...")
        try:
            devices = audio.list_output_devices()
            sessions = audio.list_output_sessions()
            error = ""
        except Exception as exc:
            devices, sessions, error = [], [], str(exc)
        self._on_loaded(devices, sessions, error)

    def _on_loaded(self, devices, sessions, error):
        self.refresh_btn.setEnabled(True)
        self._devices = devices
        self._sessions = sessions

        if error:
            self.status_label.setText(f"Could not load audio information: {error}")
        elif not sessions:
            self.status_label.setText(
                "No active app audio sessions found. Start playback in an app, then refresh."
            )
        else:
            self.status_label.setText(
                f"{len(sessions)} app session(s), {len(devices)} playback device(s)."
            )

        self._rebuild_table()
        active_pids = {session.pid for session in sessions}
        self._normalizer.prune(active_pids)
        for pid in list(self._user_volumes):
            if pid not in active_pids:
                self._user_volumes.pop(pid, None)

    def _rebuild_table(self):
        self._updating_ui = True
        self.table.setRowCount(0)
        self._row_by_pid.clear()

        for session in self._sessions:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self._row_by_pid[session.pid] = row

            app_item = QTableWidgetItem(session.display_name)
            app_item.setData(Qt.UserRole, session.pid)
            app_item.setToolTip(session.process_name)
            self.table.setItem(row, self.COL_APP, app_item)

            peak_bar = QProgressBar()
            peak_bar.setRange(0, 100)
            peak_bar.setValue(0)
            peak_bar.setTextVisible(False)
            peak_bar.setFixedHeight(12)
            self.table.setCellWidget(row, self.COL_PEAK, peak_bar)

            volume_slider = QSlider(Qt.Horizontal)
            volume_slider.setRange(0, 100)
            volume_slider.setValue(int(round(session.volume * 100)))
            volume_slider.setToolTip(f"{int(round(session.volume * 100))}%")
            volume_slider.valueChanged.connect(
                lambda value, pid=session.pid: self._on_volume_changed(pid, value)
            )
            self.table.setCellWidget(row, self.COL_VOLUME, volume_slider)

            device_combo = QComboBox()
            device_combo.addItem("System default", "")
            for device in self._devices:
                label = device.name
                if device.is_default:
                    label = f"{device.name} (system default)"
                device_combo.addItem(label, device.id)

            selected_id = audio.match_device_id(self._devices, session.device_id)
            index = device_combo.findData(selected_id)
            if index < 0:
                index = 0
            device_combo.setCurrentIndex(index)
            device_combo.currentIndexChanged.connect(
                lambda _index, pid=session.pid, name=session.process_name, combo=device_combo:
                self._on_device_changed(pid, name, combo)
            )
            self.table.setCellWidget(row, self.COL_DEVICE, device_combo)

            mute_check = QCheckBox()
            mute_check.setChecked(session.muted)
            mute_check.toggled.connect(
                lambda checked, pid=session.pid: self._on_mute_toggled(pid, checked)
            )
            mute_wrap = QWidget()
            mute_layout = QHBoxLayout(mute_wrap)
            mute_layout.setContentsMargins(8, 0, 8, 0)
            mute_layout.addStretch(1)
            mute_layout.addWidget(mute_check)
            mute_layout.addStretch(1)
            self.table.setCellWidget(row, self.COL_MUTE, mute_wrap)

            self._user_volumes.setdefault(session.pid, session.volume)
            self._normalizer.set_user_volume(session.pid, self._user_volumes[session.pid])

        self._updating_ui = False

    def _on_device_changed(self, pid, process_name, combo):
        if self._updating_ui or self._routing:
            return
        device_id = combo.currentData() or ""
        label = combo.currentText()
        self.status_label.setText(f"Routing to {label}...")
        self._routing = True
        try:
            if device_id:
                result = audio.set_app_output_device(
                    process_id=pid,
                    process_name=process_name,
                    device=device_id,
                )
            else:
                result = audio.clear_app_output_device(
                    process_id=pid,
                    process_name=process_name,
                )
        except Exception as exc:
            result = audio.RouteResult(False, f"Routing failed: {exc}", pid=pid)
        finally:
            self._routing = False
        self.status_label.setText(result.message)

    def _on_volume_changed(self, pid, value):
        if self._updating_ui:
            return
        level = max(0.0, min(1.0, value / 100.0))
        self._user_volumes[pid] = level
        self._normalizer.set_user_volume(pid, level)
        slider = self._volume_slider_for(pid)
        if slider is not None:
            slider.setToolTip(f"{value}%")
        if not audio.set_session_volume(pid, level):
            self.status_label.setText("Could not update session volume.")

    def _on_mute_toggled(self, pid, muted):
        if self._updating_ui:
            return
        if not audio.set_session_mute(pid, muted):
            self.status_label.setText("Could not update session mute.")

    def _on_safe_ear_toggled(self, enabled):
        if enabled:
            self.status_label.setText("Safe-ear guard enabled.")
            return
        self.status_label.setText("Safe-ear guard disabled.")
        for pid, volume in self._user_volumes.items():
            audio.set_session_volume(pid, volume)
            self._set_volume_slider(pid, volume)

    def _poll_peaks(self):
        if not self._visible or self._routing:
            return
        pids = list(self._row_by_pid)
        if not pids:
            return
        try:
            peaks = audio.get_session_peaks(pids)
        except Exception:
            return
        for pid, peak in peaks.items():
            self._set_peak_bar(pid, peak)
            if not self.safe_ear_check.isChecked():
                continue
            current = self._user_volumes.get(pid)
            new_volume = self._normalizer.process_peak(pid, peak, current_volume=current)
            if new_volume is None:
                continue
            audio.set_session_volume(pid, new_volume)
            self._set_volume_slider(pid, new_volume, from_normalizer=True)

    def _set_peak_bar(self, pid, peak):
        row = self._row_by_pid.get(pid)
        if row is None:
            return
        bar = self.table.cellWidget(row, self.COL_PEAK)
        if bar is None:
            return
        value = int(round(max(0.0, min(1.0, float(peak))) * 100))
        bar.setValue(value)
        if value >= 90:
            bar.setProperty("level", "danger")
        elif value >= 70:
            bar.setProperty("level", "warn")
        else:
            bar.setProperty("level", "")
        bar.style().unpolish(bar)
        bar.style().polish(bar)

    def _volume_slider_for(self, pid):
        row = self._row_by_pid.get(pid)
        if row is None:
            return None
        return self.table.cellWidget(row, self.COL_VOLUME)

    def _set_volume_slider(self, pid, level, from_normalizer=False):
        slider = self._volume_slider_for(pid)
        if slider is None:
            return
        self._updating_ui = True
        slider.setValue(int(round(max(0.0, min(1.0, level)) * 100)))
        slider.setToolTip(f"{slider.value()}%")
        self._updating_ui = False
        if not from_normalizer:
            self._user_volumes[pid] = level
