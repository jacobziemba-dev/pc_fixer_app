from datetime import datetime
from unittest.mock import patch

from app.assistant_core import AssistantSnapshot
from app.assistant_tab import InferenceWorker


class FakeEngine:
    def stream_query(self, _system_prompt, _prompt):
        return iter([
            "I can scan cleanup first.\n",
            "```json\n",
            '{"type":"skill_request","skill":"scan_cleanup","arguments":{}}\n',
            "```",
        ])


def test_inference_worker_parses_skill_actions_and_dedupes_keyword_fallback():
    snapshot = AssistantSnapshot(timestamp=datetime.now())
    actions = []
    final_text = []

    worker = InferenceWorker(
        FakeEngine(),
        "Can you clean junk?",
        "Can you clean junk?",
    )
    worker.actions_ready.connect(actions.extend)
    worker.assistant_text_ready.connect(final_text.append)

    with patch("app.assistant_tab.build_system_snapshot", return_value=snapshot):
        worker.run()

    assert [action.kind for action in actions] == ["scan_cleanup"]
    assert final_text == ["I can scan cleanup first."]
