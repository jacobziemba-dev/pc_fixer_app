import os
import time
from pathlib import Path

from app import system_info as sysinfo

DEFAULT_MODEL_FILENAME = "llama-3.2-3b-instruct-q4_k_m.gguf"
DEFAULT_STOP_TOKENS = ["<|eot_id|>"]
DEFAULT_SYSTEM_PROMPT = (
    "You are a Windows PC diagnostician inside the PC Fix app. "
    "Use the system snapshot provided with each question. "
    "Answer in 2-4 short sentences with practical advice. "
    "Do not invent hardware details that are not in the snapshot."
)
HEALTH_CHECK_PROMPT = (
    "Summarize my PC health and suggest the top 1-2 things I should check."
)
SNAPSHOT_UNAVAILABLE = "(system snapshot unavailable)"
PROJECT_ROOT = Path(__file__).resolve().parent.parent
MODELS_DIR = PROJECT_ROOT / "models"


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


def compose_user_prompt(user_text, context=None):
    if not context:
        return user_text
    return f"System snapshot:\n{context}\n\nUser question: {user_text}"


def build_system_context():
    """Build a compact live PC snapshot for the assistant prompt."""
    lines = []

    try:
        sysinfo.prime_process_cpu_percent()
        time.sleep(0.2)
    except Exception:
        pass

    try:
        cpu = sysinfo.get_cpu_stats()
        lines.append(f"CPU: {cpu['percent']:.0f}%")
    except Exception:
        lines.append("CPU: unavailable")

    try:
        mem = sysinfo.get_memory_stats()
        lines.append(
            f"RAM: {sysinfo.format_bytes(mem['used'])} / "
            f"{sysinfo.format_bytes(mem['total'])} ({mem['percent']:.0f}%)"
        )
    except Exception:
        lines.append("RAM: unavailable")

    try:
        drives = sysinfo.get_disk_usage()[:3]
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

    useful = [
        line for line in lines
        if not line.endswith(": unavailable") and line != "Top processes (by CPU):"
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
