import os
import time
from pathlib import Path

from app import system_info as sysinfo

DEFAULT_MODEL_FILENAME = "llama-3.2-3b-instruct-q4_k_m.gguf"
DEFAULT_STOP_TOKENS = ["<|eot_id|>"]
DEFAULT_SYSTEM_PROMPT = (
    "You are a Windows PC diagnostician inside the PC Fix app. "
    "Use the system snapshot provided with each question. "
    "Use recent conversation only for continuity, not as hardware facts. "
    "Answer in 2-4 short sentences with practical advice. "
    "Do not invent hardware details that are not in the snapshot."
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


def format_chat_prompt(system_prompt, user_prompt):
    """Format a prompt using the Llama 3.2 Instruct chat template."""
    return (
        "<|begin_of_text|>"
        "<|start_header_id|>system<|end_header_id|>\n\n"
        f"{system_prompt}<|eot_id|>"
        "<|start_header_id|>user<|end_header_id|>\n\n"
        f"{user_prompt}<|eot_id|>"
        "<|start_header_id|>assistant<|end_header_id|>\n\n"
    )


def trim_chat_history(history, max_turns=MAX_HISTORY_TURNS):
    """Return the newest complete chat turns, preserving their original order."""
    if not history:
        return []
    return list(history)[-max_turns:]


def format_chat_history(history, max_turns=MAX_HISTORY_TURNS):
    turns = trim_chat_history(history, max_turns)
    if not turns:
        return ""

    lines = []
    for turn in turns:
        user = str(turn.get("user", "")).strip()
        assistant = str(turn.get("assistant", "")).strip()
        if not user and not assistant:
            continue
        if user:
            lines.append(f"User: {user}")
        if assistant:
            lines.append(f"Assistant: {assistant}")
    return "\n".join(lines)


def compose_user_prompt(user_text, context=None, history=None):
    sections = []
    if context:
        sections.append(f"System snapshot:\n{context}")

    history_text = format_chat_history(history)
    if history_text:
        sections.append(f"Recent conversation:\n{history_text}")

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


def build_system_context(include_cleanup=False):
    """Build a compact live PC snapshot for the assistant prompt."""
    lines = []
    cpu_percent = None
    memory_percent = None
    drives = []

    try:
        sysinfo.prime_process_cpu_percent()
        time.sleep(0.2)
    except Exception:
        pass

    try:
        cpu = sysinfo.get_cpu_stats()
        cpu_percent = cpu["percent"]
        lines.append(f"CPU: {cpu['percent']:.0f}%")
        if cpu.get("freq_mhz"):
            lines.append(f"CPU speed: {cpu['freq_mhz']:.0f} MHz")
    except Exception:
        lines.append("CPU: unavailable")

    try:
        mem = sysinfo.get_memory_stats()
        memory_percent = mem["percent"]
        lines.append(
            f"RAM: {sysinfo.format_bytes(mem['used'])} / "
            f"{sysinfo.format_bytes(mem['total'])} ({mem['percent']:.0f}%)"
        )
    except Exception:
        lines.append("RAM: unavailable")

    try:
        drives = sysinfo.get_disk_usage()[:4]
        if drives:
            for drive in drives:
                lines.append(
                    f"Disk {drive['mountpoint']}: "
                    f"{sysinfo.format_bytes(drive['free'])} free of "
                    f"{sysinfo.format_bytes(drive['total'])} "
                    f"({drive['percent']:.0f}% used)"
                )
        else:
            lines.append("Disk: unavailable")
    except Exception:
        lines.append("Disk: unavailable")

    try:
        startup_items = sysinfo.get_startup_items()
        lines.append(f"Startup apps: {len(startup_items)} detected")
        for item in startup_items[:5]:
            lines.append(f"- Startup: {item['name']} ({item['source']})")
    except Exception:
        lines.append("Startup apps: unavailable")

    try:
        procs = sysinfo.get_top_processes(limit=5, sort_by="cpu")
        if procs:
            lines.append("Top processes (by CPU):")
            for proc in procs:
                lines.append(
                    f"- {proc['name']}: {proc['cpu']:.1f}% CPU, "
                    f"{sysinfo.format_bytes(proc['mem'])}"
                )
        else:
            lines.append("Processes: unavailable")
    except Exception:
        lines.append("Processes: unavailable")

    try:
        mem_procs = sysinfo.get_top_processes(limit=3, sort_by="mem")
        if mem_procs:
            lines.append("Top processes (by RAM):")
            for proc in mem_procs:
                lines.append(
                    f"- {proc['name']}: {sysinfo.format_bytes(proc['mem'])}, "
                    f"{proc['cpu']:.1f}% CPU"
                )
    except Exception:
        lines.append("Memory-heavy processes: unavailable")

    try:
        displays = sysinfo.get_display_devices()
        lines.append(f"Displays: {len(displays)} connected")
        for display in displays[:3]:
            mode = sysinfo.get_current_display_mode(display.name)
            primary = "primary" if display.is_primary else "secondary"
            lines.append(
                f"- Display: {display.label} ({primary}), "
                f"{mode.width}x{mode.height} @ {mode.refresh_hz} Hz"
            )
    except Exception:
        lines.append("Displays: unavailable")

    if include_cleanup:
        try:
            cleanup_categories = sysinfo.scan_cleanup_targets()
            total_cleanup = sum(cat.size_bytes for cat in cleanup_categories)
            lines.append(
                f"Cleanup candidates: {len(cleanup_categories)} categories, "
                f"{sysinfo.format_bytes(total_cleanup)} found"
            )
            for cat in cleanup_categories[:5]:
                lines.append(
                    f"- Cleanup: {cat.label}, {sysinfo.format_bytes(cat.size_bytes)}, "
                    f"{cat.file_count} files"
                )
        except Exception:
            lines.append("Cleanup candidates: unavailable")

    _append_warnings(lines, cpu_percent, memory_percent, drives)

    useful = [
        line for line in lines
        if not line.endswith(": unavailable")
        and line not in {
            "Top processes (by CPU):",
            "Top processes (by RAM):",
            "Warnings:",
        }
    ]
    if not useful:
        return SNAPSHOT_UNAVAILABLE
    return "\n".join(lines)


class EmbeddedAI:
    def __init__(
        self,
        model_path=None,
        n_ctx=2048,
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
        max_tokens=256,
        temperature=0.3,
        stop=None,
    ):
        self._ensure_loaded()
        prompt = format_chat_prompt(system_prompt, user_prompt)
        output = self._llm(
            prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            stop=stop or DEFAULT_STOP_TOKENS,
        )
        return output["choices"][0]["text"].strip()

    def stream_query(
        self,
        system_prompt,
        user_prompt,
        max_tokens=256,
        temperature=0.3,
        stop=None,
    ):
        self._ensure_loaded()
        prompt = format_chat_prompt(system_prompt, user_prompt)
        stream = self._llm(
            prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            stop=stop or DEFAULT_STOP_TOKENS,
            stream=True,
        )
        for chunk in stream:
            text = chunk["choices"][0]["text"]
            if text:
                yield text
