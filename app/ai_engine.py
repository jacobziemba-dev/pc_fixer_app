import os
from pathlib import Path

DEFAULT_MODEL_FILENAME = "llama-3.2-1b-instruct-q4_k_m.gguf"
DEFAULT_SYSTEM_PROMPT = (
    "You are a helpful Windows PC assistant inside the PC Fix app. Answer concisely."
)
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
    return (
        f"<|system|>\n{system_prompt}<|end|>\n"
        f"<|user|>\n{user_prompt}<|end|>\n"
        f"<|assistant|>\n"
    )


class EmbeddedAI:
    def __init__(
        self,
        model_path=None,
        n_ctx=1024,
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
            stop=stop or ["<|end|>", "\n\n"],
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
            stop=stop or ["<|end|>", "\n\n"],
            stream=True,
        )
        for chunk in stream:
            text = chunk["choices"][0]["text"]
            if text:
                yield text
