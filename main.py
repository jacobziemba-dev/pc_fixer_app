import sys

from PySide6.QtWidgets import QApplication, QMainWindow, QTabWidget, QWidget, QLabel, QVBoxLayout

from app.theme import DARK_STYLESHEET
from app.dashboard_tab import DashboardTab


# Heavy tabs are created on first visit to keep startup responsive.
_LAZY_TABS = {
    1: ("app.hardware_tab", "HardwareTab", "PC Setup"),
    2: ("app.display_tab", "DisplayTab", "Display"),
    3: ("app.audio_tab", "AudioTab", "Audio"),
    4: ("app.layouts_tab", "LayoutsTab", "Layouts"),
    5: ("app.startup_tab", "StartupTab", "Startup & Programs"),
    6: ("app.assistant_tab", "AssistantTab", "Assistant"),
    7: ("app.cleanup_tab", "CleanupTab", "Cleanup"),
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
        self.tabs.addTab(_placeholder("Loading PC Setup..."), "PC Setup")
        self.tabs.addTab(_placeholder("Loading Display..."), "Display")
        self.tabs.addTab(_placeholder("Loading Audio..."), "Audio")
        self.tabs.addTab(_placeholder("Loading Layouts..."), "Layouts")
        self.tabs.addTab(_placeholder("Loading Startup & Programs..."), "Startup & Programs")
        self.tabs.addTab(_placeholder("Loading Assistant..."), "Assistant")
        self.tabs.addTab(_placeholder("Loading Cleanup..."), "Cleanup")

        self._loaded_tabs = {0}  # Dashboard is eager
        self.tabs.currentChanged.connect(self._ensure_tab_loaded)
        self.setCentralWidget(self.tabs)

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
            tab = self._load_tab(2)
            if hasattr(tab, "load"):
                tab.load()
        elif kind == "refresh_audio":
            tab = self._load_tab(3)
            if hasattr(tab, "load"):
                tab.load()
        elif kind == "refresh_layouts":
            tab = self._load_tab(4)
            if hasattr(tab, "load"):
                tab.load()
            if hasattr(tab, "refresh_current_layout"):
                tab.refresh_current_layout()
        elif kind == "refresh_startup":
            tab = self._load_tab(5)
            if hasattr(tab, "load"):
                tab.load()
        elif kind == "scan_cleanup":
            tab = self._load_tab(7)
            if hasattr(tab, "start_scan"):
                tab.start_scan()


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(DARK_STYLESHEET)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
