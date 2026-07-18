from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QCheckBox, QMessageBox,
    QAbstractItemView, QTextEdit,
)

from app import system_info as sysinfo
from app import toolbox
from app.job_queue import get_job_queue
from app.toolbox_widgets import ToolRunner, result_text, set_status_label


class ScanWorker(QThread):
    finished_with_data = Signal(list)

    def run(self):
        categories = sysinfo.scan_cleanup_targets()
        self.finished_with_data.emit(categories)


class DeleteWorker(QThread):
    finished_with_result = Signal(int, list)

    def __init__(self, categories):
        super().__init__()
        self._categories = categories

    def run(self):
        bytes_freed, errors = sysinfo.delete_cleanup_items(self._categories)
        self.finished_with_result.emit(bytes_freed, errors)


class CleanupTab(QWidget):
    def __init__(self):
        super().__init__()
        outer = QVBoxLayout(self)

        header_layout = QHBoxLayout()
        title = QLabel("Safe Disk Cleanup")
        title.setProperty("role", "heading")
        header_layout.addWidget(title)
        header_layout.addStretch(1)
        self.scan_btn = QPushButton("Scan for Junk Files")
        self.scan_btn.clicked.connect(self.start_scan)
        header_layout.addWidget(self.scan_btn)
        outer.addLayout(header_layout)

        subtitle = QLabel(
            "Only well-known temp, cache, and Recycle Bin locations are scanned. "
            "Nothing is deleted until you select items below and confirm."
        )
        subtitle.setProperty("role", "caption")
        subtitle.setWordWrap(True)
        outer.addWidget(subtitle)

        self.status_label = QLabel("Click \"Scan for Junk Files\" to begin.")
        self.status_label.setProperty("role", "caption")
        outer.addWidget(self.status_label)

        group = QGroupBox("Found Items")
        group_layout = QVBoxLayout(group)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Clean", "Item", "Size"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        group_layout.addWidget(self.table)

        selection_layout = QHBoxLayout()
        self.select_all_btn = QPushButton("Select All")
        self.select_all_btn.setProperty("variant", "secondary")
        self.select_all_btn.clicked.connect(lambda: self._set_all_checked(True))
        self.select_none_btn = QPushButton("Select None")
        self.select_none_btn.setProperty("variant", "secondary")
        self.select_none_btn.clicked.connect(lambda: self._set_all_checked(False))
        self.total_label = QLabel("Selected: 0 B")
        self.total_label.setProperty("role", "caption")
        selection_layout.addWidget(self.select_all_btn)
        selection_layout.addWidget(self.select_none_btn)
        selection_layout.addStretch(1)
        selection_layout.addWidget(self.total_label)
        group_layout.addLayout(selection_layout)

        outer.addWidget(group, 1)

        storage = QGroupBox("Storage Diagnostics (read-only)")
        storage_layout = QVBoxLayout(storage)
        storage_caption = QLabel(
            "Find large files, folder size hotspots, and duplicate copies. "
            "These scans never delete files."
        )
        storage_caption.setProperty("role", "caption")
        storage_caption.setWordWrap(True)
        storage_layout.addWidget(storage_caption)
        buttons = QHBoxLayout()
        self.large_files_btn = QPushButton("Scan Large Files")
        self.large_files_btn.clicked.connect(
            lambda: self._run_storage_tool(toolbox.scan_large_files)
        )
        self.folder_sizes_btn = QPushButton("Folder Sizes")
        self.folder_sizes_btn.setProperty("variant", "secondary")
        self.folder_sizes_btn.clicked.connect(
            lambda: self._run_storage_tool(toolbox.scan_folder_sizes)
        )
        self.duplicates_btn = QPushButton("Find Duplicates")
        self.duplicates_btn.setProperty("variant", "secondary")
        self.duplicates_btn.clicked.connect(
            lambda: self._run_storage_tool(toolbox.scan_duplicate_files)
        )
        buttons.addWidget(self.large_files_btn)
        buttons.addWidget(self.folder_sizes_btn)
        buttons.addWidget(self.duplicates_btn)
        buttons.addStretch(1)
        storage_layout.addLayout(buttons)
        self.storage_status = QLabel("Choose a storage scan to begin.")
        self.storage_status.setProperty("role", "caption")
        self.storage_status.setWordWrap(True)
        storage_layout.addWidget(self.storage_status)
        self.storage_output = QTextEdit()
        self.storage_output.setReadOnly(True)
        self.storage_output.setMinimumHeight(120)
        storage_layout.addWidget(self.storage_output)
        outer.addWidget(storage)

        footer_layout = QHBoxLayout()
        footer_layout.addStretch(1)
        self.clean_btn = QPushButton("Clean Selected Items")
        self.clean_btn.setProperty("variant", "danger")
        self.clean_btn.setEnabled(False)
        self.clean_btn.clicked.connect(self.confirm_and_clean)
        footer_layout.addWidget(self.clean_btn)
        outer.addLayout(footer_layout)

        self._categories = []
        self._checkboxes = []
        self._rescan_after_clean = False
        self._storage_runner = ToolRunner(
            "cleanup",
            self._set_storage_busy,
            self.storage_status,
            busy_text="Running storage scan...",
        )

    def _set_storage_busy(self, busy):
        for button in (self.large_files_btn, self.folder_sizes_btn, self.duplicates_btn):
            button.setEnabled(not busy)
        if busy:
            self.scan_btn.setEnabled(False)
            self.clean_btn.setEnabled(False)
        else:
            self.scan_btn.setEnabled(True)
            self._update_total()

    def _run_storage_tool(self, fn, *args):
        self._storage_runner.start(fn, args, self._on_storage_result)

    def _on_storage_result(self, result):
        set_status_label(self.storage_status, result.summary, result.success)
        self.storage_output.setPlainText(result_text(result))

    def start_scan(self):
        worker = ScanWorker()
        get_job_queue().submit(
            scope="cleanup",
            title="Scanning cleanup targets...",
            worker=worker,
            result_signal="finished_with_data",
            on_started=self._on_scan_started,
            on_result=self._on_scanned,
            on_finished=self._on_cleanup_worker_finished,
            on_rejected=lambda message: self.status_label.setText(message),
        )

    def _on_scan_started(self):
        self.scan_btn.setEnabled(False)
        self.clean_btn.setEnabled(False)
        self.select_all_btn.setEnabled(False)
        self.select_none_btn.setEnabled(False)
        self.large_files_btn.setEnabled(False)
        self.folder_sizes_btn.setEnabled(False)
        self.duplicates_btn.setEnabled(False)
        self.status_label.setText("Scanning temp folders, browser caches, and Recycle Bin...")
        self.table.setRowCount(0)

    def _on_cleanup_worker_finished(self):
        self.scan_btn.setEnabled(True)
        self.select_all_btn.setEnabled(True)
        self.select_none_btn.setEnabled(True)
        self.large_files_btn.setEnabled(True)
        self.folder_sizes_btn.setEnabled(True)
        self.duplicates_btn.setEnabled(True)
        self._update_total()
        if self._rescan_after_clean:
            self._rescan_after_clean = False
            self.start_scan()

    def _on_scanned(self, categories):
        self._categories = categories
        self._checkboxes = []

        if not categories:
            self.status_label.setText("Nothing worth cleaning was found. Your PC is already tidy.")
            self.table.setRowCount(0)
            self.clean_btn.setEnabled(False)
            return

        total = sum(c.size_bytes for c in categories)
        self.status_label.setText(f"Found {sysinfo.format_bytes(total)} across {len(categories)} categories.")

        self.table.setRowCount(len(categories))
        for row, cat in enumerate(categories):
            checkbox = QCheckBox()
            checkbox.setChecked(True)
            checkbox.stateChanged.connect(self._update_total)
            cell = QWidget()
            cell_layout = QHBoxLayout(cell)
            cell_layout.addWidget(checkbox)
            cell_layout.setAlignment(Qt.AlignCenter)
            cell_layout.setContentsMargins(0, 0, 0, 0)
            self.table.setCellWidget(row, 0, cell)
            self._checkboxes.append(checkbox)

            name_item = QTableWidgetItem(f"{cat.label}\n{cat.description}")
            name_item.setToolTip(cat.description)
            self.table.setItem(row, 1, name_item)
            self.table.setItem(row, 2, QTableWidgetItem(sysinfo.format_bytes(cat.size_bytes)))

        self.table.resizeRowsToContents()
        self._update_total()

    def _set_all_checked(self, checked):
        for cb in self._checkboxes:
            cb.setChecked(checked)

    def _selected_categories(self):
        return [cat for cat, cb in zip(self._categories, self._checkboxes) if cb.isChecked()]

    def _update_total(self):
        selected = self._selected_categories()
        total = sum(c.size_bytes for c in selected)
        self.total_label.setText(f"Selected: {sysinfo.format_bytes(total)}")
        self.clean_btn.setEnabled(len(selected) > 0)

    def confirm_and_clean(self):
        selected = self._selected_categories()
        if not selected:
            return
        total = sum(c.size_bytes for c in selected)
        names = "\n".join(f"- {c.label} ({sysinfo.format_bytes(c.size_bytes)})" for c in selected)
        reply = QMessageBox.question(
            self,
            "Confirm Cleanup",
            f"This will permanently delete the following ({sysinfo.format_bytes(total)} total):\n\n{names}\n\n"
            "Continue?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        self.clean_btn.setEnabled(False)
        worker = DeleteWorker(selected)
        get_job_queue().submit(
            scope="cleanup",
            title="Cleaning selected items...",
            worker=worker,
            result_signal="finished_with_result",
            on_started=self._on_delete_started,
            on_result=self._on_cleaned,
            on_finished=self._on_cleanup_worker_finished,
            on_rejected=lambda message: self.status_label.setText(message),
        )

    def _on_delete_started(self):
        self.clean_btn.setEnabled(False)
        self.scan_btn.setEnabled(False)
        self.select_all_btn.setEnabled(False)
        self.select_none_btn.setEnabled(False)
        self.large_files_btn.setEnabled(False)
        self.folder_sizes_btn.setEnabled(False)
        self.duplicates_btn.setEnabled(False)
        self.status_label.setText("Cleaning selected items...")

    def _on_cleaned(self, bytes_freed, errors):
        self.scan_btn.setEnabled(True)
        message = f"Freed {sysinfo.format_bytes(bytes_freed)}."
        if errors:
            message += f" {len(errors)} item(s) were skipped (in use or access denied)."
        self.status_label.setText(message)
        QMessageBox.information(self, "Cleanup Complete", message)
        self._rescan_after_clean = True
