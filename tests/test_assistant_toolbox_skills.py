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
    assert "scan_folder_sizes" in catalog
    assert "end_process" in catalog
    assert "reset_winsock" in catalog
    assert "open_windows_settings" in catalog


def test_restart_adapter_resolves_from_snapshot():
    snapshot = AssistantSnapshot(
        datetime.now(),
        network_adapters=[{"name": "Wi-Fi", "is_up": True}],
    )
    action, message = skill_request_to_action({
        "type": "skill_request",
        "skill": "restart_network_adapter",
        "arguments": {},
    }, snapshot)

    assert message == ""
    assert action.payload == {"adapter_name": "Wi-Fi"}


def test_restart_adapter_rejects_when_ambiguous():
    snapshot = AssistantSnapshot(
        datetime.now(),
        network_adapters=[
            {"name": "Wi-Fi", "is_up": True},
            {"name": "Ethernet", "is_up": True},
        ],
    )
    action, message = skill_request_to_action({
        "type": "skill_request",
        "skill": "restart_network_adapter",
        "arguments": {},
    }, snapshot)

    assert action is None
    assert "more than one" in message.lower()


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


def test_end_process_skill_requires_confirmation_and_rejects_protected(monkeypatch):
    monkeypatch.setattr(
        "app.assistant_core.sysinfo.is_process_termination_allowed",
        lambda pid, name="": (False, "explorer.exe is protected and cannot be ended."),
    )

    action, message = skill_request_to_action({
        "type": "skill_request",
        "skill": "end_process",
        "arguments": {"pid": 123},
    }, AssistantSnapshot(datetime.now()))

    assert action is None
    assert "protected" in message.lower()


def test_end_process_skill_builds_confirmed_action(monkeypatch):
    monkeypatch.setattr(
        "app.assistant_core.sysinfo.is_process_termination_allowed",
        lambda pid, name="": (True, "notepad.exe"),
    )

    action, message = skill_request_to_action({
        "type": "skill_request",
        "skill": "end_process",
        "arguments": {"pid": 4321},
    }, AssistantSnapshot(datetime.now()))

    assert message == ""
    assert action.kind == "end_process"
    assert action.risk == MEDIUM_RISK
    assert action.requires_confirmation is True
    assert action.payload == {"pid": 4321}


def test_open_windows_settings_skill_rejects_unknown_page():
    action, message = skill_request_to_action({
        "type": "skill_request",
        "skill": "open_windows_settings",
        "arguments": {"page": "about:blank"},
    }, AssistantSnapshot(datetime.now()))

    assert action is None
    assert "Settings page" in message


def test_set_startup_item_enabled_skill_payload():
    snapshot = AssistantSnapshot(
        datetime.now(),
        startup_items=[{"name": "Steam", "source": "HKCU\\...\\Run", "command": "steam.exe"}],
    )
    action, message = skill_request_to_action({
        "type": "skill_request",
        "skill": "set_startup_item_enabled",
        "arguments": {"name": "Steam", "source": "HKCU\\...\\Run", "enabled": False},
    }, snapshot)

    assert message == ""
    assert action.kind == "set_startup_item_enabled"
    assert action.requires_confirmation is True
    assert action.payload == {
        "name": "Steam",
        "source": "HKCU\\...\\Run",
        "enabled": False,
        "command": "steam.exe",
    }


def test_scan_folder_sizes_skill_is_read_only():
    action, message = skill_request_to_action({
        "type": "skill_request",
        "skill": "scan_folder_sizes",
        "arguments": {"max_entries": 12},
    }, AssistantSnapshot(datetime.now()))

    assert message == ""
    assert action.kind == "scan_folder_sizes"
    assert action.risk == READ_ONLY
    assert action.requires_confirmation is False
    assert action.payload == {"max_entries": 12}
