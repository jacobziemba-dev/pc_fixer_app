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
QLabel[role="caption"][state="success"] {
    color: #9ee0b1;
}
QLabel[role="caption"][state="error"] {
    color: #ff9ea5;
}
QLabel[role="heading"] {
    font-size: 16px;
    font-weight: 700;
    color: #ffffff;
}
QLabel[role="status-chip"] {
    color: #d7ddff;
    background-color: #2b2f3f;
    border: 1px solid #3a425d;
    border-radius: 6px;
    padding: 5px 8px;
    font-size: 12px;
}
QLabel[role="action-title"] {
    color: #ffffff;
    font-weight: 700;
}
QLabel[role="snapshot-key"] {
    color: #f0f2fb;
    font-weight: 600;
    min-width: 86px;
}
QFrame[role="message-user"] {
    background-color: #334a7d;
    border: 1px solid #49649c;
    border-radius: 8px;
}
QFrame[role="message-assistant"] {
    background-color: #252832;
    border: 1px solid #363b4a;
    border-radius: 8px;
}
QFrame[role="message-system"] {
    background-color: #26352f;
    border: 1px solid #3a594b;
    border-radius: 8px;
}
QFrame[role="message-error"] {
    background-color: #3a2528;
    border: 1px solid #704045;
    border-radius: 8px;
}
QFrame[role="snapshot-panel"],
QFrame[role="missing-model"],
QFrame[role="action-card"] {
    background-color: #24252d;
    border: 1px solid #33343d;
    border-radius: 8px;
}
QFrame[role="action-card"] {
    border-color: #4a5678;
}
QScrollArea[role="chat-scroll"] {
    background-color: #202129;
    border: 1px solid #33343d;
    border-radius: 8px;
}
QToolButton {
    background-color: #24252d;
    color: #ffffff;
    border: 1px solid #33343d;
    border-radius: 6px;
    padding: 7px 10px;
    font-weight: 600;
}
QToolButton:hover {
    background-color: #2b2c35;
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
QPushButton[variant="chip"] {
    background-color: #252a36;
    border: 1px solid #3b4358;
    border-radius: 6px;
    padding: 7px 11px;
}
QPushButton[variant="chip"]:hover {
    background-color: #30384d;
}
QScrollArea {
    border: none;
}
QLineEdit {
    background-color: #24252d;
    color: #ffffff;
    border: 1px solid #33343d;
    border-radius: 6px;
    padding: 8px 10px;
}
QLineEdit:disabled {
    color: #6b6c78;
    background-color: #202129;
}
QTextEdit {
    background-color: #24252d;
    color: #e6e6ec;
    border: 1px solid #33343d;
    border-radius: 6px;
    padding: 8px;
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
