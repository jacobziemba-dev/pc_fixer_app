from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

from app.assistant_core import AssistantSnapshot
from app.assistant_tab import AssistantTab, InferenceWorker


class FakeEngine:
    def stream_query(self, _system_prompt, _prompt):
        return iter([
            "I can scan cleanup first.\n",
            "```json\n",
            '{"type":"skill_request","skill":"scan_cleanup","arguments":{}}\n',
            "```",
        ])


class FakeEngineWithHistory:
    def __init__(self):
        self.last_history = None

    def stream_query(self, _system_prompt, _prompt, history=None):
        self.last_history = history
        return iter([
            "I can scan cleanup first.\n",
            "```json\n",
            '{"type":"skill_request","skill":"scan_cleanup","arguments":{}}\n',
            "```",
        ])


def test_inference_worker_parses_skill_actions_and_skips_keyword_fallback():
    snapshot = AssistantSnapshot(timestamp=datetime.now())
    actions = []
    final_text = []
    engine = FakeEngineWithHistory()

    worker = InferenceWorker(
        engine,
        "Can you clean junk?",
        "Can you clean junk?",
        history=[{"user": "hi", "assistant": "hello"}],
    )
    worker.actions_ready.connect(actions.extend)
    worker.assistant_text_ready.connect(final_text.append)

    with patch("app.assistant_tab.build_system_snapshot", return_value=snapshot), \
         patch("app.assistant_tab.build_skill_catalog", return_value="Available assistant skills:\n- scan_cleanup") as catalog:
        worker.run()

    catalog.assert_called_once_with(user_text="Can you clean junk?")
    assert engine.last_history == [{"user": "hi", "assistant": "hello"}]
    assert [action.kind for action in actions] == ["scan_cleanup"]
    assert final_text == ["I can scan cleanup first."]


def test_inference_worker_uses_keyword_fallback_when_no_skills():
    class NoSkillEngine:
        def stream_query(self, _system_prompt, _prompt, history=None):
            return iter(["Try a cleanup scan."])

    snapshot = AssistantSnapshot(timestamp=datetime.now())
    actions = []
    worker = InferenceWorker(NoSkillEngine(), "Can you clean junk?", "Can you clean junk?")
    worker.actions_ready.connect(actions.extend)

    with patch("app.assistant_tab.build_system_snapshot", return_value=snapshot):
        worker.run()

    assert [action.kind for action in actions] == ["scan_cleanup"]


def test_streaming_filter_hides_split_fenced_skill_json():
    state = SimpleNamespace(
        _stream_filter_buffer="",
        _stream_filter_in_skill_block=False,
    )
    tokens = [
        "I can scan first.\n",
        "```",
        "json\n",
        '{"type":"skill_request","skill":"scan_cleanup","arguments":{}}\n',
        "```",
        "\nDone.",
    ]

    visible = "".join(AssistantTab._filter_streaming_skill_json(state, token) for token in tokens)
    visible += AssistantTab._flush_stream_filter(state)

    assert "skill_request" not in visible
    assert "scan_cleanup" not in visible
    assert visible == "I can scan first.\n\nDone."
