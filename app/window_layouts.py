"""Capture, persist, and apply Windows app window layouts."""
import json
import os
import subprocess
import time
import uuid
from dataclasses import dataclass
from datetime import datetime

import psutil
import win32api
import win32con
import win32gui
import win32process


APP_DATA_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "PC Fix")
LAYOUTS_PATH = os.path.join(APP_DATA_DIR, "window_layouts.json")
LAYOUT_SCHEMA_VERSION = 1

MIN_WINDOW_WIDTH = 80
MIN_WINDOW_HEIGHT = 60
PREVIEW_FALLBACK_MONITOR = {"left": 0, "top": 0, "right": 1280, "bottom": 720}

_SKIPPED_CLASSES = {
    "Progman",
    "WorkerW",
    "Shell_TrayWnd",
    "Shell_SecondaryTrayWnd",
    "DV2ControlHost",
    "MsgrIMEWindowClass",
    "SysShadow",
}


@dataclass
class LayoutApplyResult:
    moved: int
    launched: list
    missing: list
    errors: list


def _now_iso():
    return datetime.now().replace(microsecond=0).isoformat()


def normalize_exe_path(path):
    return os.path.normcase(os.path.abspath(path or "")) if path else ""


def default_layouts_path():
    return LAYOUTS_PATH


def load_layouts(path=None):
    path = path or LAYOUTS_PATH
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return []
    if isinstance(data, list):
        return data
    if not isinstance(data, dict):
        return []
    if data.get("version") != LAYOUT_SCHEMA_VERSION:
        return data.get("layouts", [])
    layouts = data.get("layouts", [])
    return layouts if isinstance(layouts, list) else []


def save_layouts(layouts, path=None):
    path = path or LAYOUTS_PATH
    os.makedirs(os.path.dirname(path), exist_ok=True)
    payload = {"version": LAYOUT_SCHEMA_VERSION, "layouts": layouts}
    temp_path = f"{path}.tmp"
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    os.replace(temp_path, path)


def rect_width(rect):
    return int(rect["right"]) - int(rect["left"])


def rect_height(rect):
    return int(rect["bottom"]) - int(rect["top"])


def is_rect(rect):
    return (
        isinstance(rect, dict)
        and {"left", "top", "right", "bottom"}.issubset(rect)
        and rect_width(rect) > 0
        and rect_height(rect) > 0
    )


def union_rect(rects):
    valid_rects = [rect for rect in rects if is_rect(rect)]
    if not valid_rects:
        return dict(PREVIEW_FALLBACK_MONITOR)
    return {
        "left": min(int(rect["left"]) for rect in valid_rects),
        "top": min(int(rect["top"]) for rect in valid_rects),
        "right": max(int(rect["right"]) for rect in valid_rects),
        "bottom": max(int(rect["bottom"]) for rect in valid_rects),
    }


def rect_to_relative(window_rect, monitor_rect):
    monitor_width = max(rect_width(monitor_rect), 1)
    monitor_height = max(rect_height(monitor_rect), 1)
    return {
        "x": (int(window_rect["left"]) - int(monitor_rect["left"])) / monitor_width,
        "y": (int(window_rect["top"]) - int(monitor_rect["top"])) / monitor_height,
        "width": rect_width(window_rect) / monitor_width,
        "height": rect_height(window_rect) / monitor_height,
    }


def relative_to_rect(relative_rect, monitor_rect):
    monitor_width = max(rect_width(monitor_rect), 1)
    monitor_height = max(rect_height(monitor_rect), 1)
    width = min(max(int(round(float(relative_rect["width"]) * monitor_width)), MIN_WINDOW_WIDTH), monitor_width)
    height = min(max(int(round(float(relative_rect["height"]) * monitor_height)), MIN_WINDOW_HEIGHT), monitor_height)
    left = int(round(int(monitor_rect["left"]) + float(relative_rect["x"]) * monitor_width))
    top = int(round(int(monitor_rect["top"]) + float(relative_rect["y"]) * monitor_height))
    max_left = int(monitor_rect["right"]) - width
    max_top = int(monitor_rect["bottom"]) - height
    left = min(max(left, int(monitor_rect["left"])), max_left)
    top = min(max(top, int(monitor_rect["top"])), max_top)
    return {"left": left, "top": top, "right": left + width, "bottom": top + height}


def update_layout_item_rect(item, window_rect):
    updated = dict(item)
    updated["window_rect"] = {
        "left": int(window_rect["left"]),
        "top": int(window_rect["top"]),
        "right": int(window_rect["right"]),
        "bottom": int(window_rect["bottom"]),
    }
    monitor_rect = updated.get("monitor_rect")
    if is_rect(monitor_rect):
        updated["relative_rect"] = rect_to_relative(updated["window_rect"], monitor_rect)
    return updated


