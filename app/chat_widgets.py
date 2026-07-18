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
        max_width = 760 if role == "assistant" else 520 if role == "user" else 620
        self.setMaximumWidth(max_width)
        self.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Minimum)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(0)
        self.text_label = QLabel(text)
        self.text_label.setProperty("role", "message-text")
        self.text_label.setProperty("tone", role)
        self.text_label.setTextFormat(Qt.PlainText)
        self.text_label.setWordWrap(True)
        interaction = Qt.NoTextInteraction if role == "user" else Qt.TextSelectableByMouse
        self.text_label.setTextInteractionFlags(interaction)
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
        layout.setContentsMargins(0, 2, 0, 2)

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
        self.setMaximumWidth(620)
        self.setMinimumWidth(440)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)

        content = QHBoxLayout()
        content.setSpacing(12)
        icon = QLabel("✓")
        icon.setProperty("role", "action-icon")
        icon.setAlignment(Qt.AlignCenter)
        content.addWidget(icon, 0, Qt.AlignTop)

        copy = QVBoxLayout()
        copy.setSpacing(5)
        title = QLabel("Suggested action")
        title.setProperty("role", "action-title")
        title.setWordWrap(True)
        copy.addWidget(title)

        desc = QLabel(f"{action.title}\n{action.description}")
        desc.setProperty("role", "action-description")
        desc.setWordWrap(True)
        copy.addWidget(desc)
        content.addLayout(copy, 1)
        layout.addLayout(content)

        target_text = self._target_text(action)
        detail_bits = []
        if target_text:
            detail_bits.append(f"Target: {target_text}")
        detail_bits.append(
            "Confirmation required" if action.requires_confirmation else "Read-only"
        )
        detail_bits.append(f"Risk: {action.risk}")
        self.meta_label = QLabel("  •  ".join(detail_bits))
        self.meta_label.setProperty("role", "action-meta-value")
        self.meta_label.setWordWrap(True)
        layout.addWidget(self.meta_label)

        self.effect_label = QLabel(f"What will happen: {self._expected_result(action)}")
        self.effect_label.setProperty("role", "caption")
        self.effect_label.setWordWrap(True)
        layout.addWidget(self.effect_label)

        self.result_label = QLabel("")
        self.result_label.setProperty("role", "caption")
        self.result_label.setWordWrap(True)
        self.result_label.setVisible(False)
        layout.addWidget(self.result_label)

        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        buttons.addStretch(1)
        self.cancel_btn = QPushButton(action.cancel_label)
        self.cancel_btn.setProperty("variant", "action-secondary")
        self.cancel_btn.clicked.connect(self._cancel)
        self.confirm_btn = QPushButton(action.confirm_label)
        self.confirm_btn.setProperty("variant", "action-confirm")
        self.confirm_btn.clicked.connect(self._confirm)
        buttons.addWidget(self.cancel_btn)
        buttons.addWidget(self.confirm_btn)
        layout.addLayout(buttons)
        self._pending = False

    def _confirm(self):
        # Do not mark Confirmed until the parent actually runs the action.
        self.confirm_btn.setEnabled(False)
        self.cancel_btn.setEnabled(False)
        self.confirm_btn.setText("Running…")
        self._pending = True
        self.confirmed.emit(self._action, self)

    def _cancel(self):
        self.mark_cancelled()

    def mark_confirmed(self):
        self._set_done("Confirmed")

    def mark_cancelled(self):
        self._set_done("Cancelled")

    def mark_failed(self, message="Failed"):
        self._set_done("Failed")
        self.set_result(False, message)

    def set_result(self, success, message):
        prefix = "Result: " if success else "Error: "
        text = f"{prefix}{(message or '').strip()}"
        self.result_label.setText(text)
        self.result_label.setVisible(bool(text.strip()))

    def _set_done(self, text):
        self.confirm_btn.setEnabled(False)
        self.cancel_btn.setEnabled(False)
        self.confirm_btn.setText(text)
        self._pending = False

    def _target_text(self, action):
        payload = action.payload or {}
        candidates = [
            payload.get("device_name"),
            payload.get("device_id"),
            payload.get("process_name"),
            payload.get("pid"),
            payload.get("layout_id"),
            payload.get("name"),
            ", ".join(payload.get("category_keys", []))
            if isinstance(payload.get("category_keys"), list)
            else "",
            payload.get("adapter_name"),
            payload.get("plan_name"),
            payload.get("root"),
            payload.get("host"),
            payload.get("page"),
            payload.get("folder"),
        ]
        return next((str(value) for value in candidates if value), "")

    def _expected_result(self, action):
        if action.kind.startswith("refresh") or action.kind.startswith("check") or action.kind.startswith("scan"):
            return "collect current information and update the app."
        if action.kind in {
            "clean_cleanup_candidates",
            "clean_temp_files",
            "clean_browser_cache",
            "clean_thumbnail_cache",
            "empty_recycle_bin",
        }:
            return "delete only the allowlisted cleanup targets shown for this action."
        if action.kind == "set_display_refresh_rate":
            return "change only the selected display refresh rate."
        if action.kind.startswith("audio_") or action.kind == "set_default_audio_device":
            return "apply the selected audio change to the resolved device or app session."
        if action.kind == "load_saved_layout":
            return "move matching windows and launch missing apps when possible."
        if action.kind == "capture_layout_snapshot":
            return "save the current window layout for later restore."
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
        layout.setContentsMargins(0, 0, 0, 8)
        layout.setSpacing(12)

        title = QLabel("AI Chat")
        title.setProperty("role", "welcome-title")
        layout.addWidget(title)

        note = QLabel(
            "Local diagnostics assistant for performance, cleanup, and startup help."
        )
        note.setProperty("role", "caption")
        note.setWordWrap(True)
        layout.addWidget(note)

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(12)
        for index, action in enumerate(quick_actions):
            if len(action) == 4:
                label, description, prompt, include_cleanup = action
            else:
                label, prompt, include_cleanup = action
                description = ""
            button = QPushButton(label)
            button.setProperty("variant", "welcome-card")
            button.setToolTip(description)
            button.setCursor(Qt.PointingHandCursor)
            button.clicked.connect(
                lambda checked=False, label=label, prompt=prompt, include_cleanup=include_cleanup:
                self.prompt_selected.emit(label, prompt, include_cleanup)
            )
            button.setText(f"{label}\n{description}")
            grid.addWidget(button, index // 4, index % 4)
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
        layout.setContentsMargins(0, 2, 0, 2)

        bubble = QFrame()
        bubble.setProperty("role", "typing-indicator")
        bubble.setMaximumWidth(220)
        bubble_layout = QVBoxLayout(bubble)
        bubble_layout.setContentsMargins(16, 12, 16, 12)
        label = QLabel("Thinking…")
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
    stop_requested = Signal()

    def __init__(self):
        super().__init__()
        self.setProperty("role", "chat-input-dock")
        self._input_enabled = False

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(12)

        self.editor = _SubmitTextEdit()
        self.editor.setPlaceholderText(
            "Ask anything about your PC..."
        )
        self.editor.setFixedHeight(58)
        self.editor.installEventFilter(self)
        self.editor.textChanged.connect(self._sync_send_button)
        self.editor.submit_requested.connect(self._submit)
        layout.addWidget(self.editor, 1)

        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setProperty("variant", "secondary")
        self.stop_btn.setCursor(Qt.PointingHandCursor)
        self.stop_btn.clicked.connect(self.stop_requested.emit)
        self.stop_btn.setVisible(False)
        layout.addWidget(self.stop_btn, 0, Qt.AlignBottom)

        self.send_btn = QPushButton("Send >")
        self.send_btn.setProperty("variant", "chat-send")
        self.send_btn.setCursor(Qt.PointingHandCursor)
        self.send_btn.clicked.connect(self._submit)
        layout.addWidget(self.send_btn, 0, Qt.AlignBottom)
        self.set_input_enabled(False)

    def set_stop_visible(self, visible):
        self.stop_btn.setVisible(bool(visible))
        self.stop_btn.setEnabled(bool(visible))

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
        self.setFixedWidth(320)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        header = QHBoxLayout()
        title = QLabel("PC Context")
        title.setProperty("role", "heading")
        header.addWidget(title)
        header.addStretch(1)
        collapse = QLabel("^")
        collapse.setProperty("role", "caption")
        header.addWidget(collapse)
        layout.addLayout(header)

        rows_card = QFrame()
        rows_card.setProperty("role", "context-rows")
        rows_card_layout = QVBoxLayout(rows_card)
        rows_card_layout.setContentsMargins(12, 10, 12, 10)
        rows_card_layout.setSpacing(0)

        self.rows_layout = QVBoxLayout()
        self.rows_layout.setSpacing(0)
        rows_card_layout.addLayout(self.rows_layout)
        layout.addWidget(rows_card)

        self.refresh_btn = QPushButton("Refresh Context")
        self.refresh_btn.setProperty("variant", "secondary")
        self.refresh_btn.clicked.connect(self.refresh_requested.emit)
        layout.addWidget(self.refresh_btn)

        self.status_label = QLabel("Snapshot not loaded")
        self.status_label.setProperty("role", "caption")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)
        layout.addStretch(1)

    def set_loading(self):
        self.refresh_btn.setEnabled(False)
        self.status_label.setText("Refreshing snapshot")

    def set_error(self, message):
        self.refresh_btn.setEnabled(True)
        self.status_label.setText(f"Snapshot failed: {message}")

    def set_snapshot(self, timestamp_text, rows):
        self.refresh_btn.setEnabled(True)
        self.status_label.setText(f"Last updated: {timestamp_text}")
        self._clear_rows()
        for name, value in rows:
            row_frame = QFrame()
            row_frame.setProperty("role", "context-row")
            row = QHBoxLayout(row_frame)
            row.setContentsMargins(4, 12, 4, 12)
            row.setSpacing(10)
            key = QLabel(name)
            key.setProperty("role", "snapshot-key")
            value_label = QLabel(value)
            value_label.setProperty("role", "caption")
            value_label.setWordWrap(True)
            status = QLabel("")
            status.setProperty("role", "status-dot")
            status.setProperty("state", self._status_state(value))
            status.setFixedSize(10, 10)
            row.addWidget(key, 1)
            row.addStretch(1)
            row.addWidget(value_label, 2)
            row.addWidget(status)
            self.rows_layout.addWidget(row_frame)

    def _status_state(self, value):
        lowered = str(value).lower()
        if any(word in lowered for word in ("unavailable", "failed", "warning")):
            return "danger"
        if "not scanned" in lowered:
            return "warn"
        percentages = [
            int(part.rstrip("%"))
            for part in lowered.split()
            if part.endswith("%") and part.rstrip("%").isdigit()
        ]
        if percentages and max(percentages) >= 85:
            return "danger"
        if percentages and max(percentages) >= 60:
            return "warn"
        return "good"

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
