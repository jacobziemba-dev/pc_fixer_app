from datetime import datetime

from app.assistant_core import (
    ASSISTANT_SKILLS,
    AssistantSnapshot,
    MEDIUM_RISK,
    READ_ONLY,
    skill_request_to_action,
    validate_skill_request,
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
    ):
        assert name in ASSISTANT_SKILLS


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