def saved_monitor_rects_for_layout(layout):
    display_monitors = []
    seen_displays = set()
    for display in layout.get("displays", []) or []:
        monitor_rect = display.get("monitor_rect") or display.get("rect")
        if not is_rect(monitor_rect):
            continue
        key = (
            display.get("device", ""),
            int(monitor_rect["left"]),
            int(monitor_rect["top"]),
            int(monitor_rect["right"]),
            int(monitor_rect["bottom"]),
        )
        if key in seen_displays:
            continue
        seen_displays.add(key)
        display_monitors.append({
            "device": display.get("device", "") or f"Display {len(display_monitors) + 1}",
            "rect": monitor_rect,
            "is_primary": bool(display.get("is_primary")),
        })
    if display_monitors:
        return display_monitors

    monitors = []
    seen = set()
    for item in layout.get("windows", []):
        monitor_rect = item.get("monitor_rect")
        if not is_rect(monitor_rect):
            continue
        key = (
            item.get("monitor_device", ""),
            int(monitor_rect["left"]),
            int(monitor_rect["top"]),
            int(monitor_rect["right"]),
            int(monitor_rect["bottom"]),
        )
        if key in seen:
            continue
        seen.add(key)
        monitors.append({
            "device": item.get("monitor_device", "") or f"Display {len(monitors) + 1}",
            "rect": monitor_rect,
            "is_primary": False,
        })
    if monitors:
        return monitors
    if not layout.get("windows"):
        return []
    return [{"device": "Saved Display", "rect": union_rect(
        item.get("window_rect") for item in layout.get("windows", [])
    ), "is_primary": False}]


def _preview_rect(rect, desktop_rect, scale, offset_x, offset_y):
    return {
        "x": int(round(offset_x + (int(rect["left"]) - int(desktop_rect["left"])) * scale)),
        "y": int(round(offset_y + (int(rect["top"]) - int(desktop_rect["top"])) * scale)),
        "width": max(int(round(rect_width(rect) * scale)), 1),
        "height": max(int(round(rect_height(rect) * scale)), 1),
    }


def _display_resolution_label(rect):
    return f"{rect_width(rect)} x {rect_height(rect)}" if is_rect(rect) else ""


