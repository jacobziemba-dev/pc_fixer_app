DARK_STYLESHEET = """
QWidget {
    background-color: #0e1117;
    color: #e6e6ec;
    font-family: 'Segoe UI', sans-serif;
    font-size: 13px;
}
QMainWindow {
    background-color: #0e1117;
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
    color: #a5a9b7;
    font-size: 12px;
}
QLabel[role="eyebrow"] {
    color: #9fb9ff;
    font-size: 12px;
    font-weight: 700;
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
QLabel[role="welcome-title"] {
    font-size: 25px;
    font-weight: 700;
    color: #f4f5fb;
}
QLabel[role="status-chip"] {
    color: #e8edf7;
    background-color: #111721;
    border: 1px solid #303846;
    border-radius: 12px;
    padding: 8px 16px;
    font-size: 12px;
    font-weight: 600;
}
QLabel[role="action-title"] {
    color: #8ee66b;
    font-size: 15px;
    font-weight: 700;
}
QLabel[role="action-description"] {
    color: #d8dce7;
    font-size: 13px;
}
QLabel[role="action-meta-label"] {
    color: #aeb6d4;
    font-size: 11px;
    font-weight: 700;
}
QLabel[role="action-meta-value"] {
    color: #9da4b3;
    font-size: 11px;
    font-weight: 500;
}
QLabel[role="snapshot-key"] {
    color: #f0f2fb;
    font-weight: 600;
    min-width: 74px;
}
QLabel[role="status-dot"] {
    border-radius: 5px;
    min-width: 10px;
    min-height: 10px;
    max-width: 10px;
    max-height: 10px;
}
QLabel[role="status-dot"][state="good"] {
    background-color: #8ee66b;
}
QLabel[role="status-dot"][state="warn"] {
    background-color: #ffc857;
}
QLabel[role="status-dot"][state="danger"] {
    background-color: #ff5c5c;
}
QLabel[role="action-icon"] {
    color: #8ee66b;
    font-size: 28px;
    font-weight: 900;
    min-width: 32px;
}
QFrame[role="message-user"] {
    background: qlineargradient(
        x1:0, y1:0, x2:1, y2:1,
        stop:0 #315a98,
        stop:1 #243f70
    );
    border: 1px solid #3e6fac;
    border-top-left-radius: 12px;
    border-top-right-radius: 12px;
    border-bottom-left-radius: 12px;
    border-bottom-right-radius: 4px;
}
QFrame[role="message-assistant"] {
    background-color: #151a22;
    border: 1px solid #303744;
    border-top-left-radius: 12px;
    border-top-right-radius: 12px;
    border-bottom-left-radius: 4px;
    border-bottom-right-radius: 12px;
}
QFrame[role="message-system"] {
    background-color: #102119;
    border: 1px solid #356d2c;
    border-radius: 10px;
}
QFrame[role="message-error"] {
    background-color: #3a2528;
    border: 1px solid #704045;
    border-radius: 12px;
}
QFrame[role="chat-thread"] {
    background-color: #0c1016;
    border: 1px solid #2c3442;
    border-top-left-radius: 8px;
    border-bottom-left-radius: 8px;
    border-top-right-radius: 0;
    border-bottom-right-radius: 0;
}
QFrame[role="snapshot-panel"],
QFrame[role="missing-model"] {
    background-color: #22242c;
    border: 1px solid #383b48;
    border-radius: 14px;
}
QFrame[role="action-card"] {
    background: qlineargradient(
        x1:0, y1:0, x2:1, y2:0,
        stop:0 #102417,
        stop:1 #0e1a12
    );
    border: 1px solid #3b7d2c;
    border-radius: 8px;
}
QFrame[role="context-drawer"] {
    background-color: #0c1016;
    border: 1px solid #2c3442;
    border-left: none;
    border-top-right-radius: 8px;
    border-bottom-right-radius: 8px;
    border-top-left-radius: 0;
    border-bottom-left-radius: 0;
}
QFrame[role="context-rows"] {
    background-color: #10151d;
    border: 1px solid #29313d;
    border-radius: 8px;
}
QFrame[role="context-row"] {
    background-color: transparent;
    border-bottom: 1px solid #252c36;
}
QFrame[role="chat-input-dock"] {
    background-color: #10151d;
    border-top: 1px solid #2c3442;
    border-left: none;
    border-right: none;
    border-bottom: none;
    border-radius: 0;
}
QFrame[role="typing-indicator"] {
    background-color: #151a22;
    border: 1px solid #303744;
    border-top-left-radius: 12px;
    border-top-right-radius: 12px;
    border-bottom-left-radius: 4px;
    border-bottom-right-radius: 12px;
}
QScrollArea[role="chat-scroll"] {
    background-color: transparent;
    border: none;
    border-radius: 0;
}
QToolButton {
    background-color: #24252d;
    color: #ffffff;
    border: 1px solid #33343d;
    border-radius: 8px;
    padding: 7px 10px;
    font-weight: 600;
}
QToolButton:hover {
    background-color: #2b2c35;
}
QToolButton[role="header-menu-btn"] {
    background-color: #111721;
    border: 1px solid #303846;
    border-radius: 12px;
    padding: 8px 16px;
}
QToolButton[role="header-menu-btn"]:checked {
    background-color: #14233b;
    border-color: #2e5fa0;
    color: #e8ecff;
}
QMenu {
    background-color: #24252d;
    color: #ffffff;
    border: 1px solid #33343d;
    padding: 4px;
}
QMenu::item {
    padding: 7px 22px;
}
QMenu::item:selected {
    background-color: #30384d;
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
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0 #4a5c9a,
        stop:1 #3d4a7a
    );
    color: #ffffff;
    border: none;
    border-radius: 10px;
    padding: 9px 16px;
    font-weight: 600;
}
QPushButton:hover {
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0 #576db0,
        stop:1 #4a58a0
    );
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
    background-color: #111721;
    border: 1px solid #303846;
    border-radius: 8px;
}
QPushButton[variant="secondary"]:hover {
    background-color: #151c28;
    border-color: #3d4858;
}
QPushButton[variant="chip"] {
    background-color: #252a36;
    border: 1px solid #3b4358;
    border-radius: 8px;
    padding: 7px 11px;
}
QPushButton[variant="chip"]:hover {
    background-color: #30384d;
}
QPushButton[variant="welcome-card"] {
    background-color: #10151d;
    border: 1px solid #303846;
    border-radius: 8px;
    padding: 18px 20px;
    min-height: 92px;
    min-width: 146px;
    text-align: left;
    font-size: 14px;
    font-weight: 600;
}
QPushButton[variant="welcome-card"]:hover {
    background-color: #141b25;
    border-color: #3776d6;
    color: #ffffff;
}
QPushButton[variant="welcome-card"]:disabled {
    background-color: #10141b;
    border-color: #252c36;
    color: #6b6c78;
}
QPushButton[variant="chat-send"] {
    background: qlineargradient(
        x1:0, y1:0, x2:1, y2:1,
        stop:0 #3b82f6,
        stop:1 #285fbd
    );
    border-radius: 8px;
    padding: 12px 18px;
    min-width: 86px;
    font-weight: 700;
}
QPushButton[variant="chat-send"]:hover {
    background: qlineargradient(
        x1:0, y1:0, x2:1, y2:1,
        stop:0 #82a0ff,
        stop:1 #6d8dff
    );
}
QPushButton[variant="chat-send"]:disabled {
    background-color: #2b2c35;
    color: #6b6c78;
}
QPushButton[variant="action-confirm"] {
    background-color: #102417;
    border: 1px solid #4d993d;
    color: #8ee66b;
    border-radius: 8px;
    padding: 9px 18px;
    font-weight: 700;
}
QPushButton[variant="action-confirm"]:hover {
    background-color: #17311f;
}
QPushButton[variant="action-confirm"]:disabled {
    background-color: #2b2c35;
    color: #6b6c78;
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
QFrame[role="chat-input-dock"] QTextEdit {
    border: 1px solid #303846;
    border-radius: 8px;
    background-color: #0d1219;
    color: #f0f2fb;
    padding: 10px 12px;
    font-size: 13px;
}
QFrame[role="chat-input-dock"] QTextEdit:disabled {
    color: #6b6c78;
    background-color: #0d1219;
}
QFrame[role="chat-input-dock"] QTextEdit:focus {
    border: 1px solid #3b82f6;
    background-color: #0d1219;
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
