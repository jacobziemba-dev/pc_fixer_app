import copy

from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtGui import QColor, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox, QInputDialog,
    QSplitter, QAbstractItemView, QDialog, QDialogButtonBox, QCheckBox,
    QScrollArea, QSpinBox,
)

from app import window_layouts


class WindowItemsWorker(QThread):
    finished_with_items = Signal(list, str)

    def run(self):
        try:
            items = window_layouts.collect_current_window_items()
            self.finished_with_items.emit(items, "")
        except Exception as exc:
            self.finished_with_items.emit([], str(exc))


class ApplyLayoutWorker(QThread):
    finished_with_result = Signal(object)

    def __init__(self, layout):
        super().__init__()
        self._layout = layout

    def run(self):
        try:
            result = window_layouts.apply_layout(self._layout, launch_missing=True)
        except Exception as exc:
            result = window_layouts.LayoutApplyResult(0, [], [], [str(exc)])
        self.finished_with_result.emit(result)


class WindowSelectionDialog(QDialog):
    def __init__(self, parent, title, message, windows, checked_keys=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(820, 520)
        self._windows = windows
        self._checkboxes = []
        checked_keys = set(checked_keys or [])

        outer = QVBoxLayout(self)
        label = QLabel(message)
        label.setProperty("role", "caption")
        label.setWordWrap(True)
        outer.addWidget(label)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Add", "App", "Window", "Display", "Position"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table_layout = QVBoxLayout(inner)
        table_layout.addWidget(self.table)
        scroll.setWidget(inner)
        outer.addWidget(scroll, 1)

        actions = QHBoxLayout()
        select_all_btn = QPushButton("Select All")
        select_all_btn.setProperty("variant", "secondary")
        select_all_btn.clicked.connect(lambda: self._set_all_checked(True))
        select_none_btn = QPushButton("Select None")
        select_none_btn.setProperty("variant", "secondary")
        select_none_btn.clicked.connect(lambda: self._set_all_checked(False))
        actions.addWidget(select_all_btn)
        actions.addWidget(select_none_btn)
        actions.addStretch(1)
        outer.addLayout(actions)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)

        self._render(checked_keys)

    def _render(self, checked_keys):
        self.table.setRowCount(len(self._windows))
        for row, item in enumerate(self._windows):
            checkbox = QCheckBox()
            checkbox.setChecked(not checked_keys or window_layouts.layout_item_key(item) in checked_keys)
            cell = QWidget()
            cell_layout = QHBoxLayout(cell)
            cell_layout.addWidget(checkbox)
            cell_layout.setAlignment(Qt.AlignCenter)
            cell_layout.setContentsMargins(0, 0, 0, 0)
            self.table.setCellWidget(row, 0, cell)
            self._checkboxes.append(checkbox)

            rect = item.get("window_rect", {})
            position = (
                f"{rect.get('left', '?')}, {rect.get('top', '?')} - "
                f"{window_layouts.rect_width(rect)} x {window_layouts.rect_height(rect)}"
                if rect else ""
            )
            self.table.setItem(row, 1, QTableWidgetItem(item.get("process_name") or item.get("exe_path") or "Unknown app"))
            self.table.setItem(row, 2, QTableWidgetItem(item.get("title") or "Untitled window"))
            self.table.setItem(row, 3, QTableWidgetItem(item.get("monitor_device", "")))
            self.table.setItem(row, 4, QTableWidgetItem(position))
        self.table.resizeRowsToContents()

    def _set_all_checked(self, checked):
        for checkbox in self._checkboxes:
            checkbox.setChecked(checked)

    def selected_windows(self):
        return [item for item, checkbox in zip(self._windows, self._checkboxes) if checkbox.isChecked()]