def _int_or_none(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def build_preview_scene(layout, canvas_width, canvas_height, padding=24):
    monitors = saved_monitor_rects_for_layout(layout)
    desktop_rect = union_rect(monitor["rect"] for monitor in monitors)
    available_width = max(int(canvas_width) - padding * 2, 1)
    available_height = max(int(canvas_height) - padding * 2, 1)
    scale = min(
        available_width / max(rect_width(desktop_rect), 1),
        available_height / max(rect_height(desktop_rect), 1),
    )
    content_width = rect_width(desktop_rect) * scale
    content_height = rect_height(desktop_rect) * scale
    offset_x = int(round((int(canvas_width) - content_width) / 2))
    offset_y = int(round((int(canvas_height) - content_height) / 2))
    scene_monitors = []
    for index, monitor in enumerate(monitors, start=1):
        scene_monitors.append({
            "index": index,
            "label": f"Display {index}",
            "device": monitor["device"],
            "is_primary": bool(monitor.get("is_primary")),
            "resolution": _display_resolution_label(monitor["rect"]),
            "rect": monitor["rect"],
            "preview_rect": _preview_rect(monitor["rect"], desktop_rect, scale, offset_x, offset_y),
        })
    scene_windows = []
    has_z_order = False
    for source_index, item in enumerate(layout.get("windows", [])):
        window_rect = item.get("window_rect")
        if not is_rect(window_rect):
            monitor_rect = item.get("monitor_rect")
            relative_rect = item.get("relative_rect")
            if is_rect(monitor_rect) and relative_rect:
                window_rect = relative_to_rect(relative_rect, monitor_rect)
        if not is_rect(window_rect):
            continue
        z_order = _int_or_none(item.get("z_order"))
        has_z_order = has_z_order or z_order is not None
        scene_windows.append({
            "label": saved_window_label(item),
            "app": item.get("process_name") or item.get("exe_path") or "App",
            "monitor_device": item.get("monitor_device", ""),
            "z_order": z_order,
            "front_rank": None,
            "layer_label": "",
            "source_index": source_index,
            "rect": window_rect,
            "preview_rect": _preview_rect(window_rect, desktop_rect, scale, offset_x, offset_y),
        })
    if has_z_order:
        front_to_back = sorted(
            scene_windows,
            key=lambda window: (
                window["z_order"] if window["z_order"] is not None else window["source_index"],
                window["source_index"],
            ),
        )
        for rank, window in enumerate(front_to_back, start=1):
            window["front_rank"] = rank
            window["layer_label"] = "Top" if rank == 1 else f"Layer {rank}"
        scene_windows = list(reversed(front_to_back))
    return {
        "desktop_rect": desktop_rect,
        "scale": scale,
        "monitors": scene_monitors,
        "windows": scene_windows,
    }


def _rect_from_tuple(rect):
    left, top, right, bottom = rect
    return {"left": int(left), "top": int(top), "right": int(right), "bottom": int(bottom)}


def _rect_center(rect):
    return (
        int(rect["left"]) + rect_width(rect) // 2,
        int(rect["top"]) + rect_height(rect) // 2,
    )


def _monitor_rect_from_info(info):
    return _rect_from_tuple(info["Monitor"])


def _work_rect_from_info(info):
    return _rect_from_tuple(info.get("Work") or info["Monitor"])


def get_monitor_layouts():
    monitors = []
    for handle, _hdc, _rect in win32api.EnumDisplayMonitors():
        info = win32api.GetMonitorInfo(handle)
        primary_flag = getattr(win32con, "MONITORINFOF_PRIMARY", 1)
        monitors.append({
            "device": info.get("Device", ""),
            "is_primary": bool(info.get("Flags", 0) & primary_flag),
            "monitor_rect": _monitor_rect_from_info(info),
            "work_rect": _work_rect_from_info(info),
        })
    monitors.sort(key=lambda item: (not item["is_primary"], item["device"]))
    return monitors


def collect_current_display_items():
    return [
        {
            "device": monitor.get("device", ""),
            "is_primary": bool(monitor.get("is_primary")),
            "monitor_rect": monitor.get("monitor_rect", {}),
            "work_rect": monitor.get("work_rect", {}),
        }
        for monitor in get_monitor_layouts()
    ]


def choose_monitor_rect(saved_window, current_monitors):
    if not current_monitors:
        return saved_window.get("monitor_rect") or {"left": 0, "top": 0, "right": 1280, "bottom": 720}
    target_device = saved_window.get("monitor_device", "")
    for monitor in current_monitors:
        if monitor.get("device") == target_device:
            return monitor.get("work_rect") or monitor.get("monitor_rect")
    primary = next((monitor for monitor in current_monitors if monitor.get("is_primary")), current_monitors[0])
    return primary.get("work_rect") or primary.get("monitor_rect")


def monitor_for_rect(window_rect, monitors):
    center_x, center_y = _rect_center(window_rect)
    for monitor in monitors:
        rect = monitor["monitor_rect"]
        if rect["left"] <= center_x < rect["right"] and rect["top"] <= center_y < rect["bottom"]:
            return monitor
    return next((monitor for monitor in monitors if monitor["is_primary"]), monitors[0] if monitors else None)


def _window_is_cloaked(hwnd):
    try:
        import ctypes
        value = ctypes.c_int(0)
        dwmapi = ctypes.WinDLL("dwmapi")
        if dwmapi.DwmGetWindowAttribute(hwnd, 14, ctypes.byref(value), ctypes.sizeof(value)) == 0:
            return value.value != 0
    except Exception:
        return False
    return False


def is_normal_window_info(info, self_pid=None):
    if not info.get("visible"):
        return False
    if info.get("iconic"):
        return False
    if info.get("cloaked"):
        return False
    if not str(info.get("title") or "").strip():
        return False
    if self_pid is not None and info.get("pid") == self_pid:
        return False
    if info.get("class_name") in _SKIPPED_CLASSES:
        return False
    ex_style = int(info.get("ex_style") or 0)
    if ex_style & win32con.WS_EX_TOOLWINDOW:
        return False
    rect = info.get("rect") or {}
    if not {"left", "top", "right", "bottom"}.issubset(rect):
        return False
    if rect_width(rect) < MIN_WINDOW_WIDTH or rect_height(rect) < MIN_WINDOW_HEIGHT:
        return False
    return True


def _process_exe(pid):
    try:
        return psutil.Process(pid).exe()
    except (psutil.NoSuchProcess, psutil.AccessDenied, OSError):
        return ""


def enumerate_app_windows(include_self=False):
    windows = []
    self_pid = os.getpid()

    def callback(hwnd, _extra):
        try:
            _thread_id, pid = win32process.GetWindowThreadProcessId(hwnd)
            rect = _rect_from_tuple(win32gui.GetWindowRect(hwnd))
            info = {
                "hwnd": hwnd,
                "title": win32gui.GetWindowText(hwnd),
                "class_name": win32gui.GetClassName(hwnd),
                "pid": pid,
                "exe_path": _process_exe(pid),
                "visible": win32gui.IsWindowVisible(hwnd),
                "iconic": win32gui.IsIconic(hwnd),
                "cloaked": _window_is_cloaked(hwnd),
                "ex_style": win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE),
                "rect": rect,
            }
        except Exception:
            return True
        if is_normal_window_info(info, None if include_self else self_pid):
            info["z_order"] = len(windows)
            windows.append(info)
        return True

    win32gui.EnumWindows(callback, None)
    return windows


