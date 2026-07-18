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
QFrame[role="app-shell"] {
    background-color: #0e1117;
    border: 1px solid #1f2630;
}
QFrame[role="top-bar"] {
    background-color: #0d1118;
    border-bottom: 1px solid #232b36;
}
QFrame[role="side-bar"] {
    background-color: #0d1118;
    border-right: 1px solid #232b36;
    min-width: 190px;
    max-width: 210px;
}
QFrame[role="top-nav"] {
    background-color: #0d1118;
    border: 1px solid #303846;
    border-radius: 10px;
}
QFrame[role="protected-card"] {
    background-color: #10151d;
    border: 1px solid #151b24;
    border-radius: 8px;
}
QLabel[role="app-logo"] {
    color: #58a0ff;
    border: 2px solid #3b82f6;
    border-radius: 4px;
    min-width: 34px;
    min-height: 28px;
    max-width: 34px;
    max-height: 28px;
    font-weight: 900;
}
QLabel[role="app-title"] {
    color: #ffffff;
    font-size: 25px;
    font-weight: 800;
}
QLabel[role="protected-title"] {
    color: #8ee66b;
    font-size: 14px;
    font-weight: 700;
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
    background-color: transparent;
    color: #e6e6ec;
}
QLabel[role="message-text"] {
    background-color: transparent;
    color: #e9edf7;
    font-size: 14px;
    font-weight: 450;
    selection-background-color: #294b78;
    selection-color: #ffffff;
}
QLabel[role="message-text"][tone="user"] {
    color: #f8fbff;
    font-weight: 600;
    selection-background-color: #d8e8ff;
    selection-color: #07111f;
}
QLabel[role="message-text"][tone="system"] {
    color: #d9f4da;
}
QLabel[role="message-text"][tone="error"] {
    color: #ffe4e6;
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
    color: #b8f28c;
    font-size: 14px;
    font-weight: 800;
}
QLabel[role="action-description"] {
    color: #eef5e9;
    font-size: 13px;
    font-weight: 600;
}
QLabel[role="action-meta-label"] {
    color: #aeb6d4;
    font-size: 11px;
    font-weight: 700;
}
QLabel[role="action-meta-value"] {
    color: #9fb29e;
    font-size: 11px;
    font-weight: 600;
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
    color: #07110b;
    background-color: #8ee66b;
    border: 1px solid #b8f28c;
    border-radius: 11px;
    font-size: 14px;
    font-weight: 900;
    min-width: 22px;
    min-height: 22px;
    max-width: 22px;
    max-height: 22px;
}
QFrame[role="message-user"] {
    background: qlineargradient(
        x1:0, y1:0, x2:1, y2:1,
        stop:0 #2f6fbd,
        stop:1 #214d86
    );
    border: 1px solid #4b88d7;
    border-top-left-radius: 14px;
    border-top-right-radius: 14px;
    border-bottom-left-radius: 14px;
    border-bottom-right-radius: 5px;
}
QFrame[role="message-assistant"] {
    background-color: #121821;
    border: 1px solid #303b4a;
    border-top-left-radius: 14px;
    border-top-right-radius: 14px;
    border-bottom-left-radius: 5px;
    border-bottom-right-radius: 14px;
}
QFrame[role="message-system"] {
    background-color: #102018;
    border: 1px solid #326c38;
    border-radius: 12px;
}
QFrame[role="message-error"] {
    background-color: #341f25;
    border: 1px solid #7b444c;
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
        x1:0, y1:0, x2:1, y2:1,
        stop:0 #122418,
        stop:1 #0d1712
    );
    border: 1px solid #2f7d35;
    border-left: 4px solid #8ee66b;
    border-radius: 10px;
}
QFrame[role="layout-card"] {
    background-color: #171a22;
    border: 1px solid #2c3442;
    border-radius: 12px;
}
QFrame[role="layout-card"]:hover {
    border-color: #3b4a63;
}
QFrame[role="layout-card"][state="selected"] {
    border: 1px solid #3b82f6;
    background-color: #131c2b;
}
QLabel[role="layout-card-title"] {
    color: #f4f5fb;
    font-size: 14px;
    font-weight: 700;
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
QPushButton[variant="action-secondary"] {
    background-color: #10151d;
    border: 1px solid #344235;
    border-radius: 8px;
    color: #d8e4d8;
    padding: 8px 14px;
    min-width: 70px;
    font-size: 12px;
}
QPushButton[variant="action-secondary"]:hover {
    background-color: #162018;
    border-color: #4e664c;
    color: #ffffff;
}
QPushButton[variant="top-nav"] {
    background-color: transparent;
    border: none;
    border-radius: 8px;
    color: #d7dae3;
    min-width: 104px;
    padding: 9px 18px;
    font-size: 14px;
}
QPushButton[variant="top-nav"]:checked {
    background: qlineargradient(
        x1:0, y1:0, x2:1, y2:1,
        stop:0 #1d3a62,
        stop:1 #172b4a
    );
    color: #ffffff;
}
QPushButton[variant="top-nav"]:hover {
    background-color: #141b25;
}
QPushButton[variant="side-nav"] {
    background-color: transparent;
    border: none;
    border-radius: 8px;
    color: #c8ccd6;
    text-align: left;
    padding: 13px 16px;
    min-height: 24px;
    font-size: 15px;
    font-weight: 500;
}
QPushButton[variant="side-nav"]:checked {
    background: qlineargradient(
        x1:0, y1:0, x2:1, y2:0,
        stop:0 #183254,
        stop:1 #121a25
    );
    border-left: 3px solid #3b82f6;
    color: #9ec8ff;
}
QPushButton[variant="side-nav"]:hover {
    background-color: #141b25;
    color: #ffffff;
}
QPushButton[variant="card-danger"] {
    background-color: #3a1e1e;
    border: 1px solid #a04a4a;
    color: #ffb3b3;
    border-radius: 8px;
    padding: 8px 16px;
    min-width: 70px;
    font-size: 12px;
    font-weight: 700;
}
QPushButton[variant="card-danger"]:hover {
    background-color: #4a2424;
    border-color: #c25a5a;
}
QPushButton[variant="row-remove"] {
    background-color: #1a1e27;
    border: 1px solid #33394a;
    color: #c7cbe0;
    border-radius: 6px;
    padding: 3px 9px;
    min-width: 0;
    font-size: 12px;
    font-weight: 700;
}
QPushButton[variant="row-remove"]:hover {
    background-color: #2a2020;
    border-color: #a04a4a;
    color: #ffb3b3;
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
    padding: 20px 22px;
    min-height: 112px;
    min-width: 165px;
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
    background-color: #17391e;
    border: 1px solid #66bd52;
    color: #b8f28c;
    border-radius: 8px;
    padding: 8px 16px;
    min-width: 70px;
    font-size: 12px;
    font-weight: 700;
}
QPushButton[variant="action-confirm"]:hover {
    background-color: #1f4b28;
    border-color: #8ee66b;
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
