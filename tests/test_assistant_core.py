from datetime import datetime
from unittest.mock import MagicMock, patch

from app.assistant_core import (
    ASSISTANT_TOOLS,
    AssistantAction,
    AssistantSnapshot,
    MEDIUM_RISK,
    READ_ONLY,
    collect_assistant_snapshot,
    dedupe_actions,
    execute_assistant_action,
    extract_skill_requests,
    get_assistant_tools,
    render_skill_catalog,
    skill_request_to_action,
    strip_skill_requests,
    validate_skill_request,
    propose_actions,
    render_snapshot_context,
    snapshot_summary_rows,
    snapshot_warnings,
)


def _cleanup_category(key="user_temp", label="User Temp Files", size=1024):
    return MagicMock(
        key=key,
        label=label,
        size_bytes=size,
        file_count=3,
    )


def test_render_snapshot_context_includes_core_sections():
    snapshot = AssistantSnapshot(
        timestamp=datetime(2026, 1, 1, 12, 0, 0),
        cpu={"percent": 91.0, "freq_mhz": 4200},
        memory={"used": 8 * 1024**3, "total": 16 * 1024**3, "percent": 50.0},
        disks=[{
            "mountpoint": "C:\\",
            "free": 10 * 1024**3,
            "total": 100 * 1024**3,
            "percent": 90.0,
        }],
        startup_items=[{"name": "OneDrive", "source": "HKCU\\...\\Run"}],
        installed_programs_summary={
            "count": 12,
            "largest": [{"name": "Big App", "size_bytes": 3 * 1024**3}],
        },
        top_cpu_processes=[{"name": "chrome.exe", "cpu": 12.0, "mem": 1024**3}],
        top_memory_processes=[{"name": "code.exe", "cpu": 2.0, "mem": 2 * 1024**3}],
        network={"bytes_sent": 1024, "bytes_recv": 4096},
        hardware_summary={"cpu": "Ryzen", "gpu": "RTX", "logical_cores": 16, "physical_cores": 8},
        displays=[{"label": "Dell", "primary": True, "mode": "2560x1440 @ 144 Hz"}],
        audio_devices=[{"name": "Speakers"}],
        audio_sessions=[{
            "display_name": "Browser (123)",
            "device_name": "Speakers",
            "volume": 0.5,
            "muted": False,
        }],
        saved_layouts=[{"name": "Work", "windows": 3, "displays": 2}],
        cleanup_categories=[_cleanup_category(size=4096)],
    )

    context = render_snapshot_context(snapshot)

    assert "CPU: 91%" in context
    assert "RAM:" in context
    assert "Disk C:\\:" in context
    assert "Startup apps: 1 detected" in context
    assert "Installed programs: 12 detected" in context
    assert "chrome.exe" in context
    assert "Network counters" in context
    assert "Hardware CPU: Ryzen" in context
    assert "Dell" in context
    assert "Audio: 1 playback device" in context
    assert "Layout: Work" in context
    assert "Cleanup candidates: 1 categories" in context
    assert "High CPU load" in context


def test_snapshot_summary_rows_reports_unavailable_and_cleanup_total():
    snapshot = AssistantSnapshot(
        timestamp=datetime.now(),
        cleanup_categories=[_cleanup_category(size=2048)],
        unavailable=["CPU"],
    )

    rows = snapshot_summary_rows(snapshot)

    assert ("CPU", "Unavailable") in rows
    assert ("Cleanup", "2.0 KB found") in rows
    assert ("Unavailable", "CPU") in rows


def test_snapshot_warnings_for_high_usage():
    snapshot = AssistantSnapshot(
        timestamp=datetime.now(),
        cpu={"percent": 90.0},
        memory={"percent": 88.0},
        disks=[{"mountpoint": "C:\\", "percent": 95.0}],
    )

    warnings = snapshot_warnings(snapshot)

    assert len(warnings) == 3
    assert any("High CPU" in warning for warning in warnings)
    assert any("High RAM" in warning for warning in warnings)
    assert any("nearly full" in warning for warning in warnings)


