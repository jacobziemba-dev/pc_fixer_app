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
        {
            "exe_path": r"C:\Apps\editor.exe",
            "title": "Project Notes",
            "monitor_device": r"\\.\DISPLAY1",
            "window_rect": {"left": 20, "top": 20, "right": 900, "bottom": 650},
        },
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
    displays = [{
        "device": r"\\.\DISPLAY1",
        "monitor_rect": {"left": 0, "top": 0, "right": 1920, "bottom": 1080},
        "work_rect": {"left": 0, "top": 0, "right": 1920, "bottom": 1040},
        "is_primary": True,
    }]
    layout = window_layouts.build_layout(
        "Work",
        [{"title": "Editor"}],
        layout_id="layout-1",
        created_at="2026-07-10T12:00:00",
        displays=displays,
    )

    assert layout["id"] == "layout-1"
    assert layout["created_at"] == "2026-07-10T12:00:00"
    assert layout["name"] == "Work"
    assert layout["displays"] == displays
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


def test_preview_scene_builds_single_saved_monitor():
    layout = {
        "windows": [{
            "title": "Editor",
            "process_name": "editor.exe",
            "monitor_device": r"\\.\DISPLAY1",
            "monitor_rect": {"left": 0, "top": 0, "right": 1920, "bottom": 1080},
            "window_rect": {"left": 0, "top": 0, "right": 960, "bottom": 540},
        }],
    }

    scene = window_layouts.build_preview_scene(layout, 960, 540, padding=0)

    assert len(scene["monitors"]) == 1
    assert len(scene["windows"]) == 1
    assert scene["monitors"][0]["preview_rect"] == {"x": 0, "y": 0, "width": 960, "height": 540}
    assert scene["windows"][0]["preview_rect"] == {"x": 0, "y": 0, "width": 480, "height": 270}


def test_preview_scene_preserves_negative_monitor_coordinates():
    layout = {
        "windows": [
            {
                "title": "Chat",
                "monitor_device": r"\\.\DISPLAY2",
                "monitor_rect": {"left": -1280, "top": 0, "right": 0, "bottom": 720},
                "window_rect": {"left": -1280, "top": 0, "right": -640, "bottom": 720},
            },
            {
                "title": "Editor",
                "monitor_device": r"\\.\DISPLAY1",
                "monitor_rect": {"left": 0, "top": 0, "right": 1920, "bottom": 1080},
                "window_rect": {"left": 0, "top": 0, "right": 960, "bottom": 540},
            },
        ],
    }

    scene = window_layouts.build_preview_scene(layout, 3200, 1080, padding=0)

    monitors = {monitor["device"]: monitor["preview_rect"] for monitor in scene["monitors"]}
    assert monitors[r"\\.\DISPLAY2"]["x"] == 0
    assert monitors[r"\\.\DISPLAY1"]["x"] == 1280


def test_preview_scene_handles_missing_monitor_data():
    layout = {
        "windows": [{
            "title": "Untitled",
            "window_rect": {"left": 20, "top": 30, "right": 420, "bottom": 330},
        }],
    }

    scene = window_layouts.build_preview_scene(layout, 800, 600, padding=20)

    assert len(scene["monitors"]) == 1
    assert len(scene["windows"]) == 1
    assert scene["desktop_rect"] == {"left": 20, "top": 30, "right": 420, "bottom": 330}


def test_preview_scene_uses_saved_displays_even_without_windows():
    layout = {
        "displays": [
            {
                "device": r"\\.\DISPLAY1",
                "monitor_rect": {"left": 0, "top": 0, "right": 1920, "bottom": 1080},
            },
            {
                "device": r"\\.\DISPLAY2",
                "monitor_rect": {"left": 1920, "top": 0, "right": 3840, "bottom": 1080},
            },
        ],
        "windows": [{
            "title": "Editor",
            "process_name": "editor.exe",
            "monitor_device": r"\\.\DISPLAY1",
            "monitor_rect": {"left": 0, "top": 0, "right": 1920, "bottom": 1080},
            "window_rect": {"left": 0, "top": 0, "right": 960, "bottom": 540},
        }],
    }

    scene = window_layouts.build_preview_scene(layout, 3840, 1080, padding=0)

    assert [monitor["device"] for monitor in scene["monitors"]] == [r"\\.\DISPLAY1", r"\\.\DISPLAY2"]
    assert len(scene["windows"]) == 1
    assert scene["monitors"][1]["preview_rect"]["x"] == 1920


def test_build_layout_derives_displays_from_windows_for_legacy_callers():
    layout = window_layouts.build_layout(
        "Legacy",
        [{
            "title": "Editor",
            "monitor_device": r"\\.\DISPLAY1",
            "monitor_rect": {"left": 0, "top": 0, "right": 1920, "bottom": 1080},
        }],
    )

    assert layout["displays"] == [{
        "device": r"\\.\DISPLAY1",
        "is_primary": False,
        "monitor_rect": {"left": 0, "top": 0, "right": 1920, "bottom": 1080},
        "work_rect": {"left": 0, "top": 0, "right": 1920, "bottom": 1080},
    }]


def test_update_layout_item_rect_refreshes_relative_rect():
    item = {
        "title": "Editor",
        "monitor_rect": {"left": 0, "top": 0, "right": 1000, "bottom": 500},
        "window_rect": {"left": 0, "top": 0, "right": 100, "bottom": 100},
        "relative_rect": {"x": 0, "y": 0, "width": 0.1, "height": 0.2},
    }

    updated = window_layouts.update_layout_item_rect(
        item,
        {"left": 100, "top": 50, "right": 600, "bottom": 300},
    )

    assert updated["window_rect"] == {"left": 100, "top": 50, "right": 600, "bottom": 300}
    assert updated["relative_rect"] == {"x": 0.1, "y": 0.1, "width": 0.5, "height": 0.5}
    assert item["window_rect"] == {"left": 0, "top": 0, "right": 100, "bottom": 100}
