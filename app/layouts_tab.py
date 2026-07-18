from datetime import datetime

from PySide6.QtCore import QTimer, QThread, Signal, Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
    QFrame, QMessageBox, QInputDialog, QSplitter, QScrollArea,
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
        if detail_font.pointSize() > 0:
            detail_font.setPointSize(max(detail_font.pointSize() - 1, 8))
        elif detail_font.pixelSize() > 0:
            detail_font.setPixelSize(max(detail_font.pixelSize() - 1, 10))
        else:
            detail_font.setPointSize(8)
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


def _clear_layout(layout):
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.deleteLater()
        elif item.layout() is not None:
            _clear_layout(item.layout())


def _build_context_row(primary_text, secondary_text="", meta_text="", trailing=None):
    row = QFrame()
    row.setProperty("role", "context-row")
    row_layout = QHBoxLayout(row)
    row_layout.setContentsMargins(4, 10, 4, 10)
    row_layout.setSpacing(10)

    text_col = QVBoxLayout()
    text_col.setSpacing(2)
    primary = QLabel(primary_text)
    primary.setProperty("role", "snapshot-key")
    primary.setWordWrap(True)
    text_col.addWidget(primary)
    if secondary_text:
        secondary = QLabel(secondary_text)
        secondary.setProperty("role", "caption")
        secondary.setWordWrap(True)
        text_col.addWidget(secondary)
    row_layout.addLayout(text_col, 1)

    if meta_text:
        meta = QLabel(meta_text)
        meta.setProperty("role", "caption")
        meta.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        row_layout.addWidget(meta)

    if trailing is not None:
        row_layout.addWidget(trailing)

    return row


def _empty_row(message):
    row = QFrame()
    row.setProperty("role", "context-row")
    row_layout = QHBoxLayout(row)
    row_layout.setContentsMargins(4, 14, 4, 14)
    label = QLabel(message)
    label.setProperty("role", "caption")
    label.setWordWrap(True)
    row_layout.addWidget(label)
    return row


def _rows_card():
    card = QFrame()
    card.setProperty("role", "context-rows")
    card_layout = QVBoxLayout(card)
    card_layout.setContentsMargins(10, 6, 10, 6)
    card_layout.setSpacing(0)
    rows_layout = QVBoxLayout()
    rows_layout.setSpacing(0)
    card_layout.addLayout(rows_layout)
    return card, rows_layout


def _layout_meta_text(layout):
    windows = layout.get("windows", [])
    displays = layout.get("displays", []) or window_layouts.displays_from_windows(windows)
    parts = [f"{len(windows)} window(s)", f"{len(displays)} display(s)"]
    updated = layout.get("updated_at", "")
    if updated:
        parts.append(f"Updated {updated}")
    return " · ".join(parts)


class LayoutCard(QFrame):
    def __init__(self, layout, on_select, on_load, on_delete):
        super().__init__()
        self._layout = layout
        self._on_select = on_select
        self._on_load = on_load
        self._on_delete = on_delete
        self.setProperty("role", "layout-card")
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumWidth(230)
        self.setMaximumWidth(300)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 14, 14, 14)
        outer.setSpacing(10)

        self.thumb = LayoutPreviewCanvas(layout)
        self.thumb.setFixedSize(240, 128)
        outer.addWidget(self.thumb)

        title = QLabel(layout.get("name", "Untitled Layout"))
        title.setProperty("role", "layout-card-title")
        title.setWordWrap(True)
        outer.addWidget(title)

        meta = QLabel(_layout_meta_text(layout))
        meta.setProperty("role", "caption")
        meta.setWordWrap(True)
        outer.addWidget(meta)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        self.load_btn = QPushButton("Load")
        self.load_btn.setProperty("variant", "action-confirm")
        self.load_btn.clicked.connect(self._handle_load)
        self.delete_btn = QPushButton("Delete")
        self.delete_btn.setProperty("variant", "card-danger")
        self.delete_btn.clicked.connect(self._handle_delete)
        actions.addWidget(self.load_btn)
        actions.addWidget(self.delete_btn)
        actions.addStretch(1)
        outer.addLayout(actions)

    def layout_id(self):
        return self._layout.get("id", "")

    def set_selected(self, selected):
        state = "selected" if selected else ""
        if self.property("state") == state:
            return
        self.setProperty("state", state)
        self.style().unpolish(self)
        self.style().polish(self)

    def set_busy(self, busy):
        self.load_btn.setEnabled(not busy)
        self.delete_btn.setEnabled(not busy)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._on_select(self._layout)
        super().mousePressEvent(event)

    def _handle_load(self):
        self._on_load(self._layout)

    def _handle_delete(self):
        self._on_delete(self._layout)


