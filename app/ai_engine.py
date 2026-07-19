import os
from datetime import datetime
from pathlib import Path

from app.assistant_core import (
    AssistantTurn,
    collect_assistant_snapshot,
    render_capability_overview,
    render_snapshot_context,
    render_skill_catalog,
    snapshot_has_useful_data,
)

DEFAULT_MODEL_FILENAME = "llama-3.2-3b-instruct-q4_k_m.gguf"
DEFAULT_STOP_TOKENS = ["<|eot_id|>"]
DEFAULT_SYSTEM_PROMPT = (
    "You are a Windows PC diagnostician inside the PC Fix app. "
    "You can help with hardware & specs, processes & performance, storage & disks, "
    "cleanup, network, startup apps, power & battery, security & updates, display, "
    "audio, window layouts, and system tools. "
    "The Capability overview lists every requestable skill name; the detailed catalog "
    "adds argument schemas for skills most relevant to the current question. "
    "Use the system snapshot provided with each question. "
    "Use recent conversation only for continuity, not as hardware facts. "
    "Answer in 2-4 short sentences with practical advice. "
    "Do not invent hardware details, process names, adapters, or devices that are not in the snapshot. "
    "Prefer one skill request unless the user clearly asked for a multi-step plan. "
    "When an app action would help, explain what you found, recommend the next action, "
    "and include fenced JSON skill requests only for known skills listed in the overview or catalog. "
    "If needed snapshot data is missing, say you need a refresh first and request the matching refresh skill. "
    "Never claim an action already ran before the app confirms it. "
    "The app validates every request and requires confirmation for PC-changing actions."
)
HEALTH_CHECK_PROMPT = (
    "Summarize my PC health and suggest the top 1-2 things I should check."
)
SLOW_PC_PROMPT = (
    "Help me understand why this PC might feel slow. Prioritize CPU, RAM, "
    "disk space, and top processes from the snapshot."
)
DISK_SPACE_PROMPT = (
    "Check my disk space and tell me whether any drive needs attention."
)
STARTUP_REVIEW_PROMPT = (
    "Review my startup apps at a high level and suggest what I should inspect."
)
CLEANUP_REVIEW_PROMPT = (
    "Tell me what looks safe to clean and what I should review before deleting."
)
SNAPSHOT_UNAVAILABLE = "(system snapshot unavailable)"
PROJECT_ROOT = Path(__file__).resolve().parent.parent
MODELS_DIR = PROJECT_ROOT / "models"
MAX_HISTORY_TURNS = 8
MAX_HISTORY_CHARS = 1800
DEFAULT_N_CTX = 4096
DEFAULT_MAX_TOKENS = 320
DEFAULT_REPEAT_PENALTY = 1.1
SNAPSHOT_REUSE_TTL_SECONDS = 30


class AIEngineError(Exception):
    pass


def resolve_model_path(filename=DEFAULT_MODEL_FILENAME):
    return MODELS_DIR / filename


def model_exists(path=None):
    target = path or resolve_model_path()
    return Path(target).is_file()


def missing_model_message(path=None):
    target = Path(path or resolve_model_path())
    return (
        f"Model file not found: {target}\n"
        f"Download a GGUF model and place it in the models/ folder. "
        f"See models/README.md for instructions."
    )


def _turn_texts(turn):
    if isinstance(turn, AssistantTurn):
        return turn.user.strip(), turn.assistant.strip()
    return str(turn.get("user", "")).strip(), str(turn.get("assistant", "")).strip()


def trim_chat_history(history, max_turns=MAX_HISTORY_TURNS, max_chars=MAX_HISTORY_CHARS):
    """Return newest turns that fit both turn and character budgets."""
    if not history:
        return []
    selected = []
    used_chars = 0
    for turn in reversed(list(history)[-max_turns:]):
        user, assistant = _turn_texts(turn)
        if not user and not assistant:
            continue
        cost = len(user) + len(assistant)
        if selected and used_chars + cost > max_chars:
            break
        selected.append(turn)
        used_chars += cost
    selected.reverse()
    return selected


def format_chat_history(history, max_turns=MAX_HISTORY_TURNS, max_chars=MAX_HISTORY_CHARS):
    """Legacy plain-text history (kept for tests and debugging)."""
    turns = trim_chat_history(history, max_turns=max_turns, max_chars=max_chars)
    if not turns:
        return ""

    lines = []
    for turn in turns:
        user, assistant = _turn_texts(turn)
        if user:
            lines.append(f"User: {user}")
        if assistant:
            lines.append(f"Assistant: {assistant}")
    return "\n".join(lines)


def format_chat_prompt(system_prompt, user_prompt, history=None):
    """Format a prompt using the Llama 3.2 Instruct chat template with native history turns."""
    parts = [
        "<|start_header_id|>system<|end_header_id|>\n\n",
        f"{system_prompt}<|eot_id|>",
    ]
    for turn in trim_chat_history(history):
        user, assistant = _turn_texts(turn)
        if user:
            parts.append(
                "<|start_header_id|>user<|end_header_id|>\n\n"
                f"{user}<|eot_id|>"
            )
        if assistant:
            parts.append(
                "<|start_header_id|>assistant<|end_header_id|>\n\n"
                f"{assistant}<|eot_id|>"
            )
    parts.append(
        "<|start_header_id|>user<|end_header_id|>\n\n"
        f"{user_prompt}<|eot_id|>"
        "<|start_header_id|>assistant<|end_header_id|>\n\n"
    )
    return "".join(parts)


