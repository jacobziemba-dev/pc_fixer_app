from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock, patch
import builtins
import sys

import pytest

from app.ai_engine import (
    AIEngineError,
    DEFAULT_MODEL_FILENAME,
    EmbeddedAI,
    MODELS_DIR,
    format_chat_prompt,
    missing_model_message,
    model_exists,
    resolve_model_path,
)


def test_resolve_model_path_uses_project_models_dir():
    path = resolve_model_path()
    assert path == MODELS_DIR / DEFAULT_MODEL_FILENAME
    assert path.parent.name == "models"


def test_format_chat_prompt_uses_llama32_template():
    prompt = format_chat_prompt("System text", "User text")
    assert prompt == (
        "<|system|>\nSystem text<|end|>\n"
        "<|user|>\nUser text<|end|>\n"
        "<|assistant|>\n"
    )


def test_missing_model_message_includes_path():
    path = resolve_model_path("custom-model.gguf")
    message = missing_model_message(path)
    assert "custom-model.gguf" in message
    assert "models/README.md" in message


def test_model_exists_false_for_missing_file(tmp_path):
    assert model_exists(tmp_path / "missing.gguf") is False


def test_model_exists_true_for_existing_file(tmp_path):
    model_file = tmp_path / "test.gguf"
    model_file.write_bytes(b"fake")
    assert model_exists(model_file) is True


def _install_fake_llama(mock_llama_cls):
    fake_module = ModuleType("llama_cpp")
    fake_module.Llama = mock_llama_cls
    return patch.dict(sys.modules, {"llama_cpp": fake_module})


def test_embedded_ai_load_raises_when_model_missing(tmp_path):
    engine = EmbeddedAI(model_path=tmp_path / "missing.gguf")
    with pytest.raises(AIEngineError, match="Model file not found"):
        engine.load()


def test_embedded_ai_load_raises_when_package_missing(tmp_path):
    model_file = tmp_path / "test.gguf"
    model_file.write_bytes(b"fake")
    engine = EmbeddedAI(model_path=model_file)

    real_import = builtins.__import__

    def mock_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "llama_cpp":
            raise ImportError("No module named 'llama_cpp'")
        return real_import(name, globals, locals, fromlist, level)

    with patch("builtins.__import__", side_effect=mock_import):
        with pytest.raises(AIEngineError, match="llama-cpp-python is not installed"):
            engine.load()


def test_embedded_ai_query_returns_trimmed_text(tmp_path):
    model_file = tmp_path / "test.gguf"
    model_file.write_bytes(b"fake")

    mock_llm = MagicMock()
    mock_llm.return_value = {"choices": [{"text": "  Hello there  "}]}

    engine = EmbeddedAI(model_path=model_file)
    with _install_fake_llama(MagicMock(return_value=mock_llm)):
        engine.load()
        result = engine.query("System", "User")

    assert result == "Hello there"
    mock_llm.assert_called_once()
    call_kwargs = mock_llm.call_args.kwargs
    assert call_kwargs["max_tokens"] == 256
    assert call_kwargs["temperature"] == 0.3
    assert call_kwargs["stop"] == ["<|end|>", "\n\n"]


def test_embedded_ai_stream_query_yields_tokens(tmp_path):
    model_file = tmp_path / "test.gguf"
    model_file.write_bytes(b"fake")

    mock_llm = MagicMock()
    mock_llm.return_value = [
        {"choices": [{"text": "Hel"}]},
        {"choices": [{"text": ""}]},
        {"choices": [{"text": "lo"}]},
    ]

    engine = EmbeddedAI(model_path=model_file)
    with _install_fake_llama(MagicMock(return_value=mock_llm)):
        engine.load()
        tokens = list(engine.stream_query("System", "User"))

    assert tokens == ["Hel", "lo"]
    call_kwargs = mock_llm.call_args.kwargs
    assert call_kwargs["stream"] is True


def test_embedded_ai_load_is_idempotent(tmp_path):
    model_file = tmp_path / "test.gguf"
    model_file.write_bytes(b"fake")

    mock_llama_cls = MagicMock()
    engine = EmbeddedAI(model_path=model_file)
    with _install_fake_llama(mock_llama_cls):
        engine.load()
        engine.load()

    mock_llama_cls.assert_called_once()