class LayoutPreviewCanvas(QWidget):
    WINDOW_COLORS = [
        QColor(109, 141, 255, 160),
        QColor(72, 190, 145, 155),
        QColor(245, 166, 35, 150),
        QColor(239, 83, 80, 145),
        QColor(166, 120, 255, 150),
    ]

    def __init__(self, layout):
        super().__init__()
        self._layout = layout
        self.setMinimumSize(780, 440)

    def set_layout(self, layout):
        self._layout = layout
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor("#1e1f26"))

        scene = window_layouts.build_preview_scene(self._layout, self.width(), self.height(), 32)
        if not scene["monitors"]:
            painter.setPen(QColor("#9294a3"))
            painter.drawText(self.rect(), Qt.AlignCenter, "No saved windows to preview.")
            return

        painter.setPen(QPen(QColor("#33343d"), 1))
        painter.setBrush(QColor("#24252d"))
        for monitor in scene["monitors"]:
            rect = monitor["preview_rect"]
            painter.drawRoundedRect(rect["x"], rect["y"], rect["width"], rect["height"], 8, 8)
            painter.setPen(QColor("#b7b8c2"))
            painter.drawText(rect["x"] + 10, rect["y"] + 22, monitor["device"])
            painter.setPen(QPen(QColor("#33343d"), 1))

        metrics = QFontMetrics(painter.font())
        for index, window in enumerate(scene["windows"]):
            rect = window["preview_rect"]
            color = self.WINDOW_COLORS[index % len(self.WINDOW_COLORS)]
            painter.setBrush(color)
            painter.setPen(QPen(QColor("#d8ddff"), 1))
            painter.drawRoundedRect(rect["x"], rect["y"], rect["width"], rect["height"], 5, 5)

            label = window["app"]
            if rect["width"] > 150 and rect["height"] > 42:
                label = window["label"]
            text_width = max(rect["width"] - 12, 10)
            text = metrics.elidedText(label, Qt.ElideRight, text_width)
            painter.setPen(QColor("#ffffff"))
            painter.drawText(
                rect["x"] + 6,
                rect["y"] + 6,
                text_width,
                max(rect["height"] - 12, 12),
                Qt.AlignLeft | Qt.AlignTop,
                text,
            )


class LayoutPreviewDialog(QDialog):
    def __init__(self, parent, layout):
        super().__init__(parent)
        self.setWindowTitle(f"Preview - {layout.get('name', 'Layout')}")
        self.resize(900, 560)

        outer = QVBoxLayout(self)
        title = QLabel(layout.get("name", "Untitled Layout"))
        title.setProperty("role", "heading")
        subtitle = QLabel("Saved monitor and window positions exactly as captured.")
        subtitle.setProperty("role", "caption")
        outer.addWidget(title)
        outer.addWidget(subtitle)
        outer.addWidget(LayoutPreviewCanvas(layout), 1)

        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)


