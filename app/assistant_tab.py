from datetime import datetime

from PySide6.QtCore import QThread, Signal, Qt, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QScrollArea, QFrame, QToolButton, QSizePolicy, QMessageBox,
)

from app.ai_engine import (
    AIEngineError,
    CLEANUP_REVIEW_PROMPT,
    DEFAULT_SYSTEM_PROMPT,
    DISK_SPACE_PROMPT,
    EmbeddedAI,
    HEALTH_CHECK_PROMPT,
    SLOW_PC_PROMPT,
    STARTUP_REVIEW_PROMPT,
    build_skill_catalog,
    build_system_snapshot,
    compose_user_prompt,
    missing_model_message,
    model_exists,
    render_snapshot_context,
    resolve_model_path,
)
from app.assistant_core import (
    AssistantAction,
    AssistantActionResult,
    AssistantTurn,
    TAB_ACTION_KINDS,
    collect_assistant_snapshot,
    merge_action_lists,
    execute_assistant_action,
    propose_actions,
    skill_requests_to_actions,
    snapshot_summary_rows,
    strip_skill_requests,
)


DISPLAY_REVIEW_PROMPT = "Review my display setup and mention anything unusual about monitor modes."
AUDIO_REVIEW_PROMPT = "Review my audio devices and app sessions at a high level."
LAYOUT_REVIEW_PROMPT = "Review my window layouts and suggest what I should refresh or check."

QUICK_ACTIONS = [
    ("Health", HEALTH_CHECK_PROMPT, False),
    ("Slow PC", SLOW_PC_PROMPT, False),
    ("Disk", DISK_SPACE_PROMPT, False),
    ("Startup", STARTUP_REVIEW_PROMPT, False),
    ("Cleanup", CLEANUP_REVIEW_PROMPT, True),
    ("Display", DISPLAY_REVIEW_PROMPT, False),
    ("Audio", AUDIO_REVIEW_PROMPT, False),
    ("Layouts", LAYOUT_REVIEW_PROMPT, False),
]


class ModelLoadWorker(QThread):
    finished_ok = Signal()
    error = Signal(str)

    def __init__(self, engine):
        super().__init__()
        self._engine = engine

    def run(self):
        try:
            self._engine.load()
            self.finished_ok.emit()
        except AIEngineError as exc:
            self.error.emit(str(exc))
        except Exception as exc:
            self.error.emit(f"Failed to load model: {exc}")


class SnapshotWorker(QThread):
    finished_with_snapshot = Signal(object)
    error = Signal(str)

    def __init__(self, include_cleanup=False):
        super().__init__()
        self._include_cleanup = include_cleanup

    def run(self):
        try:
            self.finished_with_snapshot.emit(
                collect_assistant_snapshot(include_cleanup=self._include_cleanup)
            )
        except Exception as exc:
            self.error.emit(str(exc))


class InferenceWorker(QThread):
    token_received = Signal(str)
    snapshot_ready = Signal(object)
    actions_ready = Signal(list)
    assistant_text_ready = Signal(str)
    skill_messages_ready = Signal(list)
    inference_complete = Signal()
    cancelled = Signal()
    error = Signal(str)

    def __init__(
        self,
        engine,
        user_prompt,
        display_text,
        history=None,
        include_cleanup=False,
        system_prompt=DEFAULT_SYSTEM_PROMPT,
    ):
        super().__init__()
        self._engine = engine
        self._user_prompt = user_prompt
        self._display_text = display_text
        self._history = history or []
        self._include_cleanup = include_cleanup
        self._system_prompt = system_prompt
        self._stop_requested = False

    def request_stop(self):
        self._stop_requested = True

    def run(self):
        try:
            snapshot = build_system_snapshot(include_cleanup=self._include_cleanup)
            self.snapshot_ready.emit(snapshot)
            context = render_snapshot_context(snapshot)
            prompt = compose_user_prompt(
                self._user_prompt,
                context,
                self._history,
                skill_catalog=build_skill_catalog(),
            )
            assistant_text = ""
            for token in self._engine.stream_query(self._system_prompt, prompt):
                if self._stop_requested:
                    self.cancelled.emit()
                    return
                assistant_text += token
                self.token_received.emit(token)
            cleaned_answer = strip_skill_requests(assistant_text)
            self.assistant_text_ready.emit(cleaned_answer)
            parsed_actions, parse_messages = skill_requests_to_actions(assistant_text, snapshot)
            fallback_actions = propose_actions(self._display_text, snapshot)
            actions = merge_action_lists(parsed_actions, fallback_actions)
            if parse_messages:
                self.skill_messages_ready.emit(parse_messages)
            self.actions_ready.emit(actions)
            self.inference_complete.emit()
        except AIEngineError as exc:
            self.error.emit(str(exc))
        except Exception as exc:
            self.error.emit(f"Inference failed: {exc}")


