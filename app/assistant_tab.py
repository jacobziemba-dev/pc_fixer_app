from datetime import datetime

from PySide6.QtCore import QThread, Signal, Qt, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QMessageBox,
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
from app.chat_widgets import (
    ActionCard,
    ChatInputDock,
    ChatMessageRow,
    ContextDrawer,
    TypingIndicator,
    WelcomeState,
)


DISPLAY_REVIEW_PROMPT = "Review my display setup and mention anything unusual about monitor modes."
AUDIO_REVIEW_PROMPT = "Review my audio devices and app sessions at a high level."
LAYOUT_REVIEW_PROMPT = "Review my window layouts and suggest what I should refresh or check."
NETWORK_REVIEW_PROMPT = "Diagnose my current network status and mention any likely connection issues."

QUICK_ACTIONS = [
    ("Health", "Check overall PC health and stats.", HEALTH_CHECK_PROMPT, False),
    ("Slow PC", "Find what's slowing your PC down.", SLOW_PC_PROMPT, False),
    ("Cleanup", "Free up space and remove junk.", CLEANUP_REVIEW_PROMPT, True),
    ("Network", "Diagnose network issues.", NETWORK_REVIEW_PROMPT, False),
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
        self._assistant_visible_buffer = ""
        self._stream_filter_buffer = ""
        self._stream_filter_in_skill_block = False
        self._history = []
        self._pending_user_text = ""
        self._current_assistant_bubble = None
        self._typing_indicator = None
        self._current_snapshot = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self.stop_action = None

        body_layout = QHBoxLayout()
        body_layout.setSpacing(0)

        thread_shell = QFrame()
        thread_shell.setProperty("role", "chat-thread")
        thread_layout = QVBoxLayout(thread_shell)
        thread_layout.setContentsMargins(0, 0, 0, 0)
        thread_layout.setSpacing(0)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setProperty("role", "chat-scroll")
        self.feed = QWidget()
        self.feed_layout = QVBoxLayout(self.feed)
        self.feed_layout.setContentsMargins(18, 18, 18, 14)
        self.feed_layout.setSpacing(12)

        self.welcome_state = WelcomeState(QUICK_ACTIONS)
        self.welcome_state.prompt_selected.connect(self._start_inference)
        self.feed_layout.addWidget(self.welcome_state)

        self.missing_model_panel = self._build_missing_model_panel()
        self.feed_layout.addWidget(self.missing_model_panel)

        self.messages_widget = QWidget()
        self.messages_layout = QVBoxLayout(self.messages_widget)
        self.messages_layout.setContentsMargins(0, 0, 0, 0)
        self.messages_layout.setSpacing(12)
        self.feed_layout.addWidget(self.messages_widget)
        self.feed_layout.addStretch(1)
        self.scroll.setWidget(self.feed)
        thread_layout.addWidget(self.scroll, 1)

        self.input_dock = ChatInputDock()
        self.input_dock.submitted.connect(self._send_message_text)
        thread_layout.addWidget(self.input_dock)

        body_layout.addWidget(thread_shell, 1)
        self.context_drawer = ContextDrawer()
        self.context_drawer.refresh_requested.connect(lambda: self._refresh_snapshot(False))
        body_layout.addWidget(self.context_drawer)
        outer.addLayout(body_layout, 1)

        self._refresh_snapshot(False)
        if not model_exists():
            self._show_missing_model()
        else:
            self._set_status("Waiting to load model")
            self.missing_model_panel.setVisible(False)
            self._update_empty_state()

    def showEvent(self, event):
        super().showEvent(event)
        if not self._load_started and model_exists():
            self._start_model_load()

    def _build_missing_model_panel(self):
        panel = QFrame()
        panel.setProperty("role", "missing-model")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)
        title = QLabel("Model not found")
        title.setProperty("role", "action-title")
        layout.addWidget(title)
        self.missing_model_label = QLabel("")
        self.missing_model_label.setProperty("role", "caption")
        self.missing_model_label.setWordWrap(True)
        layout.addWidget(self.missing_model_label)
        button_row = QHBoxLayout()
        button_row.addStretch(1)
        recheck_btn = QPushButton("Recheck Model")
        recheck_btn.setProperty("variant", "secondary")
        recheck_btn.clicked.connect(self._recheck_model)
        button_row.addWidget(recheck_btn)
        layout.addLayout(button_row)
        return panel

    def _set_status(self, text):
        window = self.window()
        if hasattr(window, "global_status_chip"):
            window.global_status_chip.setText(text)

    def _set_input_enabled(self, enabled):
        self.input_dock.set_input_enabled(enabled)
        self.welcome_state.set_prompts_enabled(enabled)

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
        self._update_empty_state()
        self._set_status("Ready")
        self._set_input_enabled(True)
        self.input_dock.focus_input()

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
        self._update_empty_state()
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

    def _toggle_context_drawer(self, checked):
        self.context_drawer.setVisible(checked)

    def _refresh_snapshot(self, include_cleanup):
        if self._worker_is_running(self._snapshot_worker):
            return
        self.context_drawer.set_loading()
        self._snapshot_worker = SnapshotWorker(include_cleanup=include_cleanup)
        self._snapshot_worker.finished_with_snapshot.connect(self._on_snapshot_ready)
        self._snapshot_worker.error.connect(self._on_snapshot_error)
        self._snapshot_worker.finished.connect(self._clear_snapshot_worker)
        self._snapshot_worker.finished.connect(self._snapshot_worker.deleteLater)
        self._snapshot_worker.start()

    def _clear_snapshot_worker(self):
        self._snapshot_worker = None

    def _on_snapshot_ready(self, snapshot):
        self._current_snapshot = snapshot
        self._render_snapshot(snapshot)

    def _on_snapshot_error(self, message):
        self.context_drawer.set_error(message)
        self._add_message("error", f"Snapshot refresh failed: {message}")

    def _render_snapshot(self, snapshot):
        self.context_drawer.set_snapshot(
            snapshot.timestamp.strftime("%H:%M:%S"),
            snapshot_summary_rows(snapshot),
        )

    def _clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())

    def _update_empty_state(self):
        has_messages = self.messages_layout.count() > 0
        missing_model = self.missing_model_panel.isVisible()
        self.messages_widget.setVisible(has_messages)
        self.welcome_state.setVisible(not has_messages and not missing_model)

    def _remove_typing_indicator(self):
        if not self._typing_indicator:
            return
        self.messages_layout.removeWidget(self._typing_indicator)
        self._typing_indicator.deleteLater()
        self._typing_indicator = None
        self._update_empty_state()

    def _ensure_assistant_bubble(self):
        if self._current_assistant_bubble:
            return self._current_assistant_bubble
        self._remove_typing_indicator()
        self._current_assistant_bubble = self._add_message("assistant", "")
        return self._current_assistant_bubble

    def _add_message(self, role, text=""):
        row = ChatMessageRow(role, text)
        self.messages_layout.addWidget(row)
        self._update_empty_state()
        QTimer.singleShot(0, self._scroll_to_bottom)
        return row.bubble

    def _add_action_cards(self, actions):
        for action in actions:
            card = ActionCard(action)
            card.confirmed.connect(self._run_action)
            self.messages_layout.addWidget(card, 0, Qt.AlignLeft)
            self._update_empty_state()
        if actions:
            QTimer.singleShot(0, self._scroll_to_bottom)

    def _scroll_to_bottom(self):
        bar = self.scroll.verticalScrollBar()
        bar.setValue(bar.maximum())

    def _clear_chat(self):
        self._clear_layout(self.messages_layout)
        self._history = []
        self._assistant_buffer = ""
        self._assistant_visible_buffer = ""
        self._stream_filter_buffer = ""
        self._stream_filter_in_skill_block = False
        self._pending_user_text = ""
        self._current_assistant_bubble = None
        self._typing_indicator = None
        self._update_empty_state()

    def _send_message(self):
        user_text = self.input_dock.text().strip()
        if not user_text:
            return
        self.input_dock.clear()
        self._start_inference(user_text, user_text, self._should_include_cleanup(user_text))

    def _send_message_text(self, user_text):
        self.input_dock.clear()
        self._start_inference(user_text, user_text, self._should_include_cleanup(user_text))

    def _should_include_cleanup(self, text):
        lowered = text.lower()
        return any(word in lowered for word in ("clean", "cleanup", "junk", "cache", "delete temp", "free space"))

    def _start_inference(self, display_text, prompt_text=None, include_cleanup=False):
        if not self._model_ready or self._worker_is_running(self._infer_worker):
            return
        self._add_message("user", display_text)
        self._assistant_buffer = ""
        self._assistant_visible_buffer = ""
        self._stream_filter_buffer = ""
        self._stream_filter_in_skill_block = False
        self._pending_user_text = display_text
        self._current_assistant_bubble = None
        self._typing_indicator = TypingIndicator()
        self.messages_layout.addWidget(self._typing_indicator)
        self._set_input_enabled(False)
        if self.stop_action:
            self.stop_action.setVisible(True)
            self.stop_action.setEnabled(True)
        self._set_status("Thinking")
        self.context_drawer.set_loading()

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
        visible_text = self._filter_streaming_skill_json(token)
        if visible_text:
            self._assistant_visible_buffer += visible_text
            self._ensure_assistant_bubble().append_text(visible_text)
            QTimer.singleShot(0, self._scroll_to_bottom)

    def _filter_streaming_skill_json(self, token):
        self._stream_filter_buffer += token
        output = []
        while self._stream_filter_buffer:
            if self._stream_filter_in_skill_block:
                end = self._stream_filter_buffer.find("```")
                if end < 0:
                    keep = min(len(self._stream_filter_buffer), 2)
                    self._stream_filter_buffer = self._stream_filter_buffer[-keep:] if keep else ""
                    break
                self._stream_filter_buffer = self._stream_filter_buffer[end + 3:]
                self._stream_filter_in_skill_block = False
                continue

            start = self._stream_filter_buffer.find("```")
            if start < 0:
                safe_length = max(0, len(self._stream_filter_buffer) - 2)
                if safe_length:
                    output.append(self._stream_filter_buffer[:safe_length])
                    self._stream_filter_buffer = self._stream_filter_buffer[safe_length:]
                break

            if start:
                output.append(self._stream_filter_buffer[:start])
                self._stream_filter_buffer = self._stream_filter_buffer[start:]

            lowered = self._stream_filter_buffer.lower()
            if lowered.startswith("```json") or lowered.startswith("```\n{") or lowered.startswith("``` {"):
                newline = self._stream_filter_buffer.find("\n")
                if newline < 0:
                    break
                self._stream_filter_buffer = self._stream_filter_buffer[newline + 1:]
                self._stream_filter_in_skill_block = True
                continue

            if len(self._stream_filter_buffer) < 8:
                break
            output.append("```")
            self._stream_filter_buffer = self._stream_filter_buffer[3:]

        return "".join(output)

    def _flush_stream_filter(self):
        if self._stream_filter_in_skill_block:
            self._stream_filter_buffer = ""
            self._stream_filter_in_skill_block = False
            return ""
        text = self._stream_filter_buffer
        self._stream_filter_buffer = ""
        return text

    def _on_assistant_text_ready(self, text):
        tail = self._flush_stream_filter()
        cleaned = text.strip() or self._assistant_visible_buffer.strip() or tail.strip() or "I found an app action that can help."
        self._assistant_buffer = cleaned
        self._assistant_visible_buffer = cleaned
        self._ensure_assistant_bubble().set_text(cleaned)
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
        self._ensure_assistant_bubble().append_text("\n[Stopped]")
        self._finish_inference_ui("Ready")

    def _on_inference_error(self, message):
        if self._current_assistant_bubble and self._assistant_buffer:
            self._current_assistant_bubble.append_text(f"\n[Error: {message}]")
        else:
            self._remove_typing_indicator()
            self._add_message("error", message)
        self._finish_inference_ui("Error")

    def _finish_inference_ui(self, status):
        self._pending_user_text = ""
        if self.stop_action:
            self.stop_action.setEnabled(False)
            self.stop_action.setVisible(False)
        self._set_status(status)
        self._set_input_enabled(self._model_ready)
        if self._model_ready:
            self.input_dock.focus_input()

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
