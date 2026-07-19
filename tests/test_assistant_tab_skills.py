from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtWidgets import QApplication

from app.assistant_core import AssistantAction, AssistantSnapshot, READ_ONLY, MEDIUM_RISK
from app.assistant_tab import AssistantTab, InferenceWorker
from app.chat_widgets import ActionCard


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


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


def test_action_card_auto_run_hides_confirm_for_readonly(qapp):
    action = AssistantAction(
        id="1",
        kind="scan_cleanup",
        title="Scan",
        description="Scan junk",
        risk=READ_ONLY,
        requires_confirmation=False,
    )
    card = ActionCard(action)
    assert card.confirm_btn.isHidden() is True
    assert card.cancel_btn.isHidden() is True

    received = []
    card.confirmed.connect(lambda act, c: received.append(act.kind))
    card.begin_auto_run()
    assert received == ["scan_cleanup"]
    assert card.confirm_btn.text() == "Running…"


def test_action_card_mutation_awaits_confirm(qapp):
    action = AssistantAction(
        id="2",
        kind="empty_recycle_bin",
        title="Empty",
        description="Empty bin",
        risk=MEDIUM_RISK,
        requires_confirmation=True,
    )
    card = ActionCard(action)
    assert card.awaiting_confirm is True
    assert card.confirm_btn.isHidden() is False


def test_is_affirmation_and_newest_pending(qapp):
    tab = AssistantTab.__new__(AssistantTab)
    tab._pending_confirm_cards = []
    assert AssistantTab._is_affirmation(tab, "yes") is True
    assert AssistantTab._is_affirmation(tab, "OK!") is True
    assert AssistantTab._is_affirmation(tab, "why is it slow") is False

    action = AssistantAction(
        id="3",
        kind="empty_recycle_bin",
        title="Empty",
        description="Empty bin",
        risk=MEDIUM_RISK,
        requires_confirmation=True,
    )
    card = ActionCard(action)
    tab._pending_confirm_cards = [card]
    assert tab._newest_pending_confirm_card() is card


def test_capability_reply_skips_inference(qapp):
    tab = AssistantTab.__new__(AssistantTab)
    tab._history = []
    tab._model_ready = True
    tab._add_message = MagicMock()
    tab._set_status = MagicMock()
    with patch("app.assistant_tab.render_capability_user_answer", return_value="I can help with cleanup."):
        AssistantTab._reply_capability(tab, "what can you do")
    assert tab._add_message.call_count == 2
    assert len(tab._history) == 1
    assert "cleanup" in tab._history[0].assistant


def test_action_queue_stores_while_busy(qapp):
    tab = AssistantTab.__new__(AssistantTab)
    tab._action_queue = []
    tab._pending_action_card = object()
    tab._action_worker = None
    tab._set_status = MagicMock()
    tab._worker_is_running = MagicMock(return_value=False)
    action = AssistantAction(
        id="4",
        kind="flush_dns_cache",
        title="Flush",
        description="Flush DNS",
        risk=READ_ONLY,
        requires_confirmation=True,
    )
    card = ActionCard(action)
    AssistantTab._run_action(tab, action, card)
    assert tab._action_queue == [(action, card)]
    assert card.confirm_btn.text() == "Queued…"
