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
QLabel[role="welcome-title"] {
    font-size: 24px;
    font-weight: 700;
    color: #f4f5fb;
}
QLabel[role="status-chip"] {
    color: #dce3ff;
    background-color: #252a3a;
    border: 1px solid #4a5a8a;
    border-radius: 999px;
    padding: 6px 12px;
    font-size: 12px;
    font-weight: 600;
}
QLabel[role="action-title"] {
    color: #ffffff;
    font-size: 15px;
    font-weight: 700;
}
QLabel[role="action-meta-label"] {
    color: #aeb6d4;
    font-size: 11px;
    font-weight: 700;
}
QLabel[role="action-meta-value"] {
    color: #e8ebf7;
    font-size: 12px;
    font-weight: 600;
}
QLabel[role="snapshot-key"] {
    color: #f0f2fb;
    font-weight: 600;
    min-width: 86px;
}
QFrame[role="message-user"] {
    background: qlineargradient(
        x1:0, y1:0, x2:1, y2:1,
        stop:0 #3a4f8f,
        stop:1 #2d3f72
    );
    border: 1px solid #5a74b5;
    border-top-left-radius: 16px;
    border-top-right-radius: 16px;
    border-bottom-left-radius: 16px;
    border-bottom-right-radius: 4px;
}
QFrame[role="message-assistant"] {
    background-color: #22252f;
    border: 1px solid #3a4050;
    border-top-left-radius: 16px;
    border-top-right-radius: 16px;
    border-bottom-left-radius: 4px;
    border-bottom-right-radius: 16px;
}
QFrame[role="message-system"] {
    background-color: #24332d;
    border: 1px solid #3d5c4e;
    border-radius: 12px;
}
QFrame[role="message-error"] {
    background-color: #3a2528;
    border: 1px solid #704045;
    border-radius: 12px;
}
QFrame[role="chat-thread"] {
    background-color: transparent;
    border: none;
}
QFrame[role="snapshot-panel"],
QFrame[role="missing-model"] {
    background-color: #22242c;
    border: 1px solid #383b48;
    border-radius: 14px;
}
QFrame[role="action-card"] {
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0 #262a36,
        stop:1 #1f222b
    );
    border: 1px solid #4a5878;
    border-radius: 14px;
}
QFrame[role="context-drawer"] {
    background-color: #1c1e26;
    border-left: 1px solid #343846;
    border-top: none;
    border-right: none;
    border-bottom: none;
    border-radius: 0;
}
QFrame[role="chat-input-dock"] {
    background-color: #252830;
    border: 1px solid #3d4254;
    border-radius: 16px;
}
QFrame[role="typing-indicator"] {
    background-color: #22252f;
    border: 1px solid #3a4050;
    border-top-left-radius: 16px;
    border-top-right-radius: 16px;
    border-bottom-left-radius: 4px;
    border-bottom-right-radius: 16px;
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
    background-color: #2a2c36;
    border: 1px solid #3c4050;
    border-radius: 10px;
    padding: 7px 14px;
}
QToolButton[role="header-menu-btn"]:checked {
    background-color: #32384c;
    border-color: #5a6ea8;
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
    background-color: #2b2c35;
    border: 1px solid #3a3d4a;
    border-radius: 10px;
}
QPushButton[variant="secondary"]:hover {
    background-color: #33343d;
    border-color: #4a4e5c;
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
    background-color: #232733;
    border: 1px solid #3a4154;
    border-radius: 14px;
    padding: 18px 16px;
    min-height: 56px;
    text-align: left;
    font-size: 13px;
    font-weight: 600;
}
QPushButton[variant="welcome-card"]:hover {
    background-color: #2b3140;
    border-color: #6d8dff;
    color: #ffffff;
}
QPushButton[variant="welcome-card"]:disabled {
    background-color: #22242c;
    border-color: #33343d;
    color: #6b6c78;
}
QPushButton[variant="chat-send"] {
    background: qlineargradient(
        x1:0, y1:0, x2:1, y2:1,
        stop:0 #6d8dff,
        stop:1 #5a6fd4
    );
    border-radius: 12px;
    padding: 12px 18px;
    min-width: 72px;
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
    background: qlineargradient(
        x1:0, y1:0, x2:1, y2:1,
        stop:0 #6d8dff,
        stop:1 #5a6fd4
    );
    border-radius: 10px;
    padding: 9px 18px;
    font-weight: 700;
}
QPushButton[variant="action-confirm"]:hover {
    background: qlineargradient(
        x1:0, y1:0, x2:1, y2:1,
        stop:0 #82a0ff,
        stop:1 #6d8dff
    );
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
    border: none;
    background-color: transparent;
    color: #f0f2fb;
    padding: 6px 4px;
    font-size: 13px;
}
QFrame[role="chat-input-dock"] QTextEdit:disabled {
    color: #6b6c78;
    background-color: transparent;
}
QFrame[role="chat-input-dock"] QTextEdit:focus {
    border: none;
    background-color: transparent;
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
