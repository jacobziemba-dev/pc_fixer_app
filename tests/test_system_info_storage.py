from app import system_info as sysinfo


def test_scan_folder_size_breakdown_orders_by_size(tmp_path, monkeypatch):
    big = tmp_path / "Big"
    small = tmp_path / "Small"
    big.mkdir()
    small.mkdir()
    (big / "a.bin").write_bytes(b"x" * 5000)
    (small / "b.bin").write_bytes(b"x" * 100)
    monkeypatch.setattr(sysinfo, "resolve_storage_scan_roots", lambda roots=None: [str(tmp_path)])

    entries = sysinfo.scan_folder_size_breakdown(roots=[tmp_path], max_entries=10)

    assert entries
    assert entries[0]["name"] == "Big"
    assert entries[0]["size_bytes"] >= entries[-1]["size_bytes"]


def test_find_duplicate_files_groups_by_hash(tmp_path, monkeypatch):
    payload = b"z" * (1024 * 1024)
    (tmp_path / "one.bin").write_bytes(payload)
    (tmp_path / "two.bin").write_bytes(payload)
    (tmp_path / "three.bin").write_bytes(b"w" * (1024 * 1024))
    monkeypatch.setattr(sysinfo, "resolve_storage_scan_roots", lambda roots=None: [str(tmp_path)])

    groups = sysinfo.find_duplicate_files(roots=[tmp_path], min_size_mb=1, limit_groups=10)

    assert len(groups) == 1
    assert groups[0]["count"] == 2
    assert {str(tmp_path / "one.bin"), str(tmp_path / "two.bin")} == set(groups[0]["paths"])


def test_is_process_termination_allowed_blocks_protected_names():
    ok, message = sysinfo.is_process_termination_allowed(100, "explorer.exe")
    assert ok is False
    assert "protected" in message.lower()


def test_is_process_termination_allowed_blocks_system_pid():
    ok, message = sysinfo.is_process_termination_allowed(4, "System")
    assert ok is False
    assert "protected" in message.lower()


def test_set_startup_folder_item_disable_and_enable(tmp_path, monkeypatch):
    shortcut = tmp_path / "DemoApp.lnk"
    shortcut.write_text("shortcut", encoding="utf-8")
    monkeypatch.setattr(sysinfo, "_STARTUP_FOLDERS", [str(tmp_path)])
    monkeypatch.setattr(sysinfo, "_load_disabled_run_items", lambda: [])

    items = sysinfo.get_startup_items()
    assert any(item["name"] == "DemoApp.lnk" and item["enabled"] for item in items)

    ok, message = sysinfo.set_startup_item_enabled("DemoApp.lnk", "Startup folder", False)
    assert ok is True
    assert (tmp_path / f"DemoApp.lnk{sysinfo._DISABLED_STARTUP_SUFFIX}").exists()
    assert "Disabled" in message

    ok, message = sysinfo.set_startup_item_enabled("DemoApp.lnk", "Startup folder", True)
    assert ok is True
    assert shortcut.exists()
    assert "Enabled" in message
