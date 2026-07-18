from datetime import datetime

from app.assistant_core import (
    ASSISTANT_SKILLS,
    ASSISTANT_TOOLS,
    SKILL_DOMAINS,
    AssistantSnapshot,
    LOW_RISK,
    MEDIUM_RISK,
    READ_ONLY,
    skill_request_to_action,
    validate_skill_request,
)
from app import toolbox


NEW_WAVE_SKILLS = (
    "clear_app_audio_route",
    "delete_saved_layout",
    "list_saved_layouts",
    "check_disk_free_space",
    "list_printers",
    "list_usb_devices",
    "list_running_services",
    "list_third_party_services",
    "check_service_status",
    "list_problem_devices",
    "check_listening_ports",
    "check_bluetooth_status",
    "check_unexpected_shutdowns",
    "check_component_store_health",
    "scan_volume_errors",
    "restart_print_spooler",
    "start_sfc_scan",
    "open_services_manager",
    "open_disk_cleanup",
    "open_windows_troubleshooter",
)


def test_new_wave_skills_are_registered():
    for name in (
        "empty_recycle_bin",
        "clean_temp_files",
        "list_network_adapters",
        "check_dns_resolve",
        "open_task_manager",
        "capture_layout_snapshot",
        "set_default_audio_device",
        *NEW_WAVE_SKILLS,
    ):
        assert name in ASSISTANT_SKILLS
        assert name in SKILL_DOMAINS


def test_skill_domains_cover_all_skills():
    assert set(SKILL_DOMAINS) == set(ASSISTANT_SKILLS)


def test_empty_recycle_bin_requires_confirmation():
    action, message = skill_request_to_action({
        "type": "skill_request",
        "skill": "empty_recycle_bin",
        "arguments": {},
    }, AssistantSnapshot(datetime.now()))

    assert message == ""
    assert action.kind == "empty_recycle_bin"
    assert action.risk == MEDIUM_RISK
    assert action.requires_confirmation is True


def test_check_dns_resolve_defaults_host():
    action, message = skill_request_to_action({
        "type": "skill_request",
        "skill": "check_dns_resolve",
        "arguments": {},
    }, AssistantSnapshot(datetime.now()))

    assert message == ""
    assert action.kind == "check_dns_resolve"
    assert action.risk == READ_ONLY
    assert action.payload == {"host": "one.one.one.one"}


def test_set_default_audio_device_resolves_from_snapshot():
    snapshot = AssistantSnapshot(
        datetime.now(),
        audio_devices=[{"id": "dev-1", "name": "Speakers", "is_default": True}],
    )
    action, message = skill_request_to_action({
        "type": "skill_request",
        "skill": "set_default_audio_device",
        "arguments": {"device_name": "Speakers"},
    }, snapshot)

    assert message == ""
    assert action.payload == {"device_id": "dev-1"}
    assert action.requires_confirmation is True


def test_clear_app_audio_route_resolves_from_snapshot():
    snapshot = AssistantSnapshot(
        datetime.now(),
        audio_sessions=[{
            "pid": 42,
            "display_name": "Chrome",
            "process_name": "chrome.exe",
        }],
    )
    action, message = skill_request_to_action({
        "type": "skill_request",
        "skill": "clear_app_audio_route",
        "arguments": {"app": "chrome"},
    }, snapshot)

    assert message == ""
    assert action.kind == "clear_app_audio_route"
    assert action.requires_confirmation is True
    assert action.risk == LOW_RISK
    assert action.payload["pid"] == 42


def test_delete_saved_layout_resolves_from_snapshot():
    snapshot = AssistantSnapshot(
        datetime.now(),
        saved_layouts=[{"id": "lay-1", "name": "Work"}],
    )
    action, message = skill_request_to_action({
        "type": "skill_request",
        "skill": "delete_saved_layout",
        "arguments": {"layout_name": "Work"},
    }, snapshot)

    assert message == ""
    assert action.kind == "delete_saved_layout"
    assert action.requires_confirmation is True
    assert action.risk == MEDIUM_RISK
    assert action.payload == {"layout_id": "lay-1"}


def test_check_service_status_rejects_unknown_key():
    action, message = skill_request_to_action({
        "type": "skill_request",
        "skill": "check_service_status",
        "arguments": {"service": "malware_service"},
    }, AssistantSnapshot(datetime.now()))

    assert action is None
    assert "allowlist" in message.lower()


def test_check_service_status_accepts_allowlisted_key():
    action, message = skill_request_to_action({
        "type": "skill_request",
        "skill": "check_service_status",
        "arguments": {"service": "spooler"},
    }, AssistantSnapshot(datetime.now()))

    assert message == ""
    assert action.kind == "check_service_status"
    assert action.payload == {"service": "spooler"}
    assert action.risk == READ_ONLY


def test_open_windows_troubleshooter_rejects_unknown_key():
    action, message = skill_request_to_action({
        "type": "skill_request",
        "skill": "open_windows_troubleshooter",
        "arguments": {"troubleshooter": "registry"},
    }, AssistantSnapshot(datetime.now()))

    assert action is None
    assert "troubleshooter" in message.lower()


def test_open_windows_troubleshooter_accepts_allowlisted_key():
    action, message = skill_request_to_action({
        "type": "skill_request",
        "skill": "open_windows_troubleshooter",
        "arguments": {"troubleshooter": "printer"},
    }, AssistantSnapshot(datetime.now()))

    assert message == ""
    assert action.payload == {"troubleshooter": "printer"}
    assert action.requires_confirmation is False


def test_restart_print_spooler_and_sfc_require_confirmation():
    for skill_name in ("restart_print_spooler", "start_sfc_scan"):
        action, message = skill_request_to_action({
            "type": "skill_request",
            "skill": skill_name,
            "arguments": {},
        }, AssistantSnapshot(datetime.now()))
        assert message == ""
        assert action.requires_confirmation is True
        assert action.risk == MEDIUM_RISK


def test_scan_downloads_large_files_maps_to_scan_large_files():
    action, message = skill_request_to_action({
        "type": "skill_request",
        "skill": "scan_downloads_large_files",
        "arguments": {"min_size_mb": 200},
    }, AssistantSnapshot(datetime.now()))

    assert message == ""
    assert action.kind == "scan_large_files"
    assert action.payload["min_size_mb"] == 200
    assert "Downloads" in action.payload["root"]


def test_open_storage_settings_page_allowed():
    result = validate_skill_request({
        "type": "skill_request",
        "skill": "open_windows_settings",
        "arguments": {"page": "storage"},
    })
    assert result.success
    action, message = skill_request_to_action({
        "type": "skill_request",
        "skill": "open_windows_settings",
        "arguments": {"page": "storage"},
    }, AssistantSnapshot(datetime.now()))
    assert message == ""
    assert action.payload == {"page": "storage"}


def test_new_tools_exist_for_new_skills():
    for name in NEW_WAVE_SKILLS:
        skill = ASSISTANT_SKILLS[name]
        assert skill.action_kind in ASSISTANT_TOOLS


def test_toolbox_service_and_troubleshooter_allowlists():
    assert "spooler" in toolbox.SERVICE_STATUS_KEYS
    assert "printer" in toolbox.TROUBLESHOOTER_KEYS
