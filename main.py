import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QVBoxLayout, QHBoxLayout,
    QFrame, QPushButton, QStackedWidget, QToolButton, QMenu,
)

from app.theme import DARK_STYLESHEET
from app.dashboard_tab import DashboardTab
from app.job_queue import get_job_queue


# Heavy tabs are created on first visit to keep startup responsive.
_LAZY_TABS = {
    1: ("app.assistant_tab", "AssistantTab", "AI Chat"),
    2: ("app.health_tab", "HealthTab", "Health"),
    3: ("app.cleanup_tab", "CleanupTab", "Cleanup"),
    4: ("app.dashboard_tab", "DashboardTab", "Performance"),
    5: ("app.network_tab", "NetworkTab", "Network"),
    6: ("app.display_tab", "DisplayTab", "Display"),
    7: ("app.audio_tab", "AudioTab", "Audio"),
    8: ("app.layouts_tab", "LayoutsTab", "Layouts"),
    9: ("app.startup_tab", "StartupTab", "Startup & Programs"),
    10: ("app.hardware_tab", "HardwareTab", "PC Setup"),
    11: ("app.reports_tab", "ReportsTab", "Reports"),
}

_TOOL_SEARCH = {
    "assistant": 1,
    "ai": 1,
    "chat": 1,
    "health": 2,
    "update": 2,
    "disk": 2,
    "event": 2,
    "security": 2,
    "power": 2,
    "restore": 2,
    "clean": 3,
    "junk": 3,
    "cache": 3,
    "performance": 4,
    "cpu": 4,
    "ram": 4,
    "process": 4,
    "network": 5,
    "dns": 5,
    "wifi": 5,
    "adapter": 5,
    "display": 6,
    "monitor": 6,
    "refresh rate": 6,
    "audio": 7,
    "sound": 7,
    "volume": 7,
    "layout": 8,
    "window": 8,
    "startup": 9,
    "program": 9,
    "hardware": 10,
    "spec": 10,
    "report": 11,
    "history": 11,
}