def capture_current_layout(name):
    return build_layout(name, collect_current_window_items(), displays=collect_current_display_items())


def _window_to_layout_item(window, monitor):
    return {
        "title": window["title"],
        "exe_path": window["exe_path"],
        "process_name": os.path.basename(window["exe_path"]) if window["exe_path"] else "",
        "monitor_device": monitor["device"],
        "monitor_rect": monitor["monitor_rect"],
        "window_rect": window["rect"],
        "relative_rect": rect_to_relative(window["rect"], monitor["monitor_rect"]),
        "z_order": window.get("z_order"),
    }


def layout_item_key(item):
    rect = item.get("window_rect") or {}
    rect_key = (
        rect.get("left", ""),
        rect.get("top", ""),
        rect.get("right", ""),
        rect.get("bottom", ""),
    )
    return (
        normalize_exe_path(item.get("exe_path")),
        str(item.get("title") or "").strip().lower(),
        str(item.get("monitor_device") or "").strip().lower(),
        rect_key,
    )


def layout_item_identity_key(item):
    return (
        normalize_exe_path(item.get("exe_path")),
        str(item.get("title") or "").strip().lower(),
        str(item.get("monitor_device") or "").strip().lower(),
    )


def collect_current_window_items():
    monitors = get_monitor_layouts()
    windows = []
    for window in enumerate_app_windows():
        monitor = monitor_for_rect(window["rect"], monitors)
        if not monitor:
            continue
        windows.append(_window_to_layout_item(window, monitor))
    return windows


def merge_layout_items(saved_items, current_items):
    merged = []
    seen = set()
    for item in list(saved_items or []) + list(current_items or []):
        key = layout_item_identity_key(item)
        if key in seen:
            continue
        seen.add(key)
        merged.append(item)
    return merged


def _display_from_window_item(item):
    monitor_rect = item.get("monitor_rect")
    if not is_rect(monitor_rect):
        return None
    return {
        "device": item.get("monitor_device", ""),
        "is_primary": False,
        "monitor_rect": monitor_rect,
        "work_rect": item.get("work_rect") or monitor_rect,
    }


def displays_from_windows(windows):
    displays = []
    seen = set()
    for item in windows or []:
        display = _display_from_window_item(item)
        if not display:
            continue
        rect = display["monitor_rect"]
        key = (
            display.get("device", ""),
            int(rect["left"]),
            int(rect["top"]),
            int(rect["right"]),
            int(rect["bottom"]),
        )
        if key in seen:
            continue
        seen.add(key)
        displays.append(display)
    return displays


def build_layout(name, windows, layout_id=None, created_at=None, displays=None):
    now = _now_iso()
    windows = list(windows)
    return {
        "id": layout_id or str(uuid.uuid4()),
        "name": name,
        "created_at": created_at or now,
        "updated_at": now,
        "displays": list(displays) if displays is not None else displays_from_windows(windows),
        "windows": windows,
    }


def find_best_window(saved_window, candidates, used_hwnds=None):
    used_hwnds = used_hwnds or set()
    target_path = normalize_exe_path(saved_window.get("exe_path"))
    title = str(saved_window.get("title") or "").strip().lower()

    path_matches = [
        window for window in candidates
        if window.get("hwnd") not in used_hwnds
        and target_path
        and normalize_exe_path(window.get("exe_path")) == target_path
    ]
    if path_matches:
        title_matches = [window for window in path_matches if title and title in window.get("title", "").lower()]
        return title_matches[0] if title_matches else path_matches[0]

    if title:
        for window in candidates:
            if window.get("hwnd") not in used_hwnds and title in window.get("title", "").lower():
                return window
    return None


