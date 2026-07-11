from PySide6.QtCore import Signal, Qt, QEvent
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class MessageBubble(QFrame):
    def __init__(self, role, text=""):
        super().__init__()
        self.setProperty("role", f"message-{role}")
        max_width = 660 if role in ("user", "assistant") else 560
        self.setMaximumWidth(max_width)
        self.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Minimum)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        self.text_label = QLabel(text)
        self.text_label.setWordWrap(True)
        self.text_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(self.text_label)

    def append_text(self, text):
        self.text_label.setText(self.text_label.text() + text)

    def set_text(self, text):
        self.text_label.setText(text)

    def text(self):
        return self.text_label.text()


class ChatMessageRow(QWidget):
    def __init__(self, role, text=""):
        super().__init__()
        self.setProperty("role", "chat-message-row")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.bubble = MessageBubble(role, text)
        if role == "user":
            layout.addStretch(1)
            layout.addWidget(self.bubble)
        elif role in ("system", "error"):
            layout.addStretch(1)
            layout.addWidget(self.bubble)
            layout.addStretch(1)
        else:
            layout.addWidget(self.bubble)
            layout.addStretch(1)


class ActionCard(QFrame):
    confirmed = Signal(object, object)

    def __init__(self, action):
        super().__init__()
        self._action = action
        self.setProperty("role", "action-card")
        self.setMaximumWidth(660)
        self.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Minimum)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)

        title = QLabel(action.title)
        title.setProperty("role", "action-title")
        title.setWordWrap(True)
        layout.addWidget(title)

        desc = QLabel(action.description)
        desc.setProperty("role", "caption")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        target_text = self._target_text(action)
        if target_text:
            target = QLabel(f"Target: {target_text}")
            target.setProperty("role", "caption")
            target.setWordWrap(True)
            layout.addWidget(target)

        change_text = (
            "Changes PC: yes, confirmation required"
            if action.requires_confirmation
            else "Changes PC: no, read-only"
        )
        change = QLabel(change_text)
        change.setProperty("role", "caption")
        change.setWordWrap(True)
        layout.addWidget(change)

        expected = QLabel(f"Expected result: {self._expected_result(action)}")
        expected.setProperty("role", "caption")
        expected.setWordWrap(True)
        layout.addWidget(expected)

        risk = QLabel(f"Risk: {action.risk}")
        risk.setProperty("role", "caption")
        layout.addWidget(risk)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self.cancel_btn = QPushButton(action.cancel_label)
        self.cancel_btn.setProperty("variant", "secondary")
        self.cancel_btn.clicked.connect(self._cancel)
        self.confirm_btn = QPushButton(action.confirm_label)
        self.confirm_btn.clicked.connect(self._confirm)
        buttons.addWidget(self.cancel_btn)
        buttons.addWidget(self.confirm_btn)
        layout.addLayout(buttons)

    def _confirm(self):
        self._set_done("Confirmed")
        self.confirmed.emit(self._action, self)

    def _cancel(self):
        self._set_done("Cancelled")

    def _set_done(self, text):
        self.confirm_btn.setEnabled(False)
        self.cancel_btn.setEnabled(False)
        self.confirm_btn.setText(text)

    def _target_text(self, action):
        payload = action.payload or {}
        candidates = [
            payload.get("device_name"),
            payload.get("device_id"),
            payload.get("process_name"),
            payload.get("pid"),
            payload.get("layout_id"),
            ", ".join(payload.get("category_keys", []))
            if isinstance(payload.get("category_keys"), list)
            else "",
            payload.get("adapter_name"),
            payload.get("plan_name"),
            payload.get("root"),
        ]
        return next((str(value) for value in candidates if value), "")

    def _expected_result(self, action):
        if action.kind.startswith("refresh") or action.kind.startswith("check") or action.kind.startswith("scan"):
            return "collect current information and update the app."
        if action.kind == "clean_cleanup_candidates":
            return "delete only the scanned cleanup categories shown in this app."
        if action.kind == "set_display_refresh_rate":
            return "change only the selected display refresh rate."
        if action.kind.startswith("audio_"):
            return "apply the selected audio change to the resolved app session."
        if action.kind == "load_saved_layout":
            return "move matching windows and launch missing apps when possible."
        if action.kind == "flush_dns_cache":
            return "clear Windows DNS resolver cache."
        if action.kind == "restart_network_adapter":
            return "restart the selected network adapter."
        if action.kind == "set_power_plan":
            return "switch the active Windows power plan."
        if action.kind == "create_restore_point":
            return "ask Windows to create a system restore point."
        if action.kind == "export_pc_report":
            return "write a local diagnostic report file."
        return "run the selected PC Fix tool."