def _placeholder(label_text):
    widget = QWidget()
    layout = QVBoxLayout(widget)
    label = QLabel(label_text)
    label.setProperty("role", "caption")
    layout.addWidget(label)
    layout.addStretch(1)
    return widget


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PC Fix - Performance & Cleanup")
        self.resize(1360, 820)

        self._nav_buttons = []
        self._top_nav_buttons = []
        self._tab_titles = [
            "Dashboard",
            "AI Chat",
            "Health",
            "Cleanup",
            "Performance",
            "Network",
            "Display",
            "Audio",
            "Layouts",
            "Startup & Programs",
            "PC Setup",
            "Reports",
        ]

        self.stack = QStackedWidget()
        self.stack.addWidget(DashboardTab())
        self.stack.addWidget(_placeholder("Loading AI Chat..."))
        self.stack.addWidget(_placeholder("Loading Health..."))
        self.stack.addWidget(_placeholder("Loading Cleanup..."))
        self.stack.addWidget(_placeholder("Loading Performance..."))
        self.stack.addWidget(_placeholder("Loading Network..."))
        self.stack.addWidget(_placeholder("Loading Display..."))
        self.stack.addWidget(_placeholder("Loading Audio..."))
        self.stack.addWidget(_placeholder("Loading Layouts..."))
        self.stack.addWidget(_placeholder("Loading Startup & Programs..."))
        self.stack.addWidget(_placeholder("Loading PC Setup..."))
        self.stack.addWidget(_placeholder("Loading Reports..."))

        self._loaded_tabs = {0}  # Dashboard is eager
        self.stack.currentChanged.connect(self._ensure_tab_loaded)

        shell = QFrame()
        shell.setProperty("role", "app-shell")
        shell_layout = QVBoxLayout(shell)
        shell_layout.setContentsMargins(0, 0, 0, 0)
        shell_layout.setSpacing(0)
        shell_layout.addWidget(self._build_top_bar())

        content_layout = QHBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        content_layout.addWidget(self._build_sidebar())
        content_layout.addWidget(self.stack, 1)
        shell_layout.addLayout(content_layout, 1)
        self.setCentralWidget(shell)

        self.statusBar().showMessage("Ready")
        get_job_queue().status_changed.connect(self._set_global_status)

        self._go_to_tab(1)

    def _build_top_bar(self):
        top = QFrame()
        top.setProperty("role", "top-bar")
        layout = QHBoxLayout(top)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(14)

        logo = QLabel("PC")
        logo.setProperty("role", "app-logo")
        logo.setAlignment(Qt.AlignCenter)
        layout.addWidget(logo)

        title = QLabel("PC Fix")
        title.setProperty("role", "app-title")
        layout.addWidget(title)
        layout.addSpacing(70)

        nav = QFrame()
        nav.setProperty("role", "top-nav")
        nav_layout = QHBoxLayout(nav)
        nav_layout.setContentsMargins(6, 5, 6, 5)
        nav_layout.setSpacing(6)
        for index, label in ((0, "Dashboard"), (1, "AI Chat"), (3, "Cleanup")):
            button = QPushButton(label)
            button.setCheckable(True)
            button.setProperty("variant", "top-nav")
            button.clicked.connect(lambda checked=False, index=index: self._go_to_tab(index))
            nav_layout.addWidget(button)
            self._top_nav_buttons.append((index, button))
        layout.addWidget(nav)

        layout.addStretch(1)
        self.global_status_chip = QLabel("Ready")
        self.global_status_chip.setProperty("role", "status-chip")
        layout.addWidget(self.global_status_chip)

        self.global_context_btn = QToolButton()
        self.global_context_btn.setText("PC Context")
        self.global_context_btn.setCheckable(True)
        self.global_context_btn.setChecked(True)
        self.global_context_btn.setProperty("role", "header-menu-btn")
        self.global_context_btn.toggled.connect(self._toggle_assistant_context)
        layout.addWidget(self.global_context_btn)

        self.global_menu_btn = QToolButton()
        self.global_menu_btn.setText("Menu")
        self.global_menu_btn.setProperty("role", "header-menu-btn")
        self.global_menu_btn.setPopupMode(QToolButton.InstantPopup)
        menu = QMenu(self.global_menu_btn)
        menu.addAction("Clear AI Chat", self._clear_assistant_chat)
        menu.addAction("Recheck AI Model", self._recheck_assistant_model)
        menu.addAction("Open Reports", lambda: self._go_to_tab(11))
        self.global_menu_btn.setMenu(menu)
        layout.addWidget(self.global_menu_btn)
        return top

    def _build_sidebar(self):
        sidebar = QFrame()
        sidebar.setProperty("role", "side-bar")
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(10, 16, 10, 14)
        layout.setSpacing(10)

        for index, label in (
            (1, "AI Chat"),
            (0, "Dashboard"),
            (3, "Cleanup"),
            (9, "Startup"),
            (8, "Layouts"),
            (2, "Tools"),
            (11, "Settings"),
        ):
            button = QPushButton(label)
            button.setCheckable(True)
            button.setProperty("variant", "side-nav")
            button.clicked.connect(lambda checked=False, index=index: self._go_to_tab(index))
            layout.addWidget(button)
            self._nav_buttons.append((index, button))

        layout.addStretch(1)
        protected = QFrame()
        protected.setProperty("role", "protected-card")
        protected_layout = QVBoxLayout(protected)
        protected_layout.setContentsMargins(14, 14, 14, 14)
        protected_layout.setSpacing(6)
        protected_title = QLabel("Protected")
        protected_title.setProperty("role", "protected-title")
        protected_layout.addWidget(protected_title)
        protected_caption = QLabel("Windows 11 Pro\nBuild 22631")
        protected_caption.setProperty("role", "caption")
        protected_layout.addWidget(protected_caption)
        layout.addWidget(protected)
        return sidebar

    def _ensure_tab_loaded(self, index):
        if index in self._loaded_tabs or index not in _LAZY_TABS:
            return
        self._load_tab(index, make_current=True)

    def _load_tab(self, index, make_current=False):
        if index in self._loaded_tabs or index not in _LAZY_TABS:
            return self.stack.widget(index)
        module_name, class_name, title = _LAZY_TABS[index]
        module = __import__(module_name, fromlist=[class_name])
        tab_cls = getattr(module, class_name)
        real_tab = tab_cls()
        if hasattr(real_tab, "action_requested"):
            real_tab.action_requested.connect(self._on_assistant_action_requested)
        if hasattr(real_tab, "status_changed"):
            real_tab.status_changed.connect(self.statusBar().showMessage)

        current_index = self.stack.currentIndex()
        old_widget = self.stack.widget(index)
        self.stack.blockSignals(True)
        self.stack.removeWidget(old_widget)
        old_widget.deleteLater()
        self.stack.insertWidget(index, real_tab)
        if make_current:
            self.stack.setCurrentIndex(index)
        else:
            self.stack.setCurrentIndex(current_index)
        self.stack.blockSignals(False)
        self._loaded_tabs.add(index)
        return real_tab

    def _go_to_tab(self, index):
        self.stack.setCurrentIndex(index)
        self._ensure_tab_loaded(index)
        self._sync_nav(index)
        self.statusBar().showMessage(f"Opened {self._tab_titles[index]}")

    def _sync_nav(self, index):
        for tab_index, button in self._nav_buttons + self._top_nav_buttons:
            button.setChecked(tab_index == index)
        self.global_context_btn.setVisible(index == 1)
        self.global_context_btn.setChecked(self._assistant_context_visible())

    def _set_global_status(self, message):
        self.statusBar().showMessage(message)
        self.global_status_chip.setText(message or "Ready")

    def _assistant_tab(self):
        self._load_tab(1)
        return self.stack.widget(1)

    def _assistant_context_visible(self):
        tab = self.stack.widget(1)
        drawer = getattr(tab, "context_drawer", None)
        return bool(drawer and not drawer.isHidden())

    def _toggle_assistant_context(self, checked):
        if self.stack.currentIndex() != 1:
            return
        tab = self._assistant_tab()
        drawer = getattr(tab, "context_drawer", None)
        if drawer:
            drawer.setVisible(checked)

    def _clear_assistant_chat(self):
        tab = self._assistant_tab()
        if hasattr(tab, "_clear_chat"):
            tab._clear_chat()
        self._go_to_tab(1)

    def _recheck_assistant_model(self):
        tab = self._assistant_tab()
        if hasattr(tab, "_recheck_model"):
            tab._recheck_model()
        self._go_to_tab(1)

    def _on_assistant_action_requested(self, kind, payload):
        if kind == "refresh_displays":
            tab = self._load_tab(6)
            if hasattr(tab, "load"):
                tab.load()
        elif kind == "refresh_audio":
            tab = self._load_tab(7)
            if hasattr(tab, "load"):
                tab.load()
        elif kind == "refresh_layouts":
            tab = self._load_tab(8)
            if hasattr(tab, "load"):
                tab.load()
            if hasattr(tab, "refresh_current_layout"):
                tab.refresh_current_layout()
        elif kind == "refresh_startup":
            tab = self._load_tab(9)
            if hasattr(tab, "load"):
                tab.load()
        elif kind == "scan_cleanup":
            tab = self._load_tab(3)
            if hasattr(tab, "start_scan"):
                tab.start_scan()

    def _jump_to_tool(self):
        text = ""
        if not text:
            return
        for keyword, index in _TOOL_SEARCH.items():
            if keyword in text:
                self._go_to_tab(index)
                return
        self.statusBar().showMessage("No matching tool found")


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(DARK_STYLESHEET)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