def compose_user_prompt(
    user_text,
    context=None,
    history=None,
    skill_catalog=None,
    capability_overview=None,
):
    """Compose the current-turn user message (snapshot + overview + catalog + question).

    History is passed separately to format_chat_prompt as native chat turns.
    The optional history argument is ignored here for backward compatibility.
    """
    del history  # history is applied in format_chat_prompt
    sections = []
    if context:
        sections.append(f"System snapshot:\n{context}")

    overview = capability_overview if capability_overview is not None else render_capability_overview()
    if overview:
        sections.append(overview)

    if skill_catalog:
        sections.append(skill_catalog)

    if not sections:
        return user_text
    sections.append(f"User question: {user_text}")
    return "\n\n".join(sections)


def _append_warnings(lines, cpu_percent=None, memory_percent=None, drives=None):
    warnings = []
    if cpu_percent is not None and cpu_percent >= 85:
        warnings.append(f"High CPU load ({cpu_percent:.0f}%).")
    if memory_percent is not None and memory_percent >= 85:
        warnings.append(f"High RAM use ({memory_percent:.0f}%).")
    for drive in drives or []:
        try:
            if drive["percent"] >= 90:
                warnings.append(
                    f"Drive {drive['mountpoint']} is nearly full "
                    f"({drive['percent']:.0f}% used)."
                )
        except (KeyError, TypeError):
            continue
    if warnings:
        lines.append("Warnings:")
        lines.extend(f"- {warning}" for warning in warnings)


def _snapshot_is_reusable(snapshot, include_cleanup=False):
    if snapshot is None or not getattr(snapshot, "timestamp", None):
        return False
    try:
        age = (datetime.now() - snapshot.timestamp).total_seconds()
    except Exception:
        return False
    if age < 0 or age > SNAPSHOT_REUSE_TTL_SECONDS:
        return False
    if include_cleanup and not getattr(snapshot, "cleanup_categories", None):
        return False
    return True


def build_system_snapshot(include_cleanup=False, reuse_snapshot=None, force_refresh=False):
    """Build structured live PC context for the assistant and UI."""
    if not force_refresh and _snapshot_is_reusable(reuse_snapshot, include_cleanup=include_cleanup):
        return reuse_snapshot
    return collect_assistant_snapshot(include_cleanup=include_cleanup)


def build_system_context(include_cleanup=False):
    """Build a compact live PC snapshot for the assistant prompt."""
    snapshot = build_system_snapshot(include_cleanup=include_cleanup)
    if not snapshot_has_useful_data(snapshot):
        return SNAPSHOT_UNAVAILABLE
    return render_snapshot_context(snapshot)


def build_skill_catalog(user_text=None):
    return render_skill_catalog(user_text=user_text)


class EmbeddedAI:
    def __init__(
        self,
        model_path=None,
        n_ctx=DEFAULT_N_CTX,
        n_threads=None,
    ):
        self.model_path = Path(model_path or resolve_model_path())
        self.n_ctx = n_ctx
        self.n_threads = n_threads or os.cpu_count() or 4
        self._llm = None

    @property
    def is_loaded(self):
        return self._llm is not None

    def load(self):
        if self._llm is not None:
            return

        if not self.model_path.is_file():
            raise AIEngineError(missing_model_message(self.model_path))

        try:
            from llama_cpp import Llama
        except ImportError as exc:
            raise AIEngineError(
                "llama-cpp-python is not installed. Run: pip install llama-cpp-python"
            ) from exc

        self._llm = Llama(
            model_path=str(self.model_path),
            n_ctx=self.n_ctx,
            n_threads=self.n_threads,
            verbose=False,
        )

    def _ensure_loaded(self):
        if self._llm is None:
            self.load()

    def query(
        self,
        system_prompt,
        user_prompt,
        max_tokens=DEFAULT_MAX_TOKENS,
        temperature=0.3,
        stop=None,
        history=None,
        repeat_penalty=DEFAULT_REPEAT_PENALTY,
    ):
        self._ensure_loaded()
        prompt = format_chat_prompt(system_prompt, user_prompt, history=history)
        output = self._llm(
            prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            stop=stop or DEFAULT_STOP_TOKENS,
            repeat_penalty=repeat_penalty,
        )
        return output["choices"][0]["text"].strip()

    def stream_query(
        self,
        system_prompt,
        user_prompt,
        max_tokens=DEFAULT_MAX_TOKENS,
        temperature=0.3,
        stop=None,
        history=None,
        repeat_penalty=DEFAULT_REPEAT_PENALTY,
    ):
        self._ensure_loaded()
        prompt = format_chat_prompt(system_prompt, user_prompt, history=history)
        stream = self._llm(
            prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            stop=stop or DEFAULT_STOP_TOKENS,
            repeat_penalty=repeat_penalty,
            stream=True,
        )
        for chunk in stream:
            text = chunk["choices"][0]["text"]
            if text:
                yield text
