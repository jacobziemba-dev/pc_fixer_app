from datetime import datetime
from unittest.mock import MagicMock, patch

from app.assistant_core import (
    ASSISTANT_TOOLS,
    AssistantAction,
    AssistantSnapshot,
    MEDIUM_RISK,
    READ_ONLY,
    collect_assistant_snapshot,
    execute_assistant_action,
    get_assistant_tools,
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
