from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout


def clear_layout(layout):
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.deleteLater()
        elif item.layout() is not None:
            clear_layout(item.layout())


class _ClickableFrame(QFrame):
    def __init__(self, on_click):
        super().__init__()
        self._on_click = on_click

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self._on_click:
            self._on_click()
        super().mousePressEvent(event)


def build_context_row(primary_text, secondary_text="", meta_text="", trailing=None, on_click=None):
    row = _ClickableFrame(on_click) if on_click is not None else QFrame()
    row.setProperty("role", "context-row")
    if on_click is not None:
        row.setCursor(Qt.PointingHandCursor)
    row_layout = QHBoxLayout(row)
    row_layout.setContentsMargins(4, 10, 4, 10)
    row_layout.setSpacing(10)

    text_col = QVBoxLayout()
    text_col.setSpacing(2)
    primary = QLabel(primary_text)
    primary.setProperty("role", "snapshot-key")
    primary.setWordWrap(True)
    text_col.addWidget(primary)
    if secondary_text:
        secondary = QLabel(secondary_text)
        secondary.setProperty("role", "caption")
        secondary.setWordWrap(True)
        text_col.addWidget(secondary)
    row_layout.addLayout(text_col, 1)

    if meta_text:
        meta = QLabel(meta_text)
        meta.setProperty("role", "caption")
        meta.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        row_layout.addWidget(meta)

    if trailing is not None:
        row_layout.addWidget(trailing)

    return row


def empty_row(message):
    row = QFrame()
    row.setProperty("role", "context-row")
    row_layout = QHBoxLayout(row)
    row_layout.setContentsMargins(4, 14, 4, 14)
    label = QLabel(message)
    label.setProperty("role", "caption")
    label.setWordWrap(True)
    row_layout.addWidget(label)
    return row


def rows_card():
    card = QFrame()
    card.setProperty("role", "context-rows")
    card_layout = QVBoxLayout(card)
    card_layout.setContentsMargins(10, 6, 10, 6)
    card_layout.setSpacing(0)
    rows_layout = QVBoxLayout()
    rows_layout.setSpacing(0)
    card_layout.addLayout(rows_layout)
    return card, rows_layout


def section_panel(eyebrow_text):
    panel = QFrame()
    panel.setProperty("role", "snapshot-panel")
    panel_layout = QVBoxLayout(panel)
    panel_layout.setContentsMargins(16, 14, 16, 16)
    panel_layout.setSpacing(10)

    eyebrow = QLabel(eyebrow_text)
    eyebrow.setProperty("role", "eyebrow")
    panel_layout.addWidget(eyebrow)

    body = QVBoxLayout()
    body.setSpacing(10)
    panel_layout.addLayout(body, 1)

    return panel, body