class ActionWorker(QThread):
    finished_with_result = Signal(object, object)

    def __init__(self, action, snapshot=None):
        super().__init__()
        self._action = action
        self._snapshot = snapshot

    def run(self):
        try:
            result, snapshot = self._run_action()
        except Exception as exc:
            result = AssistantActionResult(False, f"Action failed: {exc}")
            snapshot = self._snapshot
        self.finished_with_result.emit(result, snapshot)

    def _run_action(self):
        return execute_assistant_action(self._action, self._snapshot)


class MessageBubble(QFrame):
    def __init__(self, role, text=""):
        super().__init__()
        self.setProperty("role", f"message-{role}")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
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


class ActionCard(QFrame):
    confirmed = Signal(object, object)

    def __init__(self, action):
        super().__init__()
        self._action = action
        self.setProperty("role", "action-card")
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


class AssistantTab(QWidget):
    action_requested = Signal(str, dict)

    def __init__(self):
        super().__init__()
        self._engine = EmbeddedAI()
        self._load_worker = None
        self._infer_worker = None
        self._snapshot_worker = None
        self._action_worker = None
        self._model_ready = False
        self._load_started = False
        self._assistant_buffer = ""
        self._history = []
        self._pending_user_text = ""
        self._current_assistant_bubble = None
        self._current_snapshot = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 14, 14, 14)
        outer.setSpacing(10)

        header_layout = QHBoxLayout()
        title = QLabel("Assistant")
        title.setProperty("role", "heading")
        header_layout.addWidget(title)
        header_layout.addStretch(1)

        self.status_chip = QLabel("Checking model")
        self.status_chip.setProperty("role", "status-chip")
        header_layout.addWidget(self.status_chip)

        self.snapshot_chip = QLabel("Snapshot not loaded")
        self.snapshot_chip.setProperty("role", "status-chip")
        header_layout.addWidget(self.snapshot_chip)

        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setProperty("variant", "secondary")
        self.stop_btn.clicked.connect(self._stop_inference)
        self.stop_btn.setVisible(False)
        header_layout.addWidget(self.stop_btn)

        self.clear_btn = QPushButton("Clear")
        self.clear_btn.setProperty("variant", "secondary")
        self.clear_btn.clicked.connect(self._clear_chat)
        header_layout.addWidget(self.clear_btn)

        self.recheck_btn = QPushButton("Recheck Model")
        self.recheck_btn.setProperty("variant", "secondary")
        self.recheck_btn.clicked.connect(self._recheck_model)
        header_layout.addWidget(self.recheck_btn)
        outer.addLayout(header_layout)

        subtitle = QLabel(
            "Local diagnostics assistant. It can suggest safe app actions, "
            "but anything that changes your PC requires confirmation."
        )
        subtitle.setProperty("role", "caption")
        subtitle.setWordWrap(True)
        outer.addWidget(subtitle)

        self.missing_model_panel = self._build_missing_model_panel()
        outer.addWidget(self.missing_model_panel)

        self.snapshot_toggle = QToolButton()
        self.snapshot_toggle.setText("PC Snapshot")
        self.snapshot_toggle.setCheckable(True)
        self.snapshot_toggle.setChecked(True)
        self.snapshot_toggle.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.snapshot_toggle.setArrowType(Qt.DownArrow)
        self.snapshot_toggle.toggled.connect(self._toggle_snapshot_panel)
        outer.addWidget(self.snapshot_toggle)

        self.snapshot_panel = QFrame()
        self.snapshot_panel.setProperty("role", "snapshot-panel")
        snapshot_layout = QVBoxLayout(self.snapshot_panel)
        snapshot_layout.setContentsMargins(12, 10, 12, 10)
        self.snapshot_rows_layout = QVBoxLayout()
        snapshot_layout.addLayout(self.snapshot_rows_layout)
        refresh_snapshot_layout = QHBoxLayout()
        refresh_snapshot_layout.addStretch(1)
        self.refresh_snapshot_btn = QPushButton("Refresh Snapshot")
        self.refresh_snapshot_btn.setProperty("variant", "secondary")
        self.refresh_snapshot_btn.clicked.connect(lambda: self._refresh_snapshot(False))
        refresh_snapshot_layout.addWidget(self.refresh_snapshot_btn)
        snapshot_layout.addLayout(refresh_snapshot_layout)
        outer.addWidget(self.snapshot_panel)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setProperty("role", "chat-scroll")
        self.feed = QWidget()
        self.feed_layout = QVBoxLayout(self.feed)
        self.feed_layout.setContentsMargins(8, 8, 8, 8)
        self.feed_layout.setSpacing(8)
        self.feed_layout.addStretch(1)
        self.scroll.setWidget(self.feed)
        outer.addWidget(self.scroll, 1)

        quick_layout = QHBoxLayout()
        quick_layout.setSpacing(6)
        self.quick_buttons = []
        for label, prompt, include_cleanup in QUICK_ACTIONS:
            button = QPushButton(label)
            button.setProperty("variant", "chip")
            button.clicked.connect(
                lambda checked=False, label=label, prompt=prompt, include_cleanup=include_cleanup:
                    self._start_inference(label, prompt, include_cleanup)
            )
            button.setEnabled(False)
            quick_layout.addWidget(button)
            self.quick_buttons.append(button)
        quick_layout.addStretch(1)
        outer.addLayout(quick_layout)

        input_layout = QHBoxLayout()
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Ask about performance, cleanup, startup, display, audio, or layouts...")
        self.input_field.returnPressed.connect(self._send_message)
        self.input_field.setEnabled(False)
        input_layout.addWidget(self.input_field)
        self.send_btn = QPushButton("Send")
        self.send_btn.clicked.connect(self._send_message)
        self.send_btn.setEnabled(False)
        input_layout.addWidget(self.send_btn)
        outer.addLayout(input_layout)

        self._refresh_snapshot(False)
        if not model_exists():
            self._show_missing_model()
        else:
            self._set_status("Waiting to load model")
            self.missing_model_panel.setVisible(False)

    def showEvent(self, event):
        super().showEvent(event)
        if not self._load_started and model_exists():
            self._start_model_load()

    def _build_missing_model_panel(self):
        panel = QFrame()
        panel.setProperty("role", "missing-model")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 10, 12, 10)
        title = QLabel("Model not found")
        title.setProperty("role", "action-title")
        layout.addWidget(title)
        self.missing_model_label = QLabel("")
        self.missing_model_label.setProperty("role", "caption")
        self.missing_model_label.setWordWrap(True)
        layout.addWidget(self.missing_model_label)
        return panel

    def _set_status(self, text):
        self.status_chip.setText(text)

    def _set_input_enabled(self, enabled):
        self.input_field.setEnabled(enabled)
        for button in self.quick_buttons:
            button.setEnabled(enabled)
        self.send_btn.setEnabled(enabled)

    def _worker_is_running(self, worker):
        if worker is None:
            return False
        try:
            return worker.isRunning()
        except RuntimeError:
            return False

    def _start_model_load(self):
        if self._worker_is_running(self._load_worker):
            return
        self._load_started = True
        self._set_status("Loading model")
        self._set_input_enabled(False)
        self._load_worker = ModelLoadWorker(self._engine)
        self._load_worker.finished_ok.connect(self._on_model_loaded)
        self._load_worker.error.connect(self._on_model_error)
        self._load_worker.finished.connect(self._clear_load_worker)
        self._load_worker.finished.connect(self._load_worker.deleteLater)
        self._load_worker.start()

    def _clear_load_worker(self):
        self._load_worker = None

    def _clear_infer_worker(self):
        self._infer_worker = None

    def _on_model_loaded(self):
        self._model_ready = True
        self.missing_model_panel.setVisible(False)
        self._set_status("Ready")
        self._set_input_enabled(True)
        self.input_field.setFocus()

    def _on_model_error(self, message):
        self._model_ready = False
        self._set_status("Model error")
        self._set_input_enabled(False)
        self._add_message("error", message)

    def _show_missing_model(self):
        self._model_ready = False
        message = missing_model_message(resolve_model_path())
        self.missing_model_label.setText(message)
        self.missing_model_panel.setVisible(True)
        self._set_status("Model missing")
        self._set_input_enabled(False)

    def _recheck_model(self):
        if self._worker_is_running(self._load_worker) or self._worker_is_running(self._infer_worker):
            return
        if not model_exists():
            self._load_started = False
            self._show_missing_model()
            return
        self.missing_model_panel.setVisible(False)
        if self._engine.is_loaded:
            self._on_model_loaded()
            return
        self._start_model_load()

    def _toggle_snapshot_panel(self, checked):
        self.snapshot_panel.setVisible(checked)
        self.snapshot_toggle.setArrowType(Qt.DownArrow if checked else Qt.RightArrow)

    def _refresh_snapshot(self, include_cleanup):
        if self._worker_is_running(self._snapshot_worker):
            return
        self.refresh_snapshot_btn.setEnabled(False)
        self.snapshot_chip.setText("Refreshing snapshot")
        self._snapshot_worker = SnapshotWorker(include_cleanup=include_cleanup)
        self._snapshot_worker.finished_with_snapshot.connect(self._on_snapshot_ready)
        self._snapshot_worker.error.connect(self._on_snapshot_error)
        self._snapshot_worker.finished.connect(self._clear_snapshot_worker)
        self._snapshot_worker.finished.connect(self._snapshot_worker.deleteLater)
        self._snapshot_worker.start()

    def _clear_snapshot_worker(self):
        self._snapshot_worker = None
        self.refresh_snapshot_btn.setEnabled(True)

    def _on_snapshot_ready(self, snapshot):
        self._current_snapshot = snapshot
        self._render_snapshot(snapshot)

    def _on_snapshot_error(self, message):
        self.snapshot_chip.setText("Snapshot failed")
        self._add_message("error", f"Snapshot refresh failed: {message}")

    def _render_snapshot(self, snapshot):
        self._clear_layout(self.snapshot_rows_layout)
        for name, value in snapshot_summary_rows(snapshot):
            row = QHBoxLayout()
            key = QLabel(name)
            key.setProperty("role", "snapshot-key")
            value_label = QLabel(value)
            value_label.setProperty("role", "caption")
            value_label.setWordWrap(True)
            row.addWidget(key)
            row.addStretch(1)
            row.addWidget(value_label, 2)
            self.snapshot_rows_layout.addLayout(row)
        self.snapshot_chip.setText(f"Snapshot {snapshot.timestamp.strftime('%H:%M:%S')}")

    def _clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())

    def _add_message(self, role, text=""):
        bubble = MessageBubble(role, text)
        self.feed_layout.insertWidget(self.feed_layout.count() - 1, bubble)
        QTimer.singleShot(0, self._scroll_to_bottom)
        return bubble

    def _add_action_cards(self, actions):
        for action in actions:
            card = ActionCard(action)
            card.confirmed.connect(self._run_action)
            self.feed_layout.insertWidget(self.feed_layout.count() - 1, card)
        if actions:
            QTimer.singleShot(0, self._scroll_to_bottom)

    def _scroll_to_bottom(self):
        bar = self.scroll.verticalScrollBar()
        bar.setValue(bar.maximum())

    def _clear_chat(self):
        while self.feed_layout.count() > 1:
            item = self.feed_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._history = []
        self._assistant_buffer = ""
        self._pending_user_text = ""
        self._current_assistant_bubble = None

    def _send_message(self):
        user_text = self.input_field.text().strip()
        if not user_text:
            return
        self.input_field.clear()
        self._start_inference(user_text, user_text, self._should_include_cleanup(user_text))

    def _should_include_cleanup(self, text):
        lowered = text.lower()
        return any(word in lowered for word in ("clean", "cleanup", "junk", "cache", "delete temp", "free space"))

    def _start_inference(self, display_text, prompt_text=None, include_cleanup=False):
        if not self._model_ready or self._worker_is_running(self._infer_worker):
            return
        self._add_message("user", display_text)
        self._assistant_buffer = ""
        self._pending_user_text = display_text
        self._current_assistant_bubble = self._add_message("assistant", "")
        self._set_input_enabled(False)
        self.stop_btn.setVisible(True)
        self._set_status("Thinking")
        self.snapshot_chip.setText("Refreshing snapshot")

        self._infer_worker = InferenceWorker(
            self._engine,
            prompt_text or display_text,
            display_text,
            history=list(self._history),
            include_cleanup=include_cleanup,
        )
        self._infer_worker.token_received.connect(self._on_token_received)
        self._infer_worker.snapshot_ready.connect(self._on_snapshot_ready)
        self._infer_worker.assistant_text_ready.connect(self._on_assistant_text_ready)
        self._infer_worker.skill_messages_ready.connect(self._on_skill_messages_ready)
        self._infer_worker.actions_ready.connect(self._add_action_cards)
        self._infer_worker.inference_complete.connect(self._on_inference_finished)
        self._infer_worker.cancelled.connect(self._on_inference_cancelled)
        self._infer_worker.error.connect(self._on_inference_error)
        self._infer_worker.finished.connect(self._clear_infer_worker)
        self._infer_worker.finished.connect(self._infer_worker.deleteLater)
        self._infer_worker.start()

    def _stop_inference(self):
        if self._infer_worker and self._infer_worker.isRunning():
            self._infer_worker.request_stop()
            self._set_status("Stopping")

    def _on_token_received(self, token):
        self._assistant_buffer += token
        if self._current_assistant_bubble:
            self._current_assistant_bubble.append_text(token)
        QTimer.singleShot(0, self._scroll_to_bottom)

    def _on_assistant_text_ready(self, text):
        cleaned = text.strip() or "I found an app action that can help."
        self._assistant_buffer = cleaned
        if self._current_assistant_bubble:
            self._current_assistant_bubble.set_text(cleaned)
        QTimer.singleShot(0, self._scroll_to_bottom)

    def _on_skill_messages_ready(self, messages):
        for message in messages[:4]:
            self._add_message("system", f"Skill request skipped: {message}")

    def _on_inference_finished(self):
        answer = self._assistant_buffer.strip()
        if self._pending_user_text and answer:
            self._history.append(AssistantTurn(
                user=self._pending_user_text,
                assistant=answer,
                timestamp=datetime.now(),
            ))
            self._history = self._history[-8:]
        self._finish_inference_ui("Ready")

    def _on_inference_cancelled(self):
        if self._current_assistant_bubble:
            self._current_assistant_bubble.append_text("\n[Stopped]")
        self._finish_inference_ui("Ready")

    def _on_inference_error(self, message):
        if self._current_assistant_bubble and self._assistant_buffer:
            self._current_assistant_bubble.append_text(f"\n[Error: {message}]")
        else:
            self._add_message("error", message)
        self._finish_inference_ui("Error")

    def _finish_inference_ui(self, status):
        self._pending_user_text = ""
        self.stop_btn.setVisible(False)
        self._set_status(status)
        self._set_input_enabled(self._model_ready)
        if self._model_ready:
            self.input_field.setFocus()

    def _run_action(self, action, card):
        if action.kind in TAB_ACTION_KINDS:
            self.action_requested.emit(action.kind, action.payload)
            self._add_message("system", f"Requested: {action.title}.")
            return

        if action.requires_confirmation:
            reply = QMessageBox.question(
                self,
                "Confirm Assistant Action",
                f"{action.description}\n\nContinue?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                self._add_message("system", "Assistant action cancelled.")
                return

        if self._worker_is_running(self._action_worker):
            self._add_message("system", "Another assistant action is still running.")
            return

        self._set_status("Running action")
        self._action_worker = ActionWorker(action, self._current_snapshot)
        self._action_worker.finished_with_result.connect(self._on_action_finished)
        self._action_worker.finished.connect(self._clear_action_worker)
        self._action_worker.finished.connect(self._action_worker.deleteLater)
        self._action_worker.start()

    def _clear_action_worker(self):
        self._action_worker = None

    def _on_action_finished(self, result, snapshot):
        if snapshot:
            self._on_snapshot_ready(snapshot)
        role = "system" if result.success else "error"
        message = result.message
        if result.errors:
            message += "\n" + "\n".join(f"- {error}" for error in result.errors[:6])
        self._add_message(role, message)
        if snapshot and result.success:
            follow_up_actions = propose_actions("cleanup", snapshot)
            cleanup_actions = [
                action for action in follow_up_actions
                if action.kind == "clean_cleanup_candidates"
            ]
            self._add_action_cards(cleanup_actions)
        self._set_status("Ready" if self._model_ready else "Model missing")