def test_collect_assistant_snapshot_records_partial_failures():
    with patch("app.assistant_core.sysinfo.get_cpu_stats", side_effect=RuntimeError("boom")), \
         patch("app.assistant_core.sysinfo.get_memory_stats", return_value={"percent": 20, "used": 1, "total": 2}), \
         patch("app.assistant_core.sysinfo.get_disk_usage", return_value=[]), \
         patch("app.assistant_core.sysinfo.get_network_counters", return_value={"bytes_sent": 1, "bytes_recv": 2}), \
         patch("app.assistant_core.sysinfo.get_hardware_info", return_value={}), \
         patch("app.assistant_core.sysinfo.get_startup_items", return_value=[]), \
         patch("app.assistant_core.sysinfo.get_installed_programs", return_value=[]), \
         patch("app.assistant_core.sysinfo.get_top_processes", return_value=[]), \
         patch("app.assistant_core.sysinfo.get_display_devices", return_value=[]), \
         patch("app.assistant_core._audio_snapshot", return_value=([], [])), \
         patch("app.assistant_core._layout_snapshot", return_value=[]):
        snapshot = collect_assistant_snapshot()

    assert "CPU" in snapshot.unavailable
    assert snapshot.memory["percent"] == 20


def test_propose_actions_for_cleanup_without_scan():
    actions = propose_actions("Can you clean junk files?", AssistantSnapshot(datetime.now()))

    assert any(action.kind == "scan_cleanup" for action in actions)
    assert not any(action.kind == "clean_cleanup_candidates" for action in actions)


def test_propose_actions_for_cleanup_with_scan():
    snapshot = AssistantSnapshot(
        timestamp=datetime.now(),
        cleanup_categories=[_cleanup_category()],
    )

    actions = propose_actions("Can you clean junk files?", snapshot)

    clean = [action for action in actions if action.kind == "clean_cleanup_candidates"]
    assert len(clean) == 1
    assert clean[0].risk == "Medium"
    assert clean[0].payload["category_keys"] == ["user_temp"]


def test_propose_actions_for_domains():
    actions = propose_actions("Check startup display audio layout and disk", AssistantSnapshot(datetime.now()))
    kinds = {action.kind for action in actions}

    assert "refresh_snapshot" in kinds
    assert "refresh_startup" in kinds
    assert "refresh_displays" in kinds
    assert "refresh_audio" in kinds
    assert "refresh_layouts" in kinds


def test_tool_registry_marks_read_only_and_confirmed_actions():
    tools = get_assistant_tools()

    assert tools["refresh_snapshot"].risk == READ_ONLY
    assert tools["refresh_snapshot"].requires_confirmation is False
    assert tools["clean_cleanup_candidates"].risk == MEDIUM_RISK
    assert tools["clean_cleanup_candidates"].requires_confirmation is True
    assert tools["set_display_refresh_rate"].payload_schema["hz"] == "int"
    assert set(tools) == set(ASSISTANT_TOOLS)


def test_propose_actions_for_safe_diagnostic_tools():
    actions = propose_actions(
        "Check network hardware startup programs and top processes",
        AssistantSnapshot(datetime.now()),
    )
    kinds = {action.kind for action in actions}

    assert "refresh_network" in kinds
    assert "refresh_hardware" in kinds
    assert "refresh_startup" in kinds
    assert "inspect_top_processes" in kinds


def test_propose_display_refresh_change_when_target_is_known():
    snapshot = AssistantSnapshot(
        timestamp=datetime.now(),
        displays=[{
            "name": r"\\.\DISPLAY1",
            "label": "Dell",
            "primary": True,
            "current_hz": 60,
            "supported_rates": [60, 144],
        }],
    )

    actions = propose_actions("Set highest refresh rate", snapshot)
    change = [action for action in actions if action.kind == "set_display_refresh_rate"]

    assert len(change) == 1
    assert change[0].requires_confirmation is True
    assert change[0].payload == {"device_name": r"\\.\DISPLAY1", "hz": 144}


def test_propose_audio_volume_action_only_when_single_session_is_known():
    snapshot = AssistantSnapshot(
        timestamp=datetime.now(),
        audio_sessions=[{
            "pid": 123,
            "process_name": "browser.exe",
            "display_name": "Browser (123)",
        }],
    )

    actions = propose_actions("Set volume to 25%", snapshot)
    volume = [action for action in actions if action.kind == "audio_set_volume"]

    assert len(volume) == 1
    assert volume[0].payload == {"pid": 123, "level": 0.25}