class LayoutsTab(QWidget):
    REFRESH_INTERVAL_MS = 5000
    GALLERY_COLUMNS = 2

    def __init__(self):
        super().__init__()
        outer = QVBoxLayout(self)

        header_layout = QHBoxLayout()
        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        title = QLabel("Layouts")
        title.setProperty("role", "heading")
        title_col.addWidget(title)
        subtitle = QLabel("Save and restore your window arrangements across displays.")
        subtitle.setProperty("role", "caption")
        title_col.addWidget(subtitle)
        header_layout.addLayout(title_col)
        header_layout.addStretch(1)
        self.save_btn = QPushButton("Save Current Layout")
        self.save_btn.clicked.connect(self.save_current_layout)
        header_layout.addWidget(self.save_btn, 0, Qt.AlignTop)
        outer.addLayout(header_layout)

        outer.addWidget(self._build_desktop_panel(), 2)
        outer.addWidget(self._build_saved_layouts_panel(), 3)

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
        self._selected_layout_id = ""
        self._layout_cards = []
        self._current_row_remove_buttons = []
        self._busy = False

        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(self.REFRESH_INTERVAL_MS)
        self._refresh_timer.timeout.connect(self.refresh_current_layout)

        self.load()
        QTimer.singleShot(0, self.refresh_current_layout)

    def _build_desktop_panel(self):
        panel = QFrame()
        panel.setProperty("role", "snapshot-panel")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(16, 14, 16, 16)
        panel_layout.setSpacing(10)

        eyebrow = QLabel("CURRENT DESKTOP")
        eyebrow.setProperty("role", "eyebrow")
        panel_layout.addWidget(eyebrow)

        splitter = QSplitter(Qt.Horizontal)

        preview_col = QWidget()
        preview_layout = QVBoxLayout(preview_col)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        preview_layout.setSpacing(6)
        preview_title = QLabel("Live Preview")
        preview_title.setProperty("role", "caption")
        preview_layout.addWidget(preview_title)
        self.preview = LayoutPreviewCanvas()
        preview_layout.addWidget(self.preview)

        apps_col = QWidget()
        apps_layout = QVBoxLayout(apps_col)
        apps_layout.setContentsMargins(0, 0, 0, 0)
        apps_layout.setSpacing(6)
        apps_header = QHBoxLayout()
        apps_title = QLabel("Current Apps")
        apps_title.setProperty("role", "caption")
        apps_header.addWidget(apps_title)
        apps_header.addStretch(1)
        self.show_all_btn = QPushButton("Show All")
        self.show_all_btn.setProperty("variant", "secondary")
        self.show_all_btn.clicked.connect(self.restore_removed_apps)
        apps_header.addWidget(self.show_all_btn)
        apps_layout.addLayout(apps_header)

        apps_scroll = QScrollArea()
        apps_scroll.setWidgetResizable(True)
        apps_scroll.setFrameShape(QFrame.NoFrame)
        apps_rows_card, self.current_apps_rows = _rows_card()
        apps_scroll.setWidget(apps_rows_card)
        apps_layout.addWidget(apps_scroll, 1)

        splitter.addWidget(preview_col)
        splitter.addWidget(apps_col)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        panel_layout.addWidget(splitter, 1)
        return panel

    def _build_saved_layouts_panel(self):
        panel = QFrame()
        panel.setProperty("role", "snapshot-panel")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(16, 14, 16, 16)
        panel_layout.setSpacing(10)

        eyebrow = QLabel("SAVED LAYOUTS")
        eyebrow.setProperty("role", "eyebrow")
        panel_layout.addWidget(eyebrow)

        splitter = QSplitter(Qt.Horizontal)

        gallery_col = QWidget()
        gallery_layout = QVBoxLayout(gallery_col)
        gallery_layout.setContentsMargins(0, 0, 0, 0)
        gallery_layout.setSpacing(8)
        self.gallery_scroll = QScrollArea()
        self.gallery_scroll.setWidgetResizable(True)
        self.gallery_scroll.setFrameShape(QFrame.NoFrame)
        gallery_inner = QWidget()
        self.gallery_grid = QGridLayout(gallery_inner)
        self.gallery_grid.setSpacing(14)
        self.gallery_grid.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.gallery_scroll.setWidget(gallery_inner)
        gallery_layout.addWidget(self.gallery_scroll)
        self.empty_layouts_label = QLabel("No saved layouts yet. Save your current desktop to create one.")
        self.empty_layouts_label.setProperty("role", "caption")
        self.empty_layouts_label.setAlignment(Qt.AlignCenter)
        self.empty_layouts_label.setWordWrap(True)
        gallery_layout.addWidget(self.empty_layouts_label)

        windows_col = QWidget()
        windows_layout = QVBoxLayout(windows_col)
        windows_layout.setContentsMargins(0, 0, 0, 0)
        windows_layout.setSpacing(6)
        windows_title = QLabel("Layout Windows")
        windows_title.setProperty("role", "caption")
        windows_layout.addWidget(windows_title)
        windows_scroll = QScrollArea()
        windows_scroll.setWidgetResizable(True)
        windows_scroll.setFrameShape(QFrame.NoFrame)
        windows_rows_card, self.layout_windows_rows = _rows_card()
        windows_scroll.setWidget(windows_rows_card)
        windows_layout.addWidget(windows_scroll, 1)

        splitter.addWidget(gallery_col)
        splitter.addWidget(windows_col)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 1)
        panel_layout.addWidget(splitter, 1)
        return panel

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

    def restore_removed_apps(self):
        if not self._removed_current_keys:
            return
        self._removed_current_keys.clear()
        self._refresh_current_preview()
        self.status_label.setText("Restored all open apps to the current layout draft.")

    def _remove_current_app(self, item):
        self._removed_current_keys.add(self._current_item_key(item))
        self._refresh_current_preview()
        self.status_label.setText(
            f"Removed \"{window_layouts.saved_window_label(item)}\" from the current layout draft."
        )

    def _select_layout(self, layout):
        layout_id = layout.get("id", "")
        if layout_id == self._selected_layout_id:
            return
        self._selected_layout_id = layout_id
        for card in self._layout_cards:
            card.set_selected(card.layout_id() == layout_id)
        self._render_layout_windows()

    def _load_layout(self, layout):
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

    def _delete_layout(self, layout):
        layout_id = layout.get("id", "")
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
        self._layouts = [item for item in self._layouts if item.get("id") != layout_id]
        window_layouts.save_layouts(self._layouts)
        if self._selected_layout_id == layout_id:
            self._selected_layout_id = ""
        self._render_layouts()
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

    def _find_layout(self, layout_id):
        return next((item for item in self._layouts if item.get("id") == layout_id), None)

    def _render_layouts(self, select_id=""):
        if select_id:
            self._selected_layout_id = select_id
        elif self._selected_layout_id and not self._find_layout(self._selected_layout_id):
            self._selected_layout_id = ""
        if not self._selected_layout_id and self._layouts:
            self._selected_layout_id = self._layouts[0].get("id", "")

        _clear_layout(self.gallery_grid)
        self._layout_cards = []
        for index, layout in enumerate(self._layouts):
            card = LayoutCard(layout, self._select_layout, self._load_layout, self._delete_layout)
            card.set_selected(layout.get("id", "") == self._selected_layout_id)
            card.set_busy(self._busy)
            self.gallery_grid.addWidget(card, index // self.GALLERY_COLUMNS, index % self.GALLERY_COLUMNS)
            self._layout_cards.append(card)
        self.gallery_scroll.setVisible(bool(self._layouts))
        self.empty_layouts_label.setVisible(not self._layouts)

        self._render_layout_windows()

    def _render_layout_windows(self):
        layout = self._find_layout(self._selected_layout_id)
        _clear_layout(self.layout_windows_rows)
        windows = layout.get("windows", []) if layout else []
        if not windows:
            message = "This layout has no saved windows." if layout else "Select a saved layout to see its windows."
            self.layout_windows_rows.addWidget(_empty_row(message))
            return
        for item in windows:
            app_name = item.get("process_name") or item.get("exe_path") or "Unknown app"
            title = item.get("title") or "Untitled window"
            rect = item.get("window_rect", {})
            position = (
                f"{rect.get('left', '?')}, {rect.get('top', '?')} - "
                f"{window_layouts.rect_width(rect)} x {window_layouts.rect_height(rect)}"
                if window_layouts.is_rect(rect) else ""
            )
            secondary = f"{title} — {position}" if position else title
            meta = item.get("monitor_device", "")
            self.layout_windows_rows.addWidget(_build_context_row(app_name, secondary, meta))

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
        self._visible_current_items = list(items)
        _clear_layout(self.current_apps_rows)
        self._current_row_remove_buttons = []
        if not items:
            self.current_apps_rows.addWidget(_empty_row("No open app windows detected."))
        else:
            for item in items:
                app_name = item.get("process_name") or item.get("exe_path") or "Unknown app"
                title = item.get("title") or "Untitled window"
                rect = item.get("window_rect", {})
                position = (
                    f"{rect.get('left', '?')}, {rect.get('top', '?')} - "
                    f"{window_layouts.rect_width(rect)} x {window_layouts.rect_height(rect)}"
                    if window_layouts.is_rect(rect) else ""
                )
                secondary = f"{title} — {position}" if position else title
                meta = item.get("monitor_device", "")
                remove_btn = QPushButton("✕")
                remove_btn.setProperty("variant", "row-remove")
                remove_btn.setFixedWidth(30)
                remove_btn.setEnabled(not self._busy)
                remove_btn.clicked.connect(lambda checked=False, item=item: self._remove_current_app(item))
                row = _build_context_row(app_name, secondary, meta, trailing=remove_btn)
                self.current_apps_rows.addWidget(row)
                self._current_row_remove_buttons.append(remove_btn)
        self.show_all_btn.setEnabled(bool(self._removed_current_keys))

    def _set_busy(self, busy):
        self._busy = busy
        self.save_btn.setEnabled(not busy)
        for card in self._layout_cards:
            card.set_busy(busy)
        for btn in self._current_row_remove_buttons:
            btn.setEnabled(not busy)
