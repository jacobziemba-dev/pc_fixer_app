import sys

from PySide6.QtWidgets import QApplication, QMainWindow, QTabWidget, QWidget, QLabel, QVBoxLayout

from app.theme import DARK_STYLESHEET
from app.dashboard_tab import DashboardTab
from app.cleanup_tab import CleanupTab


# Heavy tabs are created on first visit to keep startup responsive.
_LAZY_TABS = {
    1: ("app.hardware_tab", "HardwareTab", "PC Setup"),
    2: ("app.display_tab", "DisplayTab", "Display"),
    3: ("app.layouts_tab", "LayoutsTab", "Layouts"),
    4: ("app.startup_tab", "StartupTab", "Startup & Programs"),
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
        self.tabs.addTab(_placeholder("Loading Layouts..."), "Layouts")
        self.tabs.addTab(_placeholder("Loading Startup & Programs..."), "Startup & Programs")
        self.tabs.addTab(CleanupTab(), "Cleanup")

        self._loaded_tabs = {0, 5}  # Dashboard and Cleanup are eager
        self.tabs.currentChanged.connect(self._ensure_tab_loaded)
        self.setCentralWidget(self.tabs)

    def _ensure_tab_loaded(self, index):
        if index in self._loaded_tabs or index not in _LAZY_TABS:
            return

        module_name, class_name, title = _LAZY_TABS[index]
        module = __import__(module_name, fromlist=[class_name])
        tab_cls = getattr(module, class_name)
        real_tab = tab_cls()

        self.tabs.blockSignals(True)
        self.tabs.removeTab(index)
        self.tabs.insertTab(index, real_tab, title)
        self.tabs.setCurrentIndex(index)
        self.tabs.blockSignals(False)
        self._loaded_tabs.add(index)


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(DARK_STYLESHEET)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