def test_execute_assistant_action_scans_cleanup():
    category = _cleanup_category(size=2048)
    with patch(
        "app.assistant_core.collect_assistant_snapshot",
        return_value=AssistantSnapshot(datetime.now(), cleanup_categories=[category]),
    ):
        result, snapshot = execute_assistant_action(
            AssistantAction(
                id="a1",
                kind="scan_cleanup",
                title="Scan",
                description="Scan",
                risk=READ_ONLY,
            )
        )

    assert result.success is True
    assert "2.0 KB" in result.message
    assert snapshot.cleanup_categories == [category]


def test_execute_assistant_action_rejects_unsupported_action():
    result, snapshot = execute_assistant_action(
        AssistantAction(
            id="a1",
            kind="not_real",
            title="Nope",
            description="Nope",
            risk=READ_ONLY,
        ),
        AssistantSnapshot(datetime.now()),
    )

    assert result.success is False
    assert "Unsupported action" in result.message
    assert snapshot is not None


def test_skill_catalog_includes_enabled_public_skills():
    catalog = render_skill_catalog()

    assert "scan_cleanup" in catalog
    assert "set_app_volume" in catalog
    assert "execute_assistant_action" not in catalog
    assert "arbitrary code" in catalog


def test_extract_skill_requests_from_fenced_and_raw_json():
    text = (
        "I can help.\n"
        "```json\n{\"type\":\"skill_request\",\"skill\":\"scan_cleanup\",\"arguments\":{}}\n```\n"
        "{\"type\":\"skill_request\",\"skill\":\"refresh_network\",\"arguments\":{}}"
    )

    requests = extract_skill_requests(text)

    assert [request["skill"] for request in requests] == ["scan_cleanup", "refresh_network"]


def test_extract_skill_requests_ignores_malformed_and_normal_text():
    assert extract_skill_requests("hello there") == []
    assert extract_skill_requests("```json\n{\"type\":\"skill_request\"\n```") == []


def test_strip_skill_requests_hides_internal_json():
    text = (
        "I will scan first.\n"
        "```json\n{\"type\":\"skill_request\",\"skill\":\"scan_cleanup\",\"arguments\":{}}\n```"
    )

    assert strip_skill_requests(text) == "I will scan first."


def test_strip_skill_requests_hides_raw_internal_json():
    text = 'I will scan first. {"type":"skill_request","skill":"scan_cleanup","arguments":{}}'

    assert strip_skill_requests(text) == "I will scan first."


def test_validate_skill_request_rejects_unknown_missing_and_wrong_type():
    assert not validate_skill_request({"type": "skill_request", "skill": "made_up", "arguments": {}}).success
    missing = validate_skill_request({
        "type": "skill_request",
        "skill": "set_app_volume",
        "arguments": {"app": "chrome"},
    })
    wrong = validate_skill_request({
        "type": "skill_request",
        "skill": "set_app_volume",
        "arguments": {"app": "chrome", "level": "quiet"},
    })
    unknown_args = validate_skill_request({
        "type": "skill_request",
        "skill": "scan_cleanup",
        "arguments": {"evil": "path"},
    })

    assert not missing.success
    assert "Missing required argument: level" in missing.message
    assert not wrong.success
    assert "level" in wrong.message
    assert not unknown_args.success
    assert "Unknown argument" in unknown_args.message


