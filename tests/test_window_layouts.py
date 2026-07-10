from app import window_layouts


def test_layout_json_save_load_round_trip(tmp_path):
    path = tmp_path / "window_layouts.json"
    layouts = [{
        "id": "layout-1",
        "name": "Work",
        "created_at": "2026-07-10T12:00:00",
        "updated_at": "2026-07-10T12:00:00",
        "windows": [{"title": "Editor", "exe_path": r"C:\Apps\editor.exe"}],
    }]

    window_layouts.save_layouts(layouts, str(path))

    assert window_layouts.load_layouts(str(path)) == layouts


def test_rect_relative_conversion_round_trip():
    monitor = {"left": 100, "top": 50, "right": 2020, "bottom": 1130}
    window = {"left": 580, "top": 320, "right": 1540, "bottom": 860}

    relative = window_layouts.rect_to_relative(window, monitor)

    assert window_layouts.relative_to_rect(relative, monitor) == window


def test_choose_monitor_falls_back_to_primary_when_saved_display_missing():
    saved = {
        "monitor_device": r"\\.\DISPLAY9",
        "monitor_rect": {"left": 0, "top": 0, "right": 800, "bottom": 600},
    }
    monitors = [
        {
            "device": r"\\.\DISPLAY2",
            "is_primary": False,
            "work_rect": {"left": 1920, "top": 0, "right": 3840, "bottom": 1080},
        },
        {
            "device": r"\\.\DISPLAY1",
            "is_primary": True,
            "work_rect": {"left": 0, "top": 0, "right": 1920, "bottom": 1040},
        },
    ]

    assert window_layouts.choose_monitor_rect(saved, monitors) == monitors[1]["work_rect"]


def test_normal_window_filter_skips_bad_candidates():
    base = {
        "visible": True,
        "iconic": False,
        "cloaked": False,
        "title": "Good Window",
        "pid": 10,
        "class_name": "ApplicationFrameWindow",
        "ex_style": 0,
        "rect": {"left": 0, "top": 0, "right": 800, "bottom": 600},
    }

    assert window_layouts.is_normal_window_info(base, self_pid=99)

    for override in (
        {"visible": False},
        {"iconic": True},
        {"cloaked": True},
        {"title": ""},
        {"pid": 99},
        {"class_name": "Shell_TrayWnd"},
        {"ex_style": window_layouts.win32con.WS_EX_TOOLWINDOW},
        {"rect": {"left": 0, "top": 0, "right": 40, "bottom": 40}},
    ):
        candidate = dict(base)
        candidate.update(override)
        assert not window_layouts.is_normal_window_info(candidate, self_pid=99)


def test_find_best_window_prefers_executable_path_before_title():
    saved = {
        "exe_path": r"C:\Apps\editor.exe",
        "title": "Project Notes",
    }
    candidates = [
        {
            "hwnd": 1,
            "exe_path": r"C:\Other\browser.exe",
            "title": "Project Notes",
        },
        {
            "hwnd": 2,
            "exe_path": r"C:\Apps\editor.exe",
            "title": "Different File",
        },
    ]

    assert window_layouts.find_best_window(saved, candidates)["hwnd"] == 2


def test_merge_layout_items_keeps_saved_first_and_dedupes():
    saved = [{
        "exe_path": r"C:\Apps\editor.exe",
        "title": "Project Notes",
        "monitor_device": r"\\.\DISPLAY1",
        "window_rect": {"left": 0, "top": 0, "right": 800, "bottom": 600},
    }]
    current = [
        dict(saved[0]),
        {
            "exe_path": r"C:\Apps\browser.exe",
            "title": "Docs",
            "monitor_device": r"\\.\DISPLAY1",
            "window_rect": {"left": 800, "top": 0, "right": 1600, "bottom": 600},
        },
    ]

    merged = window_layouts.merge_layout_items(saved, current)

    assert merged == [saved[0], current[1]]


def test_build_layout_preserves_identity_when_editing():
    layout = window_layouts.build_layout(
        "Work",
        [{"title": "Editor"}],
        layout_id="layout-1",
        created_at="2026-07-10T12:00:00",
    )

    assert layout["id"] == "layout-1"
    assert layout["created_at"] == "2026-07-10T12:00:00"
    assert layout["name"] == "Work"
    assert layout["windows"] == [{"title": "Editor"}]


def test_missing_windows_accounts_for_duplicate_app_windows():
    layout = {
        "windows": [
            {"exe_path": r"C:\Apps\editor.exe", "title": "File One"},
            {"exe_path": r"C:\Apps\editor.exe", "title": "File Two"},
        ],
    }
    candidates = [
        {"hwnd": 10, "exe_path": r"C:\Apps\editor.exe", "title": "File One"},
    ]

    missing = window_layouts.missing_windows_for_layout(layout, candidates)

    assert missing == [layout["windows"][1]]
