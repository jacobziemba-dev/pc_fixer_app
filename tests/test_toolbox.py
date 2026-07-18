from app import toolbox, tool_history


def test_windows_only_result_for_non_windows(monkeypatch):
    monkeypatch.setattr(toolbox, "is_windows", lambda: False)

    result = toolbox.check_windows_updates()

    assert result.success is False
    assert "Windows" in result.summary


def test_check_power_plan_uses_fixed_powercfg_command(monkeypatch):
    calls = []

    def fake_run(args, timeout=30):
        calls.append(args)
        if args == ["powercfg", "/GETACTIVESCHEME"]:
            return 0, "Power Scheme GUID: abc (Balanced)", ""
        return 0, "Existing Power Schemes", ""

    monkeypatch.setattr(toolbox, "is_windows", lambda: True)
    monkeypatch.setattr(toolbox, "_run_command", fake_run)

    result = toolbox.check_power_plan()

    assert result.success is True
    assert ["powercfg", "/GETACTIVESCHEME"] in calls
    assert ["powercfg", "/LIST"] in calls


def test_set_power_plan_rejects_unknown_plan(monkeypatch):
    monkeypatch.setattr(toolbox, "is_windows", lambda: True)

    result = toolbox.set_power_plan("maximum chaos")

    assert result.success is False
    assert "Unsupported" in result.summary


def test_review_startup_impact_classifies_items(monkeypatch):
    monkeypatch.setattr(
        toolbox.sysinfo,
        "get_startup_items",
        lambda: [
            {"name": "Steam", "command": "steam.exe", "source": "HKCU"},
            {"name": "Audio Driver", "command": "audio.exe", "source": "HKLM"},
        ],
    )

    result = toolbox.review_startup_impact()

    assert result.success is True
    assert any(line.startswith("Optional: Steam") for line in result.details)
    assert any(line.startswith("Keep: Audio Driver") for line in result.details)


def test_scan_large_files_is_read_only_and_reports_matches(tmp_path):
    big = tmp_path / "big.bin"
    small = tmp_path / "small.bin"
    big.write_bytes(b"x" * (2 * 1024 * 1024))
    small.write_bytes(b"x")

    result = toolbox.scan_large_files(root=tmp_path, min_size_mb=1, limit=5)

    assert result.success is True
    assert any("big.bin" in line for line in result.details)
    assert not any("small.bin" in line for line in result.details)
    assert big.exists()
    assert small.exists()


def test_scan_folder_sizes_reports_child_folders(tmp_path, monkeypatch):
    child = tmp_path / "Videos"
    child.mkdir()
    (child / "clip.bin").write_bytes(b"x" * 2048)
    monkeypatch.setattr(toolbox.sysinfo, "resolve_storage_scan_roots", lambda roots=None: [str(tmp_path)])

    result = toolbox.scan_folder_sizes(roots=[tmp_path], max_entries=10)

    assert result.success is True
    assert any("Videos" in line for line in result.details)


def test_scan_duplicate_files_groups_identical_copies(tmp_path, monkeypatch):
    payload = b"x" * (1024 * 1024)
    first = tmp_path / "a.bin"
    second = tmp_path / "b.bin"
    other = tmp_path / "c.bin"
    first.write_bytes(payload)
    second.write_bytes(payload)
    other.write_bytes(b"y" * (1024 * 1024))
    monkeypatch.setattr(toolbox.sysinfo, "resolve_storage_scan_roots", lambda roots=None: [str(tmp_path)])

    result = toolbox.scan_duplicate_files(roots=[tmp_path], min_size_mb=1, limit_groups=10)

    assert result.success is True
    assert "duplicate group" in result.summary.lower()
    assert first.exists() and second.exists() and other.exists()


def test_end_process_rejects_protected_names(monkeypatch):
    monkeypatch.setattr(
        toolbox.sysinfo,
        "terminate_process",
        lambda pid: (False, "explorer.exe is protected and cannot be ended."),
    )

    result = toolbox.end_process(1234)

    assert result.success is False
    assert "protected" in result.summary.lower()


def test_open_windows_settings_rejects_unknown_page(monkeypatch):
    monkeypatch.setattr(toolbox, "is_windows", lambda: True)

    result = toolbox.open_windows_settings("registry_editor")

    assert result.success is False
    assert "Unsupported" in result.summary


def test_open_known_folder_rejects_unknown_key(monkeypatch):
    monkeypatch.setattr(toolbox, "is_windows", lambda: True)

    result = toolbox.open_known_folder("C:\\Windows\\System32")

    assert result.success is False
    assert "Unsupported" in result.summary