class LayoutEditDialog(QDialog):
    def __init__(self, parent, layout, windows, checked_keys):
        super().__init__(parent)
        self.setWindowTitle(f"Edit - {layout.get('name', 'Layout')}")
        self.resize(1180, 680)
        self._layout = layout
        self._windows = [copy.deepcopy(item) for item in windows]
        self._checkboxes = []
        self._spin_rows = []
        self._syncing = False
        checked_keys = set(checked_keys or [])

        outer = QVBoxLayout(self)
        title = QLabel(layout.get("name", "Untitled Layout"))
        title.setProperty("role", "heading")
        subtitle = QLabel("Toggle windows and adjust saved position/size. The preview updates live; changes save only when you click Save Changes.")
        subtitle.setProperty("role", "caption")
        subtitle.setWordWrap(True)
        outer.addWidget(title)
        outer.addWidget(subtitle)

        splitter = QSplitter(Qt.Horizontal)
        editor_group = QGroupBox("Windows")
        editor_layout = QVBoxLayout(editor_group)
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(["Use", "App", "Window", "X", "Y", "W", "H"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        for col in (3, 4, 5, 6):
            self.table.horizontalHeader().setSectionResizeMode(col, QHeaderView.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        editor_layout.addWidget(self.table)

        preview_group = QGroupBox("Live Preview")
        preview_layout = QVBoxLayout(preview_group)
        self.preview = LayoutPreviewCanvas(self._draft_layout())
        preview_layout.addWidget(self.preview)

        splitter.addWidget(editor_group)
        splitter.addWidget(preview_group)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)
        outer.addWidget(splitter, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Save).setText("Save Changes")
        buttons.accepted.connect(self._accept_if_valid)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)

        self._render(checked_keys)
        self._refresh_preview()

    def _render(self, checked_keys):
        self.table.setRowCount(len(self._windows))
        for row, item in enumerate(self._windows):
            checkbox = QCheckBox()
            checkbox.setChecked(window_layouts.layout_item_key(item) in checked_keys)
            checkbox.stateChanged.connect(lambda _state: self._refresh_preview())
            cell = QWidget()
            cell_layout = QHBoxLayout(cell)
            cell_layout.addWidget(checkbox)
            cell_layout.setAlignment(Qt.AlignCenter)
            cell_layout.setContentsMargins(0, 0, 0, 0)
            self.table.setCellWidget(row, 0, cell)
            self._checkboxes.append(checkbox)

            self.table.setItem(row, 1, QTableWidgetItem(item.get("process_name") or item.get("exe_path") or "Unknown app"))
            self.table.setItem(row, 2, QTableWidgetItem(item.get("title") or "Untitled window"))

            rect = item.get("window_rect")
            if not window_layouts.is_rect(rect):
                rect = item.get("monitor_rect") or window_layouts.PREVIEW_FALLBACK_MONITOR
                item["window_rect"] = dict(rect)
            spin_row = []
            values = [
                int(rect.get("left", 0)),
                int(rect.get("top", 0)),
                window_layouts.rect_width(rect),
                window_layouts.rect_height(rect),
            ]
            for col, value in zip((3, 4, 5, 6), values):
                spin = QSpinBox()
                spin.setRange(-50000, 50000)
                if col in (5, 6):
                    spin.setMinimum(1)
                spin.setValue(value)
                spin.valueChanged.connect(lambda _value, r=row: self._on_geometry_changed(r))
                self.table.setCellWidget(row, col, spin)
                spin_row.append(spin)
            self._spin_rows.append(spin_row)
        self.table.resizeRowsToContents()

    def _on_geometry_changed(self, row):
        if self._syncing or row < 0 or row >= len(self._windows):
            return
        x_spin, y_spin, w_spin, h_spin = self._spin_rows[row]
        rect = {
            "left": x_spin.value(),
            "top": y_spin.value(),
            "right": x_spin.value() + w_spin.value(),
            "bottom": y_spin.value() + h_spin.value(),
        }
        self._windows[row] = window_layouts.update_layout_item_rect(self._windows[row], rect)
        self._refresh_preview()

    def _selected_windows(self):
        return [item for item, checkbox in zip(self._windows, self._checkboxes) if checkbox.isChecked()]

    def _draft_layout(self):
        draft = dict(self._layout)
        draft["windows"] = self._selected_windows()
        return draft

    def _refresh_preview(self):
        self.preview.set_layout(self._draft_layout())

    def _accept_if_valid(self):
        if not self._selected_windows():
            QMessageBox.information(self, "Nothing Selected", "A layout needs at least one window.")
            return
        self.accept()

    def edited_layout(self):
        return window_layouts.build_layout(
            self._layout.get("name", "Untitled Layout"),
            self._selected_windows(),
            layout_id=self._layout.get("id"),
            created_at=self._layout.get("created_at"),
        )


class LayoutsTab(QWidget):
    def __init__(self):
        super().__init__()
        outer = QVBoxLayout(self)

        header_layout = QHBoxLayout()
        title = QLabel("Window Layouts")
        title.setProperty("role", "heading")
        self.capture_btn = QPushButton("Create Layout")
        self.capture_btn.clicked.connect(self.capture_layout)
        header_layout.addWidget(title)
        header_layout.addStretch(1)
        header_layout.addWidget(self.capture_btn)
        outer.addLayout(header_layout)

        subtitle = QLabel(
            "Save your current app window setup, then reopen and arrange those apps later with one click."
        )
        subtitle.setProperty("role", "caption")
        subtitle.setWordWrap(True)
        outer.addWidget(subtitle)

        splitter = QSplitter(Qt.Horizontal)

        layouts_group = QGroupBox("Saved Layouts")
        layouts_layout = QVBoxLayout(layouts_group)
        self.layouts_table = QTableWidget(0, 3)
        self.layouts_table.setHorizontalHeaderLabels(["Name", "Windows", "Updated"])
        self.layouts_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.layouts_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.layouts_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.layouts_table.verticalHeader().setVisible(False)
        self.layouts_table.setAlternatingRowColors(True)
        self.layouts_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.layouts_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.layouts_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.layouts_table.itemSelectionChanged.connect(self._on_layout_selected)
        layouts_layout.addWidget(self.layouts_table)

        layout_actions = QHBoxLayout()
        self.apply_btn = QPushButton("Apply Layout")
        self.apply_btn.clicked.connect(self.confirm_and_apply)
        self.preview_btn = QPushButton("Preview")
        self.preview_btn.setProperty("variant", "secondary")
        self.preview_btn.clicked.connect(self.preview_layout)
        self.rename_btn = QPushButton("Rename")
        self.rename_btn.setProperty("variant", "secondary")
        self.rename_btn.clicked.connect(self.rename_layout)
        self.edit_btn = QPushButton("Edit")
        self.edit_btn.setProperty("variant", "secondary")
        self.edit_btn.clicked.connect(self.edit_layout)
        self.delete_btn = QPushButton("Delete")
        self.delete_btn.setProperty("variant", "danger")
        self.delete_btn.clicked.connect(self.delete_layout)
        layout_actions.addWidget(self.apply_btn)
        layout_actions.addWidget(self.preview_btn)
        layout_actions.addWidget(self.edit_btn)
        layout_actions.addWidget(self.rename_btn)
        layout_actions.addWidget(self.delete_btn)
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
        self._items_worker = None
        self._apply_worker = None
        self._pending_capture_name = ""
        self._pending_edit_index = -1
        self.load()

    def load(self):
        self._layouts = window_layouts.load_layouts()
        self._render_layouts()
        self.status_label.setText(
            "Create a layout from selected open app windows."
            if not self._layouts else f"Loaded {len(self._layouts)} saved layout(s)."
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

    def _render_layouts(self):
        current_id = self._selected_layout().get("id") if self._selected_layout() else ""
        self.layouts_table.setRowCount(len(self._layouts))
        selected_row = 0 if self._layouts else -1
        for row, layout in enumerate(self._layouts):
            if layout.get("id") == current_id:
                selected_row = row
            self.layouts_table.setItem(row, 0, QTableWidgetItem(layout.get("name", "Untitled Layout")))
            self.layouts_table.setItem(row, 1, QTableWidgetItem(str(len(layout.get("windows", [])))))
            self.layouts_table.setItem(row, 2, QTableWidgetItem(layout.get("updated_at", "")))
        if selected_row >= 0:
            self.layouts_table.selectRow(selected_row)
        self._on_layout_selected()

    def _on_layout_selected(self):
        layout = self._selected_layout()
        has_layout = layout is not None
        self.apply_btn.setEnabled(has_layout and bool(layout.get("windows") if layout else False))
        self.preview_btn.setEnabled(has_layout and bool(layout.get("windows") if layout else False))
        self.edit_btn.setEnabled(has_layout)
        self.rename_btn.setEnabled(has_layout)
        self.delete_btn.setEnabled(has_layout)
        self._render_windows(layout)

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
                if rect else ""
            )
            self.windows_table.setItem(row, 0, QTableWidgetItem(app_name))
            self.windows_table.setItem(row, 1, QTableWidgetItem(title))
            self.windows_table.setItem(row, 2, QTableWidgetItem(item.get("monitor_device", "")))
            self.windows_table.setItem(row, 3, QTableWidgetItem(position))
        self.windows_table.resizeRowsToContents()

    def _save_and_render(self, message):
        window_layouts.save_layouts(self._layouts)
        self._render_layouts()
        self.status_label.setText(message)

    def capture_layout(self):
        name, ok = QInputDialog.getText(self, "Create Layout", "Layout name:")
        name = name.strip()
        if not ok or not name:
            return
        self._pending_capture_name = name
        self._pending_edit_index = -1
        self._load_current_windows("Finding open app windows...")

    def _load_current_windows(self, message):
        self._set_busy(True, message)
        self._items_worker = WindowItemsWorker()
        self._items_worker.finished_with_items.connect(self._on_window_items_loaded)
        self._items_worker.start()

    def _on_window_items_loaded(self, items, error):
        self._set_busy(False)
        if error:
            QMessageBox.warning(self, "Window Scan Failed", f"Could not scan open windows:\n\n{error}")
            self.status_label.setText("Window scan failed.")
            self._pending_capture_name = ""
            self._pending_edit_index = -1
            return
        if self._pending_edit_index >= 0:
            self._show_edit_dialog(items)
        else:
            self._show_capture_dialog(items)

    def _show_capture_dialog(self, items):
        if not items:
            QMessageBox.information(
                self,
                "No Windows Found",
                "No normal app windows were found. Open and arrange the apps you want, then try again.",
            )
            self.status_label.setText("No app windows were found.")
            self._pending_capture_name = ""
            return
        dialog = WindowSelectionDialog(
            self,
            "Choose Windows",
            "Select the open app windows to include in this layout.",
            items,
        )
        if dialog.exec() != QDialog.Accepted:
            self.status_label.setText("Layout capture was canceled.")
            self._pending_capture_name = ""
            return
        selected = dialog.selected_windows()
        if not selected:
            QMessageBox.information(self, "Nothing Selected", "Choose at least one window to save a layout.")
            self.status_label.setText("No windows were selected.")
            self._pending_capture_name = ""
            return
        layout = window_layouts.build_layout(self._pending_capture_name, selected)
        self._pending_capture_name = ""
        self._layouts.append(layout)
        self._save_and_render(f"Saved \"{layout.get('name')}\" with {len(selected)} window(s).")

    def _show_edit_dialog(self, current_items):
        index = self._pending_edit_index
        self._pending_edit_index = -1
        if index < 0 or index >= len(self._layouts):
            return
        layout = self._layouts[index]
        saved_items = layout.get("windows", [])
        all_items = window_layouts.merge_layout_items(saved_items, current_items)
        checked_keys = {window_layouts.layout_item_key(item) for item in saved_items}
        if not all_items:
            QMessageBox.information(self, "No Windows Available", "No saved or open windows are available to edit.")
            return
        dialog = LayoutEditDialog(
            self,
            layout,
            all_items,
            checked_keys,
        )
        if dialog.exec() != QDialog.Accepted:
            self.status_label.setText("Layout edit was canceled.")
            return
        updated = dialog.edited_layout()
        self._layouts[index] = updated
        self._save_and_render(f"Updated \"{updated.get('name')}\" with {len(updated.get('windows', []))} window(s).")

    def confirm_and_apply(self):
        layout = self._selected_layout()
        if not layout:
            return
        missing = window_layouts.missing_launches_for_layout(layout)
        message = f"Apply \"{layout.get('name')}\" and arrange {len(layout.get('windows', []))} window(s)?"
        if missing:
            app_lines = "\n".join(
                f"- {window_layouts.saved_window_label(item)} ({item.get('exe_path', 'Unknown app')})"
                for item in missing
            )
            message += f"\n\nThe following missing window(s) will be opened first:\n{app_lines}"
        reply = QMessageBox.question(
            self,
            "Apply Layout",
            message,
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        self._set_busy(True, f"Applying \"{layout.get('name')}\"...")
        self._apply_worker = ApplyLayoutWorker(layout)
        self._apply_worker.finished_with_result.connect(self._on_applied)
        self._apply_worker.start()

    def _on_applied(self, result):
        self._set_busy(False)
        message = f"Moved {result.moved} window(s)."
        if result.launched:
            message += f" Opened {len(result.launched)} app(s)."
        if result.missing:
            message += f" Could not find {len(result.missing)} window(s)."
        if result.errors:
            message += f" {len(result.errors)} error(s)."
        self.status_label.setText(message)
        if result.missing or result.errors:
            details = ""
            if result.missing:
                details += "Missing windows:\n" + "\n".join(f"- {item}" for item in result.missing)
            if result.errors:
                if details:
                    details += "\n\n"
                details += "Errors:\n" + "\n".join(f"- {item}" for item in result.errors)
            QMessageBox.warning(self, "Layout Applied With Issues", f"{message}\n\n{details}")
        else:
            QMessageBox.information(self, "Layout Applied", message)

    def rename_layout(self):
        layout = self._selected_layout()
        if not layout:
            return
        name, ok = QInputDialog.getText(
            self,
            "Rename Layout",
            "New layout name:",
            text=layout.get("name", ""),
        )
        name = name.strip()
        if not ok or not name:
            return
        layout["name"] = name
        layout["updated_at"] = window_layouts._now_iso()
        self._save_and_render(f"Renamed layout to \"{name}\".")

    def preview_layout(self):
        layout = self._selected_layout()
        if not layout or not layout.get("windows"):
            return
        dialog = LayoutPreviewDialog(self, layout)
        dialog.exec()

    def edit_layout(self):
        index = self._selected_layout_index()
        if index < 0:
            return
        self._pending_edit_index = index
        self._pending_capture_name = ""
        self._load_current_windows("Finding open app windows for editing...")

    def delete_layout(self):
        index = self._selected_layout_index()
        layout = self._selected_layout()
        if index < 0 or not layout:
            return
        reply = QMessageBox.question(
            self,
            "Delete Layout",
            f"Delete \"{layout.get('name', 'this layout')}\"?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        name = layout.get("name", "Layout")
        del self._layouts[index]
        self._save_and_render(f"Deleted \"{name}\".")

    def _set_busy(self, busy, message=""):
        layout = self._selected_layout()
        can_apply = layout is not None and bool(layout.get("windows"))
        self.capture_btn.setEnabled(not busy)
        self.apply_btn.setEnabled(not busy and can_apply)
        self.preview_btn.setEnabled(not busy and can_apply)
        self.edit_btn.setEnabled(not busy and layout is not None)
        self.rename_btn.setEnabled(not busy and layout is not None)
        self.delete_btn.setEnabled(not busy and layout is not None)
        if message:
            self.status_label.setText(message)
