import sys

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QTabWidget, QWidget, QLabel, QVBoxLayout,
    QLineEdit,
)

from app.theme import DARK_STYLESHEET
from app.dashboard_tab import DashboardTab


# Heavy tabs are created on first visit to keep startup responsive.
_LAZY_TABS = {
    1: ("app.assistant_tab", "AssistantTab", "Assistant"),
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
        self.resize(1080, 720)

        self.tabs = QTabWidget()
        self.tabs.addTab(DashboardTab(), "Dashboard")
        self.tabs.addTab(_placeholder("Loading Assistant..."), "Assistant")
        self.tabs.addTab(_placeholder("Loading Health..."), "Health")
        self.tabs.addTab(_placeholder("Loading Cleanup..."), "Cleanup")
        self.tabs.addTab(_placeholder("Loading Performance..."), "Performance")
        self.tabs.addTab(_placeholder("Loading Network..."), "Network")
        self.tabs.addTab(_placeholder("Loading Display..."), "Display")
        self.tabs.addTab(_placeholder("Loading Audio..."), "Audio")
        self.tabs.addTab(_placeholder("Loading Layouts..."), "Layouts")
        self.tabs.addTab(_placeholder("Loading Startup & Programs..."), "Startup & Programs")
        self.tabs.addTab(_placeholder("Loading PC Setup..."), "PC Setup")
        self.tabs.addTab(_placeholder("Loading Reports..."), "Reports")

        self._loaded_tabs = {0}  # Dashboard is eager
        self.tabs.currentChanged.connect(self._ensure_tab_loaded)

        shell = QWidget()
        shell_layout = QVBoxLayout(shell)
        shell_layout.setContentsMargins(8, 8, 8, 8)
        self.tool_search = QLineEdit()
        self.tool_search.setPlaceholderText("Find a tool: cleanup, network, disk, audio, report...")
        self.tool_search.returnPressed.connect(self._jump_to_tool)
        shell_layout.addWidget(self.tool_search)
        shell_layout.addWidget(self.tabs, 1)
        self.setCentralWidget(shell)
        self.statusBar().showMessage("Ready")

    def _ensure_tab_loaded(self, index):
        if index in self._loaded_tabs or index not in _LAZY_TABS:
            return
        self._load_tab(index, make_current=True)

    def _load_tab(self, index, make_current=False):
        if index in self._loaded_tabs or index not in _LAZY_TABS:
            return self.tabs.widget(index)
        module_name, class_name, title = _LAZY_TABS[index]
        module = __import__(module_name, fromlist=[class_name])
        tab_cls = getattr(module, class_name)
        real_tab = tab_cls()
        if hasattr(real_tab, "action_requested"):
            real_tab.action_requested.connect(self._on_assistant_action_requested)
        if hasattr(real_tab, "status_changed"):
            real_tab.status_changed.connect(self.statusBar().showMessage)

        current_widget = self.tabs.currentWidget()
        self.tabs.blockSignals(True)
        self.tabs.removeTab(index)
        self.tabs.insertTab(index, real_tab, title)
        if make_current:
            self.tabs.setCurrentIndex(index)
        elif current_widget is not None:
            self.tabs.setCurrentWidget(current_widget)
        self.tabs.blockSignals(False)
        self._loaded_tabs.add(index)
        return real_tab

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
        text = self.tool_search.text().strip().lower()
        if not text:
            return
        for keyword, index in _TOOL_SEARCH.items():
            if keyword in text:
                self.tabs.setCurrentIndex(index)
                self._ensure_tab_loaded(index)
                self.statusBar().showMessage(f"Opened {self.tabs.tabText(index)}")
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