def test_renew_ip_uses_fixed_ipconfig_commands(monkeypatch):
    calls = []

    def fake_run(args, timeout=30):
        calls.append(args)
        return 0, "ok", ""

    monkeypatch.setattr(toolbox, "is_windows", lambda: True)
    monkeypatch.setattr(toolbox, "_run_command", fake_run)

    result = toolbox.renew_ip_address()

    assert result.success is True
    assert ["ipconfig", "/release"] in calls
    assert ["ipconfig", "/renew"] in calls


def test_reset_winsock_uses_fixed_netsh_command(monkeypatch):
    calls = []

    def fake_run(args, timeout=30):
        calls.append(args)
        return 0, "reset ok", ""

    monkeypatch.setattr(toolbox, "is_windows", lambda: True)
    monkeypatch.setattr(toolbox, "_run_command", fake_run)

    result = toolbox.reset_winsock()

    assert result.success is True
    assert ["netsh", "winsock", "reset"] in calls
    assert any("reboot" in line.lower() for line in result.details)


def test_open_system_tool_rejects_unknown_key(monkeypatch):
    monkeypatch.setattr(toolbox, "is_windows", lambda: True)

    result = toolbox.open_system_tool("regedit")

    assert result.success is False
    assert "Unsupported" in result.summary


def test_open_system_tool_allows_services_and_disk_cleanup(monkeypatch):
    monkeypatch.setattr(toolbox, "is_windows", lambda: True)
    started = []

    def fake_startfile(path):
        started.append(path)

    monkeypatch.setattr(toolbox.os, "startfile", fake_startfile)
    monkeypatch.setattr(toolbox, "_run_command", lambda args, timeout=10: (0, "", ""))

    services = toolbox.open_system_tool("services")
    cleanup = toolbox.open_system_tool("disk_cleanup")

    assert services.success is True
    assert cleanup.success is True
    assert "services.msc" in started


def test_check_service_status_rejects_unknown_key(monkeypatch):
    monkeypatch.setattr(toolbox, "is_windows", lambda: True)

    result = toolbox.check_service_status("not_a_real_service")

    assert result.success is False
    assert "allowlist" in result.summary.lower()


def test_open_windows_troubleshooter_rejects_unknown_key(monkeypatch):
    monkeypatch.setattr(toolbox, "is_windows", lambda: True)

    result = toolbox.open_windows_troubleshooter("everything")

    assert result.success is False
    assert "allowlist" in result.summary.lower()


def test_check_component_store_health_uses_fixed_dism(monkeypatch):
    calls = []

    def fake_run(args, timeout=30):
        calls.append(args)
        return 0, "No component store corruption detected.", ""

    monkeypatch.setattr(toolbox, "is_windows", lambda: True)
    monkeypatch.setattr(toolbox, "_run_command", fake_run)

    result = toolbox.check_component_store_health()

    assert result.success is True
    assert calls == [["DISM.exe", "/Online", "/Cleanup-Image", "/CheckHealth"]]


def test_scan_volume_errors_uses_scan_only(monkeypatch):
    calls = []

    def fake_run(args, timeout=30):
        calls.append(args)
        return 0, "Windows has scanned the file system and found no problems.", ""

    monkeypatch.setattr(toolbox, "is_windows", lambda: True)
    monkeypatch.setattr(toolbox, "_run_command", fake_run)
    monkeypatch.setattr(
        toolbox.sysinfo,
        "get_disk_usage",
        lambda: [{"mountpoint": "C:\\", "total": 1, "used": 1, "free": 1, "percent": 50}],
    )

    result = toolbox.scan_volume_errors("C")

    assert result.success is True
    assert calls == [["chkdsk.exe", "C:", "/scan"]]


def test_restart_print_spooler_uses_fixed_service(monkeypatch):
    calls = []

    def fake_ps(command, timeout=30):
        calls.append(command)
        return 0, "ok", ""

    monkeypatch.setattr(toolbox, "is_windows", lambda: True)
    monkeypatch.setattr(toolbox, "_run_powershell", fake_ps)

    result = toolbox.restart_print_spooler()

    assert result.success is True
    assert "Restart-Service -Name Spooler" in calls[0]


def test_tool_history_records_result():
    tool_history.clear()
    result = toolbox.ToolResult(True, "Check", "All good", ["detail"])

    entry = tool_history.add_result(result)

    assert entry.title == "Check"
    assert tool_history.entries()[0].summary == "All good"
