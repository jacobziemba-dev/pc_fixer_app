from datetime import datetime
from unittest.mock import patch

from app.assistant_core import (
    AssistantAction,
    AssistantSnapshot,
    LOW_RISK,
    MEDIUM_RISK,
    READ_ONLY,
    execute_assistant_action,
    render_skill_catalog,
    skill_request_to_action,
    validate_skill_request,
)
from app.toolbox import ToolResult


def test_toolbox_skills_are_documented_in_catalog():
    catalog = render_skill_catalog()

    assert "check_windows_updates" in catalog
    assert "restart_network_adapter" in catalog
    assert "create_restore_point" in catalog


def test_restart_adapter_requires_adapter_name():
    request = {
        "type": "skill_request",
        "skill": "restart_network_adapter",
        "arguments": {},
    }

    result = validate_skill_request(request)

    assert result.success is False
    assert "adapter_name" in result.message


def test_set_power_plan_skill_validation_and_action_payload():
    action, message = skill_request_to_action({
        "type": "skill_request",
        "skill": "set_power_plan",
        "arguments": {"plan_name": "balanced"},
    }, AssistantSnapshot(datetime.now()))

    assert message == ""
    assert action.kind == "set_power_plan"
    assert action.risk == LOW_RISK
    assert action.requires_confirmation is True
    assert action.payload == {"plan_name": "balanced"}


def test_scan_event_log_skill_clamps_hours():
    action, message = skill_request_to_action({
        "type": "skill_request",
        "skill": "scan_event_log_errors",
        "arguments": {"hours": 999},
    }, AssistantSnapshot(datetime.now()))

    assert message == ""
    assert action.payload == {"hours": 168}


def test_execute_toolbox_action_records_result_and_returns_details():
    with patch("app.assistant_core.toolbox.check_windows_updates") as check, \
         patch("app.assistant_core.tool_history.add_result") as add_result, \
         patch("app.assistant_core.collect_assistant_snapshot", return_value=AssistantSnapshot(datetime.now())):
        check.return_value = ToolResult(True, "Windows Update", "Checked updates.", ["Pending software updates: 0"])

        result, snapshot = execute_assistant_action(
            AssistantAction("1", "check_windows_updates", "Check", "Check", READ_ONLY),
            AssistantSnapshot(datetime.now()),
        )

    assert result.success is True
    assert "Pending software updates: 0" in result.message
    assert snapshot is not None
    add_result.assert_called_once()


def test_create_restore_point_action_is_confirmed_medium_risk():
    action, message = skill_request_to_action({
        "type": "skill_request",
        "skill": "create_restore_point",
        "arguments": {"description": "Before repair"},
    }, AssistantSnapshot(datetime.now()))

    assert message == ""
    assert action.kind == "create_restore_point"
    assert action.risk == MEDIUM_RISK
    assert action.requires_confirmation is True
    assert action.payload == {"description": "Before repair"}
