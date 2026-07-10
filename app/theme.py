DARK_STYLESHEET = """
QWidget {
    background-color: #1e1f26;
    color: #e6e6ec;
    font-family: 'Segoe UI', sans-serif;
    font-size: 13px;
}
QMainWindow {
    background-color: #1e1f26;
}
QTabWidget::pane {
    border: 1px solid #33343d;
    border-radius: 6px;
    top: -1px;
}
QTabBar::tab {
    background: #26272f;
    color: #b7b8c2;
    padding: 9px 18px;
    margin-right: 2px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
}
QTabBar::tab:selected {
    background: #33343d;
    color: #ffffff;
    font-weight: 600;
}
QTabBar::tab:hover {
    color: #ffffff;
}
QGroupBox {
    border: 1px solid #33343d;
    border-radius: 8px;
    margin-top: 14px;
    padding: 12px;
    font-weight: 600;
    color: #a6b8ff;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 6px;
}
QLabel {
    color: #e6e6ec;
}
QLabel[role="metric"] {
    font-size: 22px;
    font-weight: 700;
    color: #ffffff;
}
QLabel[role="caption"] {
    color: #9294a3;
    font-size: 12px;
}
QLabel[role="heading"] {
    font-size: 16px;
    font-weight: 700;
    color: #ffffff;
}
QProgressBar {
    border: none;
    border-radius: 5px;
    background-color: #2b2c35;
    height: 10px;
    text-align: center;
    color: transparent;
}
QProgressBar::chunk {
    border-radius: 5px;
    background-color: #6d8dff;
}
QProgressBar[level="warn"]::chunk {
    background-color: #f5a623;
}
QProgressBar[level="danger"]::chunk {
    background-color: #ef5350;
}
QTableWidget {
    background-color: #24252d;
    alternate-background-color: #292a33;
    gridline-color: #33343d;
    border: 1px solid #33343d;
    border-radius: 6px;
    selection-background-color: #3d4a7a;
}
QHeaderView::section {
    background-color: #2b2c35;
    color: #b7b8c2;
    padding: 6px;
    border: none;
    border-bottom: 1px solid #33343d;
    font-weight: 600;
}
QPushButton {
    background-color: #3d4a7a;
    color: #ffffff;
    border: none;
    border-radius: 6px;
    padding: 8px 16px;
    font-weight: 600;
}
QPushButton:hover {
    background-color: #4a58a0;
}
QPushButton:disabled {
    background-color: #2b2c35;
    color: #6b6c78;
}
QPushButton[variant="danger"] {
    background-color: #7a3d3d;
}
QPushButton[variant="danger"]:hover {
    background-color: #a04a4a;
}
QPushButton[variant="secondary"] {
    background-color: #2b2c35;
    border: 1px solid #33343d;
}
QPushButton[variant="secondary"]:hover {
    background-color: #33343d;
}
QScrollArea {
    border: none;
}
QCheckBox {
    spacing: 8px;
}
QComboBox {
    background-color: #2b2c35;
    color: #ffffff;
    border: 1px solid #33343d;
    border-radius: 6px;
    padding: 7px 10px;
}
QComboBox:disabled {
    color: #6b6c78;
}
QComboBox QAbstractItemView {
    background-color: #24252d;
    color: #ffffff;
    selection-background-color: #3d4a7a;
    border: 1px solid #33343d;
}
QSplitter::handle {
    background-color: #33343d;
}
"""