def saved_window_label(saved_window):
    return (
        saved_window.get("title")
        or saved_window.get("process_name")
        or saved_window.get("exe_path")
        or "Unknown window"
    )


def missing_windows_for_layout(layout, candidates=None):
    candidates = enumerate_app_windows() if candidates is None else candidates
    used_hwnds = set()
    missing = []
    for saved_window in layout.get("windows", []):
        match = find_best_window(saved_window, candidates, used_hwnds)
        if match:
            used_hwnds.add(match["hwnd"])
        else:
            missing.append(saved_window)
    return missing


def _all_layout_windows_matched(layout, candidates):
    return not missing_windows_for_layout(layout, candidates)


def _running_paths():
    paths = set()
    for proc in psutil.process_iter(["exe"]):
        try:
            exe = proc.info.get("exe")
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
        if exe:
            paths.add(normalize_exe_path(exe))
    return paths


def missing_apps_for_layout(layout):
    running = _running_paths()
    missing = []
    seen = set()
    for item in layout.get("windows", []):
        exe_path = item.get("exe_path", "")
        key = normalize_exe_path(exe_path)
        if not key or key in running or key in seen:
            continue
        seen.add(key)
        missing.append(exe_path)
    return missing


def missing_launches_for_layout(layout):
    missing = []
    seen = set()
    for item in missing_windows_for_layout(layout):
        exe_path = item.get("exe_path", "")
        key = (normalize_exe_path(exe_path), saved_window_label(item))
        if not exe_path or key in seen:
            continue
        seen.add(key)
        missing.append(item)
    return missing


def _launch_missing_apps(paths):
    launched = []
    errors = []
    for exe_path in paths:
        if not exe_path or not os.path.exists(exe_path):
            errors.append(f"{exe_path or 'Unknown app'}: executable was not found")
            continue
        try:
            subprocess.Popen([exe_path], close_fds=True)
            launched.append(exe_path)
        except OSError as exc:
            errors.append(f"{exe_path}: {exc}")
    return launched, errors


def _wait_for_layout_windows(layout, timeout=8.0):
    deadline = time.monotonic() + timeout
    candidates = enumerate_app_windows()
    while time.monotonic() < deadline:
        if _all_layout_windows_matched(layout, candidates):
            break
        time.sleep(0.3)
        candidates = enumerate_app_windows()
    return candidates


def apply_layout(layout, launch_missing=True):
    candidates = enumerate_app_windows()
    missing_windows = missing_windows_for_layout(layout, candidates) if launch_missing else []
    missing_paths = [item.get("exe_path", "") for item in missing_windows if item.get("exe_path")]
    launched, launch_errors = _launch_missing_apps(missing_paths) if launch_missing else ([], [])
    candidates = _wait_for_layout_windows(layout) if launched else enumerate_app_windows()
    monitors = get_monitor_layouts()
    used_hwnds = set()
    moved = 0
    missing = []
    errors = list(launch_errors)
    matched_windows = []

    for saved_window in layout.get("windows", []):
        match = find_best_window(saved_window, candidates, used_hwnds)
        if not match:
            missing.append(saved_window_label(saved_window))
            continue
        used_hwnds.add(match["hwnd"])
        target_monitor = choose_monitor_rect(saved_window, monitors)
        target_rect = relative_to_rect(saved_window["relative_rect"], target_monitor)
        width = rect_width(target_rect)
        height = rect_height(target_rect)
        try:
            if win32gui.IsIconic(match["hwnd"]):
                win32gui.ShowWindow(match["hwnd"], win32con.SW_RESTORE)
            win32gui.SetWindowPos(
                match["hwnd"],
                None,
                target_rect["left"],
                target_rect["top"],
                width,
                height,
                win32con.SWP_NOZORDER | win32con.SWP_NOACTIVATE,
            )
            moved += 1
            z_order = _int_or_none(saved_window.get("z_order"))
            matched_windows.append((z_order, len(matched_windows), match["hwnd"]))
        except Exception as exc:
            errors.append(f"{saved_window.get('title', 'Window')}: {exc}")

    for z_order, _index, hwnd in sorted(
        matched_windows,
        key=lambda item: (item[0] if item[0] is not None else item[1], item[1]),
        reverse=True,
    ):
        try:
            win32gui.SetWindowPos(
                hwnd,
                win32con.HWND_TOP,
                0,
                0,
                0,
                0,
                win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_NOACTIVATE,
            )
        except Exception as exc:
            errors.append(f"Could not restore window layer: {exc}")

    return LayoutApplyResult(moved=moved, launched=launched, missing=missing, errors=errors)
