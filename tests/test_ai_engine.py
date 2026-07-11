from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock, patch
import builtins
import sys

import pytest

from app.assistant_core import AssistantTurn
from app.ai_engine import (
    AIEngineError,
    DEFAULT_MODEL_FILENAME,
    EmbeddedAI,
    MODELS_DIR,
    SNAPSHOT_UNAVAILABLE,
    build_skill_catalog,
    build_system_context,
    compose_user_prompt,
    format_chat_history,
    format_chat_prompt,
    missing_model_message,
    model_exists,
    resolve_model_path,
    trim_chat_history,
)


def test_resolve_model_path_uses_project_models_dir():
    path = resolve_model_path()
    assert path == MODELS_DIR / DEFAULT_MODEL_FILENAME
    assert path.parent.name == "models"


def test_format_chat_prompt_uses_llama32_template():
    prompt = format_chat_prompt("System text", "User text")
    assert prompt == (
        "<|start_header_id|>system<|end_header_id|>\n\n"
        "System text<|eot_id|>"
        "<|start_header_id|>user<|end_header_id|>\n\n"
        "User text<|eot_id|>"
        "<|start_header_id|>assistant<|end_header_id|>\n\n"
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
    assert call_kwargs["stop"] == ["<|eot_id|>"]


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


def _mock_sysinfo_happy():
    return {
        "prime_process_cpu_percent": MagicMock(),
        "get_cpu_stats": MagicMock(return_value={"percent": 34.2, "per_core": [], "freq_mhz": None}),
        "get_memory_stats": MagicMock(return_value={
            "total": 32 * 1024**3,
            "used": 12.1 * 1024**3,
            "available": 19.9 * 1024**3,
            "percent": 38.0,
        }),
        "get_disk_usage": MagicMock(return_value=[{
            "device": "C:",
            "mountpoint": "C:\\",
            "fstype": "NTFS",
            "total": 512 * 1024**3,
            "used": 332 * 1024**3,
            "free": 180 * 1024**3,
            "percent": 65.0,
        }]),
        "get_network_counters": MagicMock(return_value={"bytes_sent": 1024, "bytes_recv": 2048}),
        "get_hardware_info": MagicMock(return_value={
            "cpu": [{"Name": "Test CPU"}],
            "gpu": [{"Name": "Test GPU"}],
            "system": [],
            "board": [],
            "bios": [],
            "os": [],
            "disk_drives": [],
            "physical_disks": [],
            "memory_modules": [],
            "logical_cores": 8,
            "physical_cores": 4,
        }),
        "get_startup_items": MagicMock(return_value=[
            {"name": "OneDrive", "command": "onedrive.exe", "source": "HKCU\\...\\Run"},
        ]),
        "get_installed_programs": MagicMock(return_value=[
            {"name": "Example App", "publisher": "Example", "size_bytes": 1024**3},
        ]),
        "get_top_processes": MagicMock(return_value=[
            {"pid": 1, "name": "chrome.exe", "cpu": 12.4, "mem": 1.2 * 1024**3},
            {"pid": 2, "name": "code.exe", "cpu": 8.1, "mem": 800 * 1024**2},
        ]),
        "get_display_devices": MagicMock(return_value=[]),
        "format_bytes": MagicMock(side_effect=lambda n: f"{n / 1024**3:.1f} GB"),
    }


def test_compose_user_prompt_with_context():
    result = compose_user_prompt("Why is it slow?", "CPU: 90%")
    assert "System snapshot:" in result
    assert "CPU: 90%" in result
    assert "User question: Why is it slow?" in result


def test_compose_user_prompt_with_skill_catalog():
    result = compose_user_prompt("Clean junk?", "CPU: 10%", skill_catalog="Available assistant skills:\n- scan_cleanup")

    assert "System snapshot:" in result
    assert "Available assistant skills:" in result
    assert "scan_cleanup" in result
    assert "User question: Clean junk?" in result


def test_build_skill_catalog_mentions_skill_request_shape():
    catalog = build_skill_catalog()

    assert "skill_request" in catalog
    assert "scan_cleanup" in catalog


def test_compose_user_prompt_without_context():
    assert compose_user_prompt("Hello") == "Hello"
    assert compose_user_prompt("Hello", None) == "Hello"
    assert compose_user_prompt("Hello", "") == "Hello"


def test_trim_chat_history_keeps_newest_turns():
    history = [{"user": f"u{i}", "assistant": f"a{i}"} for i in range(10)]
    trimmed = trim_chat_history(history, max_turns=3)

    assert trimmed == history[-3:]


def test_format_chat_history_uses_user_and_assistant_lines():
    history = [AssistantTurn("What is high?", "CPU is high.", MagicMock())]

    result = format_chat_history(history)

    assert "User: What is high?" in result
    assert "Assistant: CPU is high." in result


def test_compose_user_prompt_with_history():
    history = [AssistantTurn("What is high?", "CPU is high.", MagicMock())]

    result = compose_user_prompt("What next?", "CPU: 90%", history)

    assert "System snapshot:" in result
    assert "Recent conversation:" in result
    assert "Assistant: CPU is high." in result
    assert "User question: What next?" in result


def test_build_system_context_happy_path():
    mocks = _mock_sysinfo_happy()
    with patch("app.ai_engine.time.sleep") as sleep_mock, \
         patch.multiple("app.assistant_core.sysinfo", **mocks):
        context = build_system_context()

    sleep_mock.assert_called_once_with(0.2)
    mocks["prime_process_cpu_percent"].assert_called_once()
    assert "CPU: 34%" in context
    assert "RAM:" in context
    assert "38%" in context
    assert "Disk C:\\:" in context
    assert "Startup apps: 1 detected" in context
    assert "chrome.exe" in context
    assert "code.exe" in context


def test_build_system_context_partial_failure():
    mocks = _mock_sysinfo_happy()
    mocks["get_disk_usage"] = MagicMock(side_effect=RuntimeError("disk boom"))
    with patch("app.ai_engine.time.sleep"), \
         patch.multiple("app.assistant_core.sysinfo", **mocks):
        context = build_system_context()

    assert "CPU: 34%" in context
    assert "RAM:" in context
    assert "chrome.exe" in context
    assert "Disk: unavailable" in context


def test_build_system_context_total_failure():
    failing = MagicMock(side_effect=RuntimeError("boom"))
    with patch("app.ai_engine.time.sleep"), \
         patch("app.assistant_core.sysinfo.prime_process_cpu_percent", failing), \
         patch("app.assistant_core.sysinfo.get_cpu_stats", failing), \
         patch("app.assistant_core.sysinfo.get_memory_stats", failing), \
         patch("app.assistant_core.sysinfo.get_disk_usage", failing), \
         patch("app.assistant_core.sysinfo.get_network_counters", failing), \
         patch("app.assistant_core.sysinfo.get_hardware_info", failing), \
         patch("app.assistant_core.sysinfo.get_startup_items", failing), \
         patch("app.assistant_core.sysinfo.get_installed_programs", failing), \
         patch("app.assistant_core.sysinfo.get_top_processes", failing), \
         patch("app.assistant_core.sysinfo.get_display_devices", failing), \
         patch("app.assistant_core._audio_snapshot", failing), \
         patch("app.assistant_core._layout_snapshot", failing):
        context = build_system_context()

    assert context == SNAPSHOT_UNAVAILABLE
