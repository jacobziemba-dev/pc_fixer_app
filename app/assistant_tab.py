from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QShowEvent, QTextCursor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QLineEdit,
)

from app.ai_engine import (
    AIEngineError,
    DEFAULT_SYSTEM_PROMPT,
    EmbeddedAI,
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


class InferenceWorker(QThread):
    token_received = Signal(str)
    finished = Signal()
    error = Signal(str)

    def __init__(self, engine, user_prompt, system_prompt=DEFAULT_SYSTEM_PROMPT):
        super().__init__()
        self._engine = engine
        self._user_prompt = user_prompt
        self._system_prompt = system_prompt

    def run(self):
        try:
            for token in self._engine.stream_query(
                self._system_prompt,
                self._user_prompt,
            ):
                self.token_received.emit(token)
            self.finished.emit()
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

        outer = QVBoxLayout(self)

        header_layout = QHBoxLayout()
        title = QLabel("Assistant")
        title.setProperty("role", "heading")
        header_layout.addWidget(title)
        header_layout.addStretch(1)
        self.status_label = QLabel("Checking model...")
        self.status_label.setProperty("role", "caption")
        header_layout.addWidget(self.status_label)
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
        self.send_btn.setEnabled(enabled)

    def _start_model_load(self):
        if self._load_worker and self._load_worker.isRunning():
            return

        self._load_started = True
        self._set_status("Loading model...")
        self._set_input_enabled(False)

        self._load_worker = ModelLoadWorker(self._engine)
        self._load_worker.finished_ok.connect(self._on_model_loaded)
        self._load_worker.error.connect(self._on_model_error)
        self._load_worker.finished.connect(self._load_worker.deleteLater)
        self._load_worker.start()

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

    def _send_message(self):
        if not self._model_ready:
            return
        if self._infer_worker and self._infer_worker.isRunning():
            return

        user_text = self.input_field.text().strip()
        if not user_text:
            return

        self.input_field.clear()
        self._append_transcript_line(f"You: {user_text}")
        self._assistant_buffer = ""
        self._append_transcript_line("Assistant: ")
        self._set_input_enabled(False)
        self._set_status("Thinking...")

        self._infer_worker = InferenceWorker(self._engine, user_text)
        self._infer_worker.token_received.connect(self._on_token_received)
        self._infer_worker.finished.connect(self._on_inference_finished)
        self._infer_worker.error.connect(self._on_inference_error)
        self._infer_worker.finished.connect(self._infer_worker.deleteLater)
        self._infer_worker.start()

    def _on_token_received(self, token):
        self._assistant_buffer += token
        self._append_transcript_token(token)

    def _on_inference_finished(self):
        self._set_status("Ready")
        self._set_input_enabled(True)
        self.input_field.setFocus()

    def _on_inference_error(self, message):
        if not self._assistant_buffer:
            self._append_transcript_token(f"[Error: {message}]")
        else:
            self._append_transcript_token(f"\n[Error: {message}]")
        self._set_status(message)
        self._set_input_enabled(True)
