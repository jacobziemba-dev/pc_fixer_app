from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QLineEdit,
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
    build_system_context,
    compose_user_prompt,
    missing_model_message,
    model_exists,
    resolve_model_path,
)


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


QUICK_ACTIONS = [
    ("How's my PC?", HEALTH_CHECK_PROMPT, False),
    ("Why is it slow?", SLOW_PC_PROMPT, False),
    ("Check disk space", DISK_SPACE_PROMPT, False),
    ("Startup review", STARTUP_REVIEW_PROMPT, False),
    ("Safe cleanup", CLEANUP_REVIEW_PROMPT, True),
]


class InferenceWorker(QThread):
    token_received = Signal(str)
    inference_complete = Signal()
    error = Signal(str)

    def __init__(
        self,
        engine,
        user_prompt,
        history=None,
        include_cleanup=False,
        system_prompt=DEFAULT_SYSTEM_PROMPT,
    ):
        super().__init__()
        self._engine = engine
        self._user_prompt = user_prompt
        self._history = history or []
        self._include_cleanup = include_cleanup
        self._system_prompt = system_prompt

    def run(self):
        try:
            context = build_system_context(include_cleanup=self._include_cleanup)
            prompt = compose_user_prompt(self._user_prompt, context, self._history)
            for token in self._engine.stream_query(
                self._system_prompt,
                prompt,
            ):
                self.token_received.emit(token)
            self.inference_complete.emit()
        except AIEngineError as exc:
            self.error.emit(str(exc))
        except Exception as exc:
            self.error.emit(f"Inference failed: {exc}")


