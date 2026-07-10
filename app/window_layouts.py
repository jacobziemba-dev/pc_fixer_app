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
            windows.append(info)
        return True

    win32gui.EnumWindows(callback, None)
    return windows


def capture_current_layout(name):
    monitors = get_monitor_layouts()
    windows = []
    for window in enumerate_app_windows():
        monitor = monitor_for_rect(window["rect"], monitors)
        if not monitor:
            continue
        windows.append({
            "title": window["title"],
            "exe_path": window["exe_path"],
            "process_name": os.path.basename(window["exe_path"]) if window["exe_path"] else "",
            "monitor_device": monitor["device"],
            "monitor_rect": monitor["monitor_rect"],
            "window_rect": window["rect"],
            "relative_rect": rect_to_relative(window["rect"], monitor["monitor_rect"]),
        })
    now = _now_iso()
    return {
        "id": str(uuid.uuid4()),
        "name": name,
        "created_at": now,
        "updated_at": now,
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
        if all(find_best_window(item, candidates) for item in layout.get("windows", [])):
            break
        time.sleep(0.3)
        candidates = enumerate_app_windows()
    return candidates


def apply_layout(layout, launch_missing=True):
    missing_paths = missing_apps_for_layout(layout) if launch_missing else []
    launched, launch_errors = _launch_missing_apps(missing_paths) if launch_missing else ([], [])
    candidates = _wait_for_layout_windows(layout) if launched else enumerate_app_windows()
    monitors = get_monitor_layouts()
    used_hwnds = set()
    moved = 0
    missing = []
    errors = list(launch_errors)

    for saved_window in layout.get("windows", []):
        match = find_best_window(saved_window, candidates, used_hwnds)
        if not match:
            missing.append(saved_window.get("title") or saved_window.get("exe_path") or "Unknown window")
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
        except Exception as exc:
            errors.append(f"{saved_window.get('title', 'Window')}: {exc}")

    return LayoutApplyResult(moved=moved, launched=launched, missing=missing, errors=errors)
