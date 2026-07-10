from datetime import datetime

from PySide6.QtCore import QTimer, QThread, Signal, Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox, QInputDialog,
    QSplitter, QAbstractItemView,
)

from app import window_layouts


class LayoutScanWorker(QThread):
    finished_with_items = Signal(list, list, str, str)

    def __init__(self, purpose):
        super().__init__()
        self._purpose = purpose

    def run(self):
        try:
            items = window_layouts.collect_current_window_items()
            displays = window_layouts.collect_current_display_items()
            self.finished_with_items.emit(items, displays, "", self._purpose)
        except Exception as exc:
            self.finished_with_items.emit([], [], str(exc), self._purpose)


class LayoutApplyWorker(QThread):
    finished_with_result = Signal(object, str)

    def __init__(self, layout):
        super().__init__()
        self._layout = layout

    def run(self):
        try:
            result = window_layouts.apply_layout(self._layout, launch_missing=True)
            self.finished_with_result.emit(result, "")
        except Exception as exc:
            self.finished_with_result.emit(None, str(exc))


class LayoutPreviewCanvas(QWidget):
    WINDOW_COLORS = [
        QColor("#5c7cfa"),
        QColor("#2fb380"),
        QColor("#d9902f"),
        QColor("#d95c5c"),
        QColor("#8b6fe8"),
    ]
    CANVAS_COLOR = QColor("#22242b")
    MONITOR_COLOR = QColor("#292c35")
    MONITOR_BORDER = QColor("#454a58")
    MONITOR_TEXT = QColor("#f2f4fb")
    MUTED_TEXT = QColor("#a6a9b8")
    WINDOW_TEXT = QColor("#ffffff")

    def __init__(self, layout=None):
        super().__init__()
        self._layout = layout or {"displays": [], "windows": []}
        self.setMinimumSize(760, 380)

    def set_layout(self, layout):
        self._layout = layout or {"displays": [], "windows": []}
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), self.CANVAS_COLOR)

        scene = window_layouts.build_preview_scene(self._layout, self.width(), self.height(), 32)
        if not scene["monitors"]:
            self._draw_center_message(painter, "No connected displays found.")
            return

        for monitor in scene["monitors"]:
            self._draw_monitor(painter, monitor)

        if not scene["windows"]:
            self._draw_center_message(painter, "No app windows selected for this layout.")
            return

        metrics = QFontMetrics(painter.font())
        for index, window in enumerate(scene["windows"]):
            self._draw_window(painter, metrics, window, index)

    def _draw_center_message(self, painter, message):
        painter.save()
        font = painter.font()
        font.setWeight(QFont.DemiBold)
        painter.setFont(font)
        painter.setPen(self.MUTED_TEXT)
        painter.drawText(self.rect(), Qt.AlignCenter, message)
        painter.restore()

    def _draw_monitor(self, painter, monitor):
        painter.save()
        rect = monitor["preview_rect"]
        x = rect["x"]
        y = rect["y"]
        width = rect["width"]
        height = rect["height"]
        painter.setBrush(self.MONITOR_COLOR)
        painter.setPen(QPen(self.MONITOR_BORDER, 1))
        painter.drawRoundedRect(x, y, width, height, 8, 8)

        if width < 80 or height < 42:
            painter.restore()
            return

        title_font = painter.font()
        title_font.setWeight(QFont.DemiBold)
        painter.setFont(title_font)
        title_metrics = QFontMetrics(title_font)
        painter.setPen(self.MONITOR_TEXT)
        label = title_metrics.elidedText(monitor.get("label", "Display"), Qt.ElideRight, max(width - 24, 10))
        painter.drawText(x + 12, y + 22, label)

        detail_font = painter.font()
        detail_font.setWeight(QFont.Normal)
        detail_font.setPointSize(max(detail_font.pointSize() - 1, 8))
        painter.setFont(detail_font)
        detail_metrics = QFontMetrics(detail_font)
        details = []
        if monitor.get("resolution"):
            details.append(monitor["resolution"])
        if monitor.get("device"):
            details.append(monitor["device"])
        if monitor.get("is_primary"):
            details.append("Primary")
        detail_text = " - ".join(details)
        if detail_text and height > 58:
            detail_text = detail_metrics.elidedText(detail_text, Qt.ElideRight, max(width - 24, 10))
            painter.setPen(self.MUTED_TEXT)
            painter.drawText(x + 12, y + 40, detail_text)
        painter.restore()

    def _draw_window(self, painter, metrics, window, index):
        painter.save()
        rect = window["preview_rect"]
        x = rect["x"]
        y = rect["y"]
        width = rect["width"]
        height = rect["height"]
        if width <= 0 or height <= 0:
            painter.restore()
            return

        color = self.WINDOW_COLORS[index % len(self.WINDOW_COLORS)]
        title_bar = min(max(height // 5, 16), 24)
        painter.setBrush(QColor(0, 0, 0, 68))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(x + 4, y + 5, width, height, 5, 5)
        painter.setBrush(color)
        painter.setPen(QPen(QColor("#e4e8ff"), 1))
        painter.drawRoundedRect(x, y, width, height, 5, 5)
        painter.fillRect(x + 1, y + 1, max(width - 2, 1), max(min(title_bar, height - 2), 1), QColor(0, 0, 0, 54))

        if width < 38 or height < 24:
            painter.restore()
            return

        text_x = x + 7
        text_width = max(width - 14, 10)
        app_text = metrics.elidedText(window.get("app") or "App", Qt.ElideRight, text_width)
        painter.setPen(self.WINDOW_TEXT)
        painter.drawText(text_x, y + 4, text_width, title_bar, Qt.AlignLeft | Qt.AlignVCenter, app_text)
        layer_text = window.get("layer_label") or ""
        if layer_text and width > 96:
            layer_width = min(metrics.horizontalAdvance(layer_text) + 12, max(width // 3, 34))
            painter.setPen(QColor("#f7f8ff"))
            painter.drawText(
                x + width - layer_width - 6,
                y + 4,
                layer_width,
                title_bar,
                Qt.AlignRight | Qt.AlignVCenter,
                layer_text,
            )

        if width > 130 and height > 52:
            label = metrics.elidedText(window.get("label") or "", Qt.ElideRight, text_width)
            painter.setPen(QColor("#eef1ff"))
            painter.drawText(
                text_x,
                y + title_bar + 6,
                text_width,
                max(height - title_bar - 12, 12),
                Qt.AlignLeft | Qt.AlignTop,
                label,
            )
        painter.restore()


class LayoutsTab(QWidget):
    REFRESH_INTERVAL_MS = 5000

    def __init__(self):
        super().__init__()
        outer = QVBoxLayout(self)

        header_layout = QHBoxLayout()
        title = QLabel("Layouts")
        title.setProperty("role", "heading")
        self.save_btn = QPushButton("Save Current Layout")
        self.save_btn.clicked.connect(self.save_current_layout)
        header_layout.addWidget(title)
        header_layout.addStretch(1)
        header_layout.addWidget(self.save_btn)
        outer.addLayout(header_layout)

        desktop_group = QGroupBox("Current Desktop")
        desktop_layout = QVBoxLayout(desktop_group)
        desktop_splitter = QSplitter(Qt.Horizontal)

        preview_group = QGroupBox("Live Preview")
        preview_layout = QVBoxLayout(preview_group)
        self.preview = LayoutPreviewCanvas()
        preview_layout.addWidget(self.preview)

        apps_group = QGroupBox("Current Apps")
        apps_layout = QVBoxLayout(apps_group)
        self.current_apps_table = QTableWidget(0, 4)
        self.current_apps_table.setHorizontalHeaderLabels(["App", "Window", "Display", "Position"])
        self.current_apps_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.current_apps_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.current_apps_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.current_apps_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.current_apps_table.verticalHeader().setVisible(False)
        self.current_apps_table.setAlternatingRowColors(True)
        self.current_apps_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.current_apps_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.current_apps_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.current_apps_table.itemSelectionChanged.connect(self._update_current_app_actions)
        apps_layout.addWidget(self.current_apps_table)

        app_actions = QHBoxLayout()
        self.remove_app_btn = QPushButton("Remove")
        self.remove_app_btn.setProperty("variant", "secondary")
        self.remove_app_btn.clicked.connect(self.remove_selected_current_app)
        self.show_all_btn = QPushButton("Show All")
        self.show_all_btn.setProperty("variant", "secondary")
        self.show_all_btn.clicked.connect(self.restore_removed_apps)
        app_actions.addWidget(self.remove_app_btn)
        app_actions.addWidget(self.show_all_btn)
        app_actions.addStretch(1)
        apps_layout.addLayout(app_actions)

        desktop_splitter.addWidget(preview_group)
        desktop_splitter.addWidget(apps_group)
        desktop_splitter.setStretchFactor(0, 3)
        desktop_splitter.setStretchFactor(1, 1)
        desktop_layout.addWidget(desktop_splitter)
        outer.addWidget(desktop_group, 2)

        splitter = QSplitter(Qt.Horizontal)

        layouts_group = QGroupBox("Saved Layouts")
        layouts_layout = QVBoxLayout(layouts_group)
        self.layouts_table = QTableWidget(0, 4)
        self.layouts_table.setHorizontalHeaderLabels(["Name", "Windows", "Displays", "Updated"])
        self.layouts_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.layouts_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.layouts_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.layouts_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.layouts_table.verticalHeader().setVisible(False)
        self.layouts_table.setAlternatingRowColors(True)
        self.layouts_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.layouts_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.layouts_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.layouts_table.itemSelectionChanged.connect(self._on_layout_selected)
        layouts_layout.addWidget(self.layouts_table)

        layout_actions = QHBoxLayout()
        self.load_layout_btn = QPushButton("Load Layout")
        self.load_layout_btn.clicked.connect(self.load_selected_layout)
        self.delete_layout_btn = QPushButton("Delete")
        self.delete_layout_btn.setProperty("variant", "danger")
        self.delete_layout_btn.clicked.connect(self.delete_selected_layout)
        layout_actions.addStretch(1)
        layout_actions.addWidget(self.load_layout_btn)
        layout_actions.addWidget(self.delete_layout_btn)
        layouts_layout.addLayout(layout_actions)

        windows_group = QGroupBox("Layout Windows")
        windows_layout = QVBoxLayout(windows_group)
        self.windows_table = QTableWidget(0, 4)
        self.windows_table.setHorizontalHeaderLabels(["App", "Window", "Display", "Position"])
        self.windows_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.windows_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.windows_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.windows_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.windows_table.verticalHeader().setVisible(False)
        self.windows_table.setAlternatingRowColors(True)
        self.windows_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        windows_layout.addWidget(self.windows_table)

        splitter.addWidget(layouts_group)
        splitter.addWidget(windows_group)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        outer.addWidget(splitter, 1)

        self.status_label = QLabel("")
        self.status_label.setProperty("role", "caption")
        self.status_label.setWordWrap(True)
        outer.addWidget(self.status_label)

        self._layouts = []
        self._scan_worker = None
        self._apply_worker = None
        self._queued_save_name = ""
        self._active_save_name = ""
        self._current_items = []
        self._current_displays = []
        self._removed_current_keys = set()
        self._visible_current_items = []
        self._current_signature = None
        self._resume_refresh_after_apply = False

        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(self.REFRESH_INTERVAL_MS)
        self._refresh_timer.timeout.connect(self.refresh_current_layout)

        self.load()
        QTimer.singleShot(0, self.refresh_current_layout)

    def showEvent(self, event):
        super().showEvent(event)
        self._refresh_timer.start()
        self.refresh_current_layout()

    def hideEvent(self, event):
        self._refresh_timer.stop()
        super().hideEvent(event)

    def load(self):
        self._layouts = window_layouts.load_layouts()
        self._render_layouts()
        self.status_label.setText(
            "No saved layouts yet." if not self._layouts else f"Loaded {len(self._layouts)} saved layout(s)."
        )

    def refresh_current_layout(self):
        if self._scan_worker and self._scan_worker.isRunning():
            return
        self._start_scan("refresh")

    def save_current_layout(self):
        was_refreshing = self._refresh_timer.isActive()
        self._refresh_timer.stop()
        name, ok = QInputDialog.getText(self, "Save Current Layout", "Layout name:")
        if was_refreshing:
            self._refresh_timer.start()
        name = name.strip()
        if not ok or not name:
            return
        if self._scan_worker and self._scan_worker.isRunning():
            self._queued_save_name = name
            self.status_label.setText("Waiting for the current scan to finish before saving.")
            return
        self._active_save_name = name
        self._start_scan("save")

    def remove_selected_current_app(self):
        selected = self.current_apps_table.selectionModel().selectedRows()
        if not selected:
            return
        row = selected[0].row()
        if row < 0 or row >= len(self._visible_current_items):
            return
        item = self._visible_current_items[row]
        self._removed_current_keys.add(self._current_item_key(item))
        self._refresh_current_preview()
        self.status_label.setText(
            f"Removed \"{window_layouts.saved_window_label(item)}\" from the current layout draft."
        )

    def restore_removed_apps(self):
        if not self._removed_current_keys:
            return
        self._removed_current_keys.clear()
        self._refresh_current_preview()
        self.status_label.setText("Restored all open apps to the current layout draft.")

    def load_selected_layout(self):
        layout = self._selected_layout()
        if not layout:
            return
        if self._scan_worker and self._scan_worker.isRunning():
            self.status_label.setText("Waiting for the current scan to finish before loading a layout.")
            return
        name = layout.get("name", "this layout")
        window_count = len(layout.get("windows", []))
        if window_count == 0:
            QMessageBox.information(
                self,
                "No Windows in Layout",
                f"\"{name}\" does not have any saved windows to load.",
            )
            return

        was_refreshing = self._refresh_timer.isActive()
        self._refresh_timer.stop()
        reply = QMessageBox.question(
            self,
            "Load Layout",
            f"Load \"{name}\"?\n\nThis will move matching windows and open missing apps when possible.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if was_refreshing:
            self._refresh_timer.start()
        if reply != QMessageBox.Yes:
            return

        self._start_apply_layout(dict(layout))

    def delete_selected_layout(self):
        index = self._selected_layout_index()
        layout = self._selected_layout()
        if index < 0 or not layout:
            return
        name = layout.get("name", "this layout")
        was_refreshing = self._refresh_timer.isActive()
        self._refresh_timer.stop()
        reply = QMessageBox.question(
            self,
            "Delete Layout",
            f"Delete \"{name}\"?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if was_refreshing:
            self._refresh_timer.start()
        if reply != QMessageBox.Yes:
            return
        del self._layouts[index]
        window_layouts.save_layouts(self._layouts)
        next_id = ""
        if self._layouts:
            next_index = min(index, len(self._layouts) - 1)
            next_id = self._layouts[next_index].get("id", "")
        self._render_layouts(select_id=next_id)
        self.status_label.setText(f"Deleted \"{name}\".")

    def _start_scan(self, purpose):
        if self._scan_worker and self._scan_worker.isRunning():
            return
        self._set_busy(purpose == "save")
        if purpose == "save":
            self.status_label.setText("Scanning current layout...")
        self._scan_worker = LayoutScanWorker(purpose)
        self._scan_worker.finished_with_items.connect(self._on_scan_finished)
        self._scan_worker.finished.connect(self._scan_worker.deleteLater)
        self._scan_worker.start()

    def _start_apply_layout(self, layout):
        if self._apply_worker and self._apply_worker.isRunning():
            return
        self._resume_refresh_after_apply = self._refresh_timer.isActive()
        self._refresh_timer.stop()
        self._set_busy(True)
        self.status_label.setText(f"Loading \"{layout.get('name', 'selected layout')}\"...")
        self._apply_worker = LayoutApplyWorker(layout)
        self._apply_worker.finished_with_result.connect(self._on_layout_applied)
        self._apply_worker.finished.connect(self._apply_worker.deleteLater)
        self._apply_worker.start()

    def _on_layout_applied(self, result, error):
        self._set_busy(False)
        self._apply_worker = None
        if self._resume_refresh_after_apply:
            self._refresh_timer.start()
        self._resume_refresh_after_apply = False
        if error:
            self.status_label.setText("Could not load the selected layout.")
            QMessageBox.warning(self, "Layout Load Failed", f"Could not load layout:\n\n{error}")
            return
        if result is None:
            self.status_label.setText("Could not load the selected layout.")
            return

        parts = [f"Moved {result.moved} window(s)"]
        if result.launched:
            parts.append(f"launched {len(result.launched)} app(s)")
        if result.missing:
            parts.append(f"{len(result.missing)} window(s) missing")
        if result.errors:
            parts.append(f"{len(result.errors)} error(s)")
        self.status_label.setText("Layout loaded: " + ", ".join(parts) + ".")
        if result.missing or result.errors:
            details = []
            if result.missing:
                details.append("Missing windows:\n" + "\n".join(result.missing[:8]))
            if result.errors:
                details.append("Errors:\n" + "\n".join(result.errors[:8]))
            QMessageBox.warning(self, "Layout Loaded with Issues", "\n\n".join(details))
        self.refresh_current_layout()

    def _on_scan_finished(self, items, displays, error, purpose):
        self._set_busy(False)
        self._scan_worker = None

        if error:
            self.status_label.setText("Could not scan the current layout.")
            if purpose == "save":
                QMessageBox.warning(self, "Layout Scan Failed", f"Could not scan open windows:\n\n{error}")
                self._active_save_name = ""
            self._start_queued_save_if_needed()
            return

        signature = self._scan_signature(items, displays)
        changed = signature != self._current_signature
        self._current_signature = signature
        self._current_items = items
        self._current_displays = displays
        self._removed_current_keys.intersection_update(
            self._current_item_key(item) for item in items
        )
        if purpose == "save" or changed:
            self._refresh_current_preview()

        if purpose == "save":
            self._save_scanned_layout(self._included_current_items(), displays)
        else:
            timestamp = datetime.now().strftime("%H:%M:%S")
            included_count = len(self._included_current_items())
            removed_count = len(items) - included_count
            removed_text = f", {removed_count} removed" if removed_count else ""
            self.status_label.setText(
                f"Live preview updated at {timestamp}: {len(displays)} display(s), {included_count} window(s){removed_text}."
            )

        self._start_queued_save_if_needed()

    def _start_queued_save_if_needed(self):
        if not self._queued_save_name:
            return
        self._active_save_name = self._queued_save_name
        self._queued_save_name = ""
        self._start_scan("save")

    def _save_scanned_layout(self, items, displays):
        name = self._active_save_name
        self._active_save_name = ""
        if not items:
            QMessageBox.information(
                self,
                "No Windows Found",
                "No app windows are selected for this layout. Use Show All or open the apps you want, then try again.",
            )
            self.status_label.setText("No app windows were selected to save.")
            return

        layout = window_layouts.build_layout(name, items, displays=displays)
        self._layouts.append(layout)
        window_layouts.save_layouts(self._layouts)
        self._render_layouts(select_id=layout.get("id"))
        self.status_label.setText(
            f"Saved \"{layout.get('name')}\" with {len(items)} window(s) on {len(displays)} display(s)."
        )

    def _selected_layout_index(self):
        selected = self.layouts_table.selectionModel().selectedRows()
        if not selected:
            return -1
        return selected[0].row()

    def _selected_layout(self):
        index = self._selected_layout_index()
        if index < 0 or index >= len(self._layouts):
            return None
        return self._layouts[index]

    def _render_layouts(self, select_id=""):
        current = self._selected_layout()
        current_id = select_id or (current.get("id") if current else "")
        self.layouts_table.setRowCount(len(self._layouts))
        selected_row = 0 if self._layouts else -1
        for row, layout in enumerate(self._layouts):
            if layout.get("id") == current_id:
                selected_row = row
            displays = layout.get("displays", []) or window_layouts.displays_from_windows(layout.get("windows", []))
            self.layouts_table.setItem(row, 0, QTableWidgetItem(layout.get("name", "Untitled Layout")))
            self.layouts_table.setItem(row, 1, QTableWidgetItem(str(len(layout.get("windows", [])))))
            self.layouts_table.setItem(row, 2, QTableWidgetItem(str(len(displays))))
            self.layouts_table.setItem(row, 3, QTableWidgetItem(layout.get("updated_at", "")))
        if selected_row >= 0:
            self.layouts_table.selectRow(selected_row)
        self._on_layout_selected()

    def _on_layout_selected(self):
        self._render_windows(self._selected_layout())
        has_layout = self._selected_layout() is not None
        self.load_layout_btn.setEnabled(has_layout)
        self.delete_layout_btn.setEnabled(has_layout)

    def _render_windows(self, layout):
        windows = layout.get("windows", []) if layout else []
        self.windows_table.setRowCount(len(windows))
        for row, item in enumerate(windows):
            app_name = item.get("process_name") or item.get("exe_path") or "Unknown app"
            title = item.get("title") or "Untitled window"
            rect = item.get("window_rect", {})
            position = (
                f"{rect.get('left', '?')}, {rect.get('top', '?')} - "
                f"{window_layouts.rect_width(rect)} x {window_layouts.rect_height(rect)}"
                if window_layouts.is_rect(rect) else ""
            )
            self.windows_table.setItem(row, 0, QTableWidgetItem(app_name))
            self.windows_table.setItem(row, 1, QTableWidgetItem(title))
            self.windows_table.setItem(row, 2, QTableWidgetItem(item.get("monitor_device", "")))
            self.windows_table.setItem(row, 3, QTableWidgetItem(position))
        self.windows_table.resizeRowsToContents()

    def _refresh_current_preview(self):
        included = self._included_current_items()
        self.preview.set_layout({"displays": self._current_displays, "windows": included})
        self._render_current_apps(included)

    def _included_current_items(self):
        return [
            item for item in self._current_items
            if self._current_item_key(item) not in self._removed_current_keys
        ]

    def _current_item_key(self, item):
        return window_layouts.layout_item_key(item)

    def _scan_signature(self, items, displays):
        display_key = tuple(
            (
                display.get("device", ""),
                self._rect_key(display.get("monitor_rect")),
                self._rect_key(display.get("work_rect")),
            )
            for display in displays
        )
        item_key = tuple(
            (
                self._current_item_key(item),
                item.get("process_name", ""),
                item.get("z_order"),
            )
            for item in items
        )
        return display_key, item_key

    def _rect_key(self, rect):
        if not window_layouts.is_rect(rect):
            return None
        return (
            int(rect["left"]),
            int(rect["top"]),
            int(rect["right"]),
            int(rect["bottom"]),
        )

    def _render_current_apps(self, items):
        selected_key, selected_identity = self._selected_current_app_keys()
        self._visible_current_items = list(items)
        self.current_apps_table.blockSignals(True)
        self.current_apps_table.setRowCount(len(items))
        selected_row = -1
        for row, item in enumerate(items):
            app_name = item.get("process_name") or item.get("exe_path") or "Unknown app"
            title = item.get("title") or "Untitled window"
            rect = item.get("window_rect", {})
            position = (
                f"{rect.get('left', '?')}, {rect.get('top', '?')} - "
                f"{window_layouts.rect_width(rect)} x {window_layouts.rect_height(rect)}"
                if window_layouts.is_rect(rect) else ""
            )
            self.current_apps_table.setItem(row, 0, QTableWidgetItem(app_name))
            self.current_apps_table.setItem(row, 1, QTableWidgetItem(title))
            self.current_apps_table.setItem(row, 2, QTableWidgetItem(item.get("monitor_device", "")))
            self.current_apps_table.setItem(row, 3, QTableWidgetItem(position))
            if self._current_item_key(item) == selected_key:
                selected_row = row
            elif selected_row < 0 and window_layouts.layout_item_identity_key(item) == selected_identity:
                selected_row = row
        if selected_row >= 0:
            self.current_apps_table.selectRow(selected_row)
        else:
            self.current_apps_table.clearSelection()
        self.current_apps_table.blockSignals(False)
        self.current_apps_table.resizeRowsToContents()
        self._update_current_app_actions()

    def _selected_current_app_keys(self):
        selected = self.current_apps_table.selectionModel().selectedRows()
        if not selected:
            return None, None
        row = selected[0].row()
        if row < 0 or row >= len(self._visible_current_items):
            return None, None
        item = self._visible_current_items[row]
        return self._current_item_key(item), window_layouts.layout_item_identity_key(item)

    def _update_current_app_actions(self):
        has_selection = bool(self.current_apps_table.selectionModel().selectedRows())
        self.remove_app_btn.setEnabled(has_selection)
        self.show_all_btn.setEnabled(bool(self._removed_current_keys))

    def _set_busy(self, busy):
        self.save_btn.setEnabled(not busy)
        self.load_layout_btn.setEnabled(not busy and self._selected_layout() is not None)
        self.delete_layout_btn.setEnabled(not busy and self._selected_layout() is not None)
        if busy:
            self.remove_app_btn.setEnabled(False)
        else:
            self._update_current_app_actions()