class AssistantTab(QWidget):
    def __init__(self):
        super().__init__()
        self._engine = EmbeddedAI()
        self._load_worker = None
        self._infer_worker = None
        self._model_ready = False
        self._load_started = False
        self._assistant_buffer = ""
        self._history = []
        self._pending_user_text = ""

        outer = QVBoxLayout(self)

        header_layout = QHBoxLayout()
        title = QLabel("Assistant")
        title.setProperty("role", "heading")
        header_layout.addWidget(title)
        header_layout.addStretch(1)
        self.status_label = QLabel("Checking model...")
        self.status_label.setProperty("role", "caption")
        header_layout.addWidget(self.status_label)
        self.recheck_btn = QPushButton("Recheck Model")
        self.recheck_btn.setProperty("variant", "secondary")
        self.recheck_btn.clicked.connect(self._recheck_model)
        header_layout.addWidget(self.recheck_btn)
        outer.addLayout(header_layout)

        subtitle = QLabel(
            "Local AI assistant powered by an on-device model. "
            "Conversations stay on your PC and do not require internet."
        )
        subtitle.setProperty("role", "caption")
        subtitle.setWordWrap(True)
        outer.addWidget(subtitle)

        self.transcript = QTextEdit()
        self.transcript.setReadOnly(True)
        self.transcript.setAcceptRichText(False)
        self.transcript.setPlaceholderText("Ask a question about your PC...")
        outer.addWidget(self.transcript)

        quick_layout = QHBoxLayout()
        self.quick_buttons = []
        for label, prompt, include_cleanup in QUICK_ACTIONS:
            button = QPushButton(label)
            button.setProperty("variant", "secondary")
            button.clicked.connect(
                lambda checked=False, label=label, prompt=prompt, include_cleanup=include_cleanup:
                    self._start_inference(label, prompt, include_cleanup)
            )
            button.setEnabled(False)
            quick_layout.addWidget(button)
            self.quick_buttons.append(button)
        quick_layout.addStretch(1)
        self.clear_btn = QPushButton("Clear")
        self.clear_btn.setProperty("variant", "secondary")
        self.clear_btn.clicked.connect(self._clear_chat)
        quick_layout.addWidget(self.clear_btn)
        outer.addLayout(quick_layout)

        input_layout = QHBoxLayout()
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Type a message and press Enter...")
        self.input_field.returnPressed.connect(self._send_message)
        self.input_field.setEnabled(False)
        input_layout.addWidget(self.input_field)

        self.send_btn = QPushButton("Send")
        self.send_btn.clicked.connect(self._send_message)
        self.send_btn.setEnabled(False)
        input_layout.addWidget(self.send_btn)
        outer.addLayout(input_layout)

        if not model_exists():
            self._set_status(missing_model_message(resolve_model_path()))
        else:
            self._set_status("Waiting to load model...")

    def showEvent(self, event):
        super().showEvent(event)
        if not self._load_started and model_exists():
            self._start_model_load()

    def _set_status(self, text):
        self.status_label.setText(text)

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
        self._set_status("Loading model...")
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
        self._set_status("Ready")
        self._set_input_enabled(True)
        self.input_field.setFocus()

    def _on_model_error(self, message):
        self._model_ready = False
        self._set_status(message)
        self._set_input_enabled(False)

    def _append_transcript_line(self, line):
        self.transcript.append(line)
        scrollbar = self.transcript.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _append_transcript_token(self, token):
        cursor = self.transcript.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertText(token)
        self.transcript.setTextCursor(cursor)
        scrollbar = self.transcript.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _clear_chat(self):
        self.transcript.clear()
        self._history = []
        self._assistant_buffer = ""
        self._pending_user_text = ""

    def _send_message(self):
        user_text = self.input_field.text().strip()
        if not user_text:
            return
        self.input_field.clear()
        self._start_inference(user_text, user_text, self._should_include_cleanup(user_text))

    def _should_include_cleanup(self, text):
        lowered = text.lower()
        return any(word in lowered for word in ("clean", "cleanup", "delete temp", "free space"))

    def _recheck_model(self):
        if self._worker_is_running(self._load_worker) or self._worker_is_running(self._infer_worker):
            return
        if not model_exists():
            self._model_ready = False
            self._load_started = False
            self._set_status(missing_model_message(resolve_model_path()))
            self._set_input_enabled(False)
            return
        if self._engine.is_loaded:
            self._model_ready = True
            self._set_status("Ready")
            self._set_input_enabled(True)
            return
        self._start_model_load()

    def _start_inference(self, display_text, prompt_text=None, include_cleanup=False):
        if not self._model_ready:
            return
        if self._worker_is_running(self._infer_worker):
            return

        self._append_transcript_line(f"You: {display_text}")
        self._assistant_buffer = ""
        self._pending_user_text = display_text
        self._append_transcript_line("Assistant: ")
        self._set_input_enabled(False)
        self._set_status("Thinking...")

        self._infer_worker = InferenceWorker(
            self._engine,
            prompt_text or display_text,
            history=list(self._history),
            include_cleanup=include_cleanup,
        )
        self._infer_worker.token_received.connect(self._on_token_received)
        self._infer_worker.inference_complete.connect(self._on_inference_finished)
        self._infer_worker.error.connect(self._on_inference_error)
        self._infer_worker.finished.connect(self._clear_infer_worker)
        self._infer_worker.finished.connect(self._infer_worker.deleteLater)
        self._infer_worker.start()

    def _on_token_received(self, token):
        self._assistant_buffer += token
        self._append_transcript_token(token)

    def _on_inference_finished(self):
        answer = self._assistant_buffer.strip()
        if self._pending_user_text and answer:
            self._history.append({
                "user": self._pending_user_text,
                "assistant": answer,
            })
            self._history = self._history[-8:]
        self._pending_user_text = ""
        self._set_status("Ready")
        self._set_input_enabled(True)
        self.input_field.setFocus()

    def _on_inference_error(self, message):
        if not self._assistant_buffer:
            self._append_transcript_token(f"[Error: {message}]")
        else:
            self._append_transcript_token(f"\n[Error: {message}]")
        self._pending_user_text = ""
        self._set_status(message)
        self._set_input_enabled(True)
