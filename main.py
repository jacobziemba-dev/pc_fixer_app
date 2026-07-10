import sys

from PySide6.QtWidgets import QApplication, QMainWindow, QTabWidget

from app.theme import DARK_STYLESHEET
from app.dashboard_tab import DashboardTab
from app.hardware_tab import HardwareTab
from app.display_tab import DisplayTab
from app.startup_tab import StartupTab
from app.cleanup_tab import CleanupTab


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PC Fix - Performance & Cleanup")
        self.resize(1080, 720)

        tabs = QTabWidget()
        tabs.addTab(DashboardTab(), "Dashboard")
        tabs.addTab(HardwareTab(), "PC Setup")
        tabs.addTab(DisplayTab(), "Display")
        tabs.addTab(StartupTab(), "Startup & Programs")
        tabs.addTab(CleanupTab(), "Cleanup")
        self.setCentralWidget(tabs)


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(DARK_STYLESHEET)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
