from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox, QInputDialog,
    QSplitter, QAbstractItemView,
)

from app import window_layouts


class CaptureLayoutWorker(QThread):
    finished_with_layout = Signal(object, str)

    def __init__(self, name):
        super().__init__()
        self._name = name

    def run(self):
        try:
            layout = window_layouts.capture_current_layout(self._name)
            self.finished_with_layout.emit(layout, "")
        except Exception as exc:
            self.finished_with_layout.emit(None, str(exc))


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


class LayoutsTab(QWidget):
    def __init__(self):
        super().__init__()
        outer = QVBoxLayout(self)

        header_layout = QHBoxLayout()
        title = QLabel("Window Layouts")
        title.setProperty("role", "heading")
        self.capture_btn = QPushButton("Capture Current Layout")
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
        self.rename_btn = QPushButton("Rename")
        self.rename_btn.setProperty("variant", "secondary")
        self.rename_btn.clicked.connect(self.rename_layout)
        self.delete_btn = QPushButton("Delete")
        self.delete_btn.setProperty("variant", "danger")
        self.delete_btn.clicked.connect(self.delete_layout)
        layout_actions.addWidget(self.apply_btn)
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
        self._capture_worker = None
        self._apply_worker = None
        self.load()

    def load(self):
        self._layouts = window_layouts.load_layouts()
        self._render_layouts()
        self.status_label.setText(
            "Capture your current desktop arrangement to create a layout."
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
        name, ok = QInputDialog.getText(self, "Capture Layout", "Layout name:")
        name = name.strip()
        if not ok or not name:
            return
        self._set_busy(True, "Capturing visible app windows...")
        self._capture_worker = CaptureLayoutWorker(name)
        self._capture_worker.finished_with_layout.connect(self._on_captured)
        self._capture_worker.start()

    def _on_captured(self, layout, error):
        self._set_busy(False)
        if error:
            QMessageBox.warning(self, "Capture Failed", f"Could not capture this layout:\n\n{error}")
            self.status_label.setText("Capture failed.")
            return
        count = len(layout.get("windows", [])) if layout else 0
        if count == 0:
            QMessageBox.information(
                self,
                "No Windows Captured",
                "No normal app windows were found. Open and arrange the apps you want, then try again.",
            )
            self.status_label.setText("No app windows were captured.")
            return
        reply = QMessageBox.question(
            self,
            "Save Layout",
            f"Save \"{layout.get('name')}\" with {count} captured window(s)?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )
        if reply != QMessageBox.Yes:
            self.status_label.setText("Captured layout was not saved.")
            return
        self._layouts.append(layout)
        self._save_and_render(f"Saved \"{layout.get('name')}\" with {count} window(s).")

    def confirm_and_apply(self):
        layout = self._selected_layout()
        if not layout:
            return
        missing = window_layouts.missing_apps_for_layout(layout)
        message = f"Apply \"{layout.get('name')}\" and arrange {len(layout.get('windows', []))} window(s)?"
        if missing:
            app_lines = "\n".join(f"- {path}" for path in missing)
            message += f"\n\nThe following app(s) will be opened first:\n{app_lines}"
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
        self.rename_btn.setEnabled(not busy and layout is not None)
        self.delete_btn.setEnabled(not busy and layout is not None)
        if message:
            self.status_label.setText(message)