class WelcomeState(QWidget):
    prompt_selected = Signal(str, str, bool)

    def __init__(self, quick_actions):
        super().__init__()
        self.setProperty("role", "welcome-state")
        self._buttons = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 24, 4, 20)
        layout.setSpacing(14)

        title = QLabel("How can I help with this PC?")
        title.setProperty("role", "welcome-title")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        note = QLabel("Local AI can inspect diagnostics, suggest safe tools, and ask before changing anything.")
        note.setProperty("role", "caption")
        note.setAlignment(Qt.AlignCenter)
        note.setWordWrap(True)
        layout.addWidget(note)

        grid = QGridLayout()
        grid.setSpacing(8)
        for index, (label, prompt, include_cleanup) in enumerate(quick_actions):
            button = QPushButton(label)
            button.setProperty("variant", "welcome-card")
            button.clicked.connect(
                lambda checked=False, label=label, prompt=prompt, include_cleanup=include_cleanup:
                self.prompt_selected.emit(label, prompt, include_cleanup)
            )
            grid.addWidget(button, index // 2, index % 2)
            self._buttons.append(button)
        layout.addLayout(grid)
        layout.addStretch(1)

    def set_prompts_enabled(self, enabled):
        for button in self._buttons:
            button.setEnabled(enabled)


class TypingIndicator(QWidget):
    def __init__(self):
        super().__init__()
        self.setProperty("role", "chat-message-row")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        bubble = QFrame()
        bubble.setProperty("role", "typing-indicator")
        bubble.setMaximumWidth(220)
        bubble_layout = QVBoxLayout(bubble)
        bubble_layout.setContentsMargins(12, 9, 12, 9)
        label = QLabel("Thinking...")
        label.setProperty("role", "caption")
        bubble_layout.addWidget(label)
        layout.addWidget(bubble)
        layout.addStretch(1)


class _SubmitTextEdit(QTextEdit):
    submit_requested = Signal()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter) and not event.modifiers() & Qt.ShiftModifier:
            self.submit_requested.emit()
            event.accept()
            return
        super().keyPressEvent(event)


class ChatInputDock(QFrame):
    submitted = Signal(str)

    def __init__(self):
        super().__init__()
        self.setProperty("role", "chat-input-dock")
        self._input_enabled = False

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        self.editor = _SubmitTextEdit()
        self.editor.setPlaceholderText("Ask about performance, cleanup, startup, display, audio, or layouts...")
        self.editor.setFixedHeight(72)
        self.editor.installEventFilter(self)
        self.editor.textChanged.connect(self._sync_send_button)
        self.editor.submit_requested.connect(self._submit)
        layout.addWidget(self.editor, 1)

        self.send_btn = QPushButton("Send")
        self.send_btn.clicked.connect(self._submit)
        layout.addWidget(self.send_btn)
        self.set_input_enabled(False)

    def eventFilter(self, watched, event):
        if watched is self.editor and event.type() == QEvent.FocusIn:
            self._sync_send_button()
        return super().eventFilter(watched, event)

    def set_input_enabled(self, enabled):
        self._input_enabled = enabled
        self.editor.setEnabled(enabled)
        self._sync_send_button()

    def text(self):
        return self.editor.toPlainText()

    def clear(self):
        self.editor.clear()
        self._sync_send_button()

    def focus_input(self):
        self.editor.setFocus()

    def _sync_send_button(self):
        self.send_btn.setEnabled(self._input_enabled and bool(self.text().strip()))

    def _submit(self):
        text = self.text().strip()
        if not self._input_enabled or not text:
            return
        self.submitted.emit(text)


class ContextDrawer(QFrame):
    refresh_requested = Signal()

    def __init__(self):
        super().__init__()
        self.setProperty("role", "context-drawer")
        self.setFixedWidth(300)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        header = QHBoxLayout()
        title = QLabel("PC Context")
        title.setProperty("role", "heading")
        header.addWidget(title)
        header.addStretch(1)
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.setProperty("variant", "secondary")
        self.refresh_btn.clicked.connect(self.refresh_requested.emit)
        header.addWidget(self.refresh_btn)
        layout.addLayout(header)

        self.status_label = QLabel("Snapshot not loaded")
        self.status_label.setProperty("role", "caption")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        self.rows_layout = QVBoxLayout()
        self.rows_layout.setSpacing(8)
        layout.addLayout(self.rows_layout)
        layout.addStretch(1)

    def set_loading(self):
        self.refresh_btn.setEnabled(False)
        self.status_label.setText("Refreshing snapshot")

    def set_error(self, message):
        self.refresh_btn.setEnabled(True)
        self.status_label.setText(f"Snapshot failed: {message}")

    def set_snapshot(self, timestamp_text, rows):
        self.refresh_btn.setEnabled(True)
        self.status_label.setText(f"Snapshot {timestamp_text}")
        self._clear_rows()
        for name, value in rows:
            row = QHBoxLayout()
            key = QLabel(name)
            key.setProperty("role", "snapshot-key")
            value_label = QLabel(value)
            value_label.setProperty("role", "caption")
            value_label.setWordWrap(True)
            row.addWidget(key)
            row.addStretch(1)
            row.addWidget(value_label, 2)
            self.rows_layout.addLayout(row)

    def _clear_rows(self):
        while self.rows_layout.count():
            item = self.rows_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())

    def _clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())