def test_scan_large_files_rejects_non_allowlisted_root(monkeypatch, tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    monkeypatch.setattr(
        "app.assistant_core._allowlisted_scan_roots",
        lambda snapshot=None: [],
    )
    action, message = skill_request_to_action({
        "type": "skill_request",
        "skill": "scan_large_files",
        "arguments": {"root": str(outside)},
    }, AssistantSnapshot(datetime.now()))

    assert action is None
    assert "allowlisted" in message.lower()


def test_skill_request_to_action_for_cleanup_scan():
    action, message = skill_request_to_action({
        "type": "skill_request",
        "skill": "scan_cleanup",
        "arguments": {},
    }, AssistantSnapshot(datetime.now()))

    assert message == ""
    assert action.kind == "scan_cleanup"
    assert action.risk == READ_ONLY


def test_skill_request_to_action_for_cleanup_clean_uses_scanned_categories():
    snapshot = AssistantSnapshot(
        timestamp=datetime.now(),
        cleanup_categories=[_cleanup_category("user_temp", size=2048)],
    )

    action, message = skill_request_to_action({
        "type": "skill_request",
        "skill": "clean_scanned_cleanup",
        "arguments": {},
    }, snapshot)

    assert message == ""
    assert action.kind == "clean_cleanup_candidates"
    assert action.requires_confirmation is True
    assert action.payload == {"category_keys": ["user_temp"]}


def test_skill_request_to_action_for_display_refresh_by_label():
    snapshot = AssistantSnapshot(
        timestamp=datetime.now(),
        displays=[{
            "name": r"\\.\DISPLAY1",
            "label": "Dell Gaming",
            "primary": True,
            "supported_rates": [60, 144],
        }],
    )

    action, message = skill_request_to_action({
        "type": "skill_request",
        "skill": "set_display_refresh_rate",
        "arguments": {"display_label": "dell", "hz": 144},
    }, snapshot)

    assert message == ""
    assert action.kind == "set_display_refresh_rate"
    assert action.payload == {"device_name": r"\\.\DISPLAY1", "hz": 144}


def test_skill_request_to_action_rejects_ambiguous_audio_target():
    snapshot = AssistantSnapshot(
        timestamp=datetime.now(),
        audio_sessions=[
            {"pid": 1, "process_name": "chrome.exe", "display_name": "Chrome One"},
            {"pid": 2, "process_name": "chrome.exe", "display_name": "Chrome Two"},
        ],
    )

    action, message = skill_request_to_action({
        "type": "skill_request",
        "skill": "set_app_volume",
        "arguments": {"app": "chrome", "level": 0.2},
    }, snapshot)

    assert action is None
    assert "More than one" in message


def test_skill_request_to_action_for_audio_volume_mute_route_and_layout():
    snapshot = AssistantSnapshot(
        timestamp=datetime.now(),
        audio_devices=[{"id": "dev-1", "name": "Speakers"}],
        audio_sessions=[{"pid": 12, "process_name": "music.exe", "display_name": "Music"}],
        saved_layouts=[{"id": "layout-1", "name": "Work", "windows": 2, "displays": 1}],
    )

    volume, _ = skill_request_to_action({
        "type": "skill_request",
        "skill": "set_app_volume",
        "arguments": {"app": "music", "level": 0.4},
    }, snapshot)
    mute, _ = skill_request_to_action({
        "type": "skill_request",
        "skill": "mute_app_audio",
        "arguments": {"app": "music", "muted": True},
    }, snapshot)
    route, _ = skill_request_to_action({
        "type": "skill_request",
        "skill": "route_app_audio",
        "arguments": {"app": "music", "device_name": "speaker"},
    }, snapshot)
    layout, _ = skill_request_to_action({
        "type": "skill_request",
        "skill": "load_saved_layout",
        "arguments": {"layout_name": "work"},
    }, snapshot)

    assert volume.kind == "audio_set_volume"
    assert volume.payload == {"pid": 12, "level": 0.4}
    assert mute.kind == "audio_mute_session"
    assert mute.payload == {"pid": 12, "muted": True}
    assert route.kind == "audio_route_session"
    assert route.payload == {"pid": 12, "process_name": "music.exe", "device_id": "dev-1"}
    assert layout.kind == "load_saved_layout"
    assert layout.payload == {"layout_id": "layout-1"}


def test_dedupe_actions_uses_kind_and_payload():
    first = AssistantAction("1", "refresh_network", "A", "A", READ_ONLY, payload={})
    duplicate = AssistantAction("2", "refresh_network", "B", "B", READ_ONLY, payload={})
    other = AssistantAction("3", "refresh_network", "C", "C", READ_ONLY, payload={"x": 1})

    assert dedupe_actions([first, duplicate, other]) == [first, other]


def test_detect_skill_domains_windows_updates_excludes_layouts():
    from app.assistant_core import detect_skill_domains

    domains = detect_skill_domains("check windows updates")

    assert "layouts" not in domains
    assert "security" in domains


def test_detect_skill_domains_still_matches_layout_intents():
    from app.assistant_core import detect_skill_domains

    assert "layouts" in detect_skill_domains("arrange my windows")
    assert "layouts" in detect_skill_domains("restore my window layout")
    assert "layouts" in detect_skill_domains("save this desktop layout")
