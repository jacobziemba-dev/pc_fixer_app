"""Backend helpers for live stats, hardware info, startup/programs listing and
safe disk cleanup scanning. Every function here is read-only except
`delete_cleanup_items`, which only ever removes files inside the specific
cache/temp locations returned by `scan_cleanup_targets` -- never arbitrary
user paths -- and is only called after the user reviews and confirms in the UI.
"""
import json
import os
import subprocess
import winreg
from dataclasses import dataclass, field

import psutil
import win32api
import win32con

SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "scripts")

# Hide the console window that would otherwise flash when we shell out to
# powershell.exe from this GUI app.
_STARTUPINFO = subprocess.STARTUPINFO()
_STARTUPINFO.dwFlags |= subprocess.STARTF_USESHOWWINDOW
_CREATIONFLAGS = subprocess.CREATE_NO_WINDOW


def _run_powershell_script(script_path, timeout=20):
    try:
        proc = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy", "Bypass",
                "-File", script_path,
            ],
            capture_output=True,
            text=True,
            timeout=timeout,
            startupinfo=_STARTUPINFO,
            creationflags=_CREATIONFLAGS,
        )
        if proc.returncode != 0 or not proc.stdout.strip():
            return None
        return json.loads(proc.stdout)
    except Exception:
        return None


def _run_powershell_command(command, timeout=30):
    try:
        proc = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy", "Bypass",
                "-Command", command,
            ],
            capture_output=True,
            text=True,
            timeout=timeout,
            startupinfo=_STARTUPINFO,
            creationflags=_CREATIONFLAGS,
        )
        return proc.returncode == 0
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Live dashboard stats
# ---------------------------------------------------------------------------

def get_cpu_stats():
    return {
        "percent": psutil.cpu_percent(interval=None),
        "per_core": psutil.cpu_percent(interval=None, percpu=True),
        "freq_mhz": (psutil.cpu_freq().current if psutil.cpu_freq() else None),
    }


def get_memory_stats():
    vm = psutil.virtual_memory()
    return {
        "total": vm.total,
        "used": vm.used,
        "available": vm.available,
        "percent": vm.percent,
    }


def get_disk_usage():
    drives = []
    for part in psutil.disk_partitions(all=False):
        if not part.fstype:
            continue
        try:
            usage = psutil.disk_usage(part.mountpoint)
        except (PermissionError, OSError):
            continue
        drives.append({
            "device": part.device,
            "mountpoint": part.mountpoint,
            "fstype": part.fstype,
            "total": usage.total,
            "used": usage.used,
            "free": usage.free,
            "percent": usage.percent,
        })
    return drives


def get_network_counters():
    counters = psutil.net_io_counters()
    return {"bytes_sent": counters.bytes_sent, "bytes_recv": counters.bytes_recv}


# psutil.Process.cpu_percent(interval=None) only returns a meaningful value
# on the *second and later* calls against the same Process object (it measures
# the delta since the previous call). process_iter() hands back fresh Process
# objects every time, so we keep our own pid->Process cache across ticks.
_process_cache = {}


def _refresh_process_cache():
    current_pids = set()
    for p in psutil.process_iter(["pid", "name"]):
        pid = p.info["pid"]
        current_pids.add(pid)
        if pid not in _process_cache:
            try:
                p.cpu_percent(interval=None)  # prime it
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
            _process_cache[pid] = p
    for pid in list(_process_cache):
        if pid not in current_pids:
            del _process_cache[pid]


def get_top_processes(limit=8, sort_by="cpu"):
    _refresh_process_cache()
    procs = []
    for pid, p in list(_process_cache.items()):
        try:
            cpu = p.cpu_percent(interval=None)
            mem = p.memory_info().rss
            name = p.name()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
        procs.append({"pid": pid, "name": name, "cpu": cpu, "mem": mem})
    key = "cpu" if sort_by == "cpu" else "mem"
    procs.sort(key=lambda x: x[key], reverse=True)
    return procs[:limit]


def prime_process_cpu_percent():
    """Call once at startup so the first dashboard tick already has a baseline."""
    _refresh_process_cache()


# ---------------------------------------------------------------------------
# Hardware overview
# ---------------------------------------------------------------------------

def get_hardware_info():
    script = os.path.join(SCRIPTS_DIR, "hardware_info.ps1")
    data = _run_powershell_script(script) or {}

    def as_list(v):
        if v is None:
            return []
        return v if isinstance(v, list) else [v]

    return {
        "cpu": as_list(data.get("cpu")),
        "gpu": as_list(data.get("gpu")),
        "system": as_list(data.get("system")),
        "board": as_list(data.get("board")),
        "bios": as_list(data.get("bios")),
        "os": as_list(data.get("os")),
        "disk_drives": as_list(data.get("diskDrives")),
        "physical_disks": as_list(data.get("physicalDisks")),
        "memory_modules": as_list(data.get("memoryModules")),
        "logical_cores": psutil.cpu_count(logical=True),
        "physical_cores": psutil.cpu_count(logical=False),
        "boot_time": psutil.boot_time(),
    }


# ---------------------------------------------------------------------------
# Display devices and refresh-rate changes
# ---------------------------------------------------------------------------

DISPLAY_DEVICE_ATTACHED_TO_DESKTOP = 0x00000001
DISPLAY_DEVICE_PRIMARY_DEVICE = 0x00000004


@dataclass
class DisplayDevice:
    name: str
    label: str
    adapter_label: str = ""
    monitor_device_name: str = ""
    device_id: str = ""
    device_key: str = ""
    is_primary: bool = False


@dataclass
class DisplayMode:
    width: int
    height: int
    bit_depth: int
    refresh_hz: int


@dataclass
class DisplayChangeResult:
    success: bool
    code: int
    message: str
    requires_restart: bool = False


def _display_mode_from_devmode(devmode):
    return DisplayMode(
        width=int(devmode.PelsWidth),
        height=int(devmode.PelsHeight),
        bit_depth=int(devmode.BitsPerPel),
        refresh_hz=int(devmode.DisplayFrequency),
    )


def _monitor_name_from_edid(edid):
    if not edid or len(edid) < 128:
        return ""
    for offset in range(54, 126, 18):
        descriptor = edid[offset:offset + 18]
        if len(descriptor) < 18:
            continue
        if descriptor[0:3] == b"\x00\x00\x00" and descriptor[3] == 0xFC:
            raw_name = descriptor[5:18].split(b"\x0A", 1)[0]
            return raw_name.decode("ascii", errors="ignore").strip(" \t\r\n\x00")
    return ""


def _monitor_hardware_id(device_id):
    parts = str(device_id or "").split("\\")
    if len(parts) >= 2 and parts[0].upper() == "MONITOR":
        return parts[1]
    return ""


def _monitor_name_from_registry(device_id):
    hardware_id = _monitor_hardware_id(device_id)
    if not hardware_id:
        return ""
    base_path = rf"SYSTEM\CurrentControlSet\Enum\DISPLAY\{hardware_id}"
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, base_path, 0, winreg.KEY_READ) as base:
            index = 0
            while True:
                try:
                    instance_name = winreg.EnumKey(base, index)
                except OSError:
                    break
                index += 1
                params_path = rf"{base_path}\{instance_name}\Device Parameters"
                try:
                    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, params_path, 0, winreg.KEY_READ) as params:
                        edid = winreg.QueryValueEx(params, "EDID")[0]
                except OSError:
                    continue
                monitor_name = _monitor_name_from_edid(edid)
                if monitor_name:
                    return monitor_name
    except OSError:
        return ""
    return ""


def _monitor_for_adapter(adapter_name):
    index = 0
    while True:
        try:
            monitor = win32api.EnumDisplayDevices(adapter_name, index)
        except Exception:
            break
        index += 1
        if monitor.StateFlags & DISPLAY_DEVICE_ATTACHED_TO_DESKTOP:
            return monitor
    return None


def _result_message(code):
    messages = {
        win32con.DISP_CHANGE_SUCCESSFUL: "Refresh rate changed successfully.",
        win32con.DISP_CHANGE_RESTART: "Refresh rate was accepted, but Windows requires a restart.",
        win32con.DISP_CHANGE_FAILED: "Windows or the display driver refused the change.",
        win32con.DISP_CHANGE_BADMODE: "That refresh rate is not supported for the current display mode.",
        win32con.DISP_CHANGE_NOTUPDATED: "Windows could not save the display settings.",
        win32con.DISP_CHANGE_BADFLAGS: "The display change request used invalid flags.",
        win32con.DISP_CHANGE_BADPARAM: "The display change request used invalid parameters.",
        win32con.DISP_CHANGE_BADDUALVIEW: "The display change is not supported while DualView is enabled.",
    }
    return messages.get(code, f"Windows returned display change code {code}.")


def _supported_refresh_rates_for_modes(current_mode, modes):
    rates = {
        int(mode.refresh_hz)
        for mode in modes
        if int(mode.width) == int(current_mode.width)
        and int(mode.height) == int(current_mode.height)
        and int(mode.bit_depth) == int(current_mode.bit_depth)
        and int(mode.refresh_hz) > 1
    }
    if int(current_mode.refresh_hz) > 1:
        rates.add(int(current_mode.refresh_hz))
    return sorted(rates)


def get_display_devices():
    devices = []
    index = 0
    while True:
        try:
            device = win32api.EnumDisplayDevices(None, index)
        except Exception:
            break
        index += 1
        if not (device.StateFlags & DISPLAY_DEVICE_ATTACHED_TO_DESKTOP):
            continue
        monitor = _monitor_for_adapter(device.DeviceName)
        monitor_name = ""
        monitor_device_name = ""
        monitor_device_id = ""
        if monitor:
            monitor_device_name = monitor.DeviceName
            monitor_device_id = monitor.DeviceID
            monitor_name = _monitor_name_from_registry(monitor.DeviceID) or monitor.DeviceString
        devices.append(DisplayDevice(
            name=device.DeviceName,
            label=monitor_name or device.DeviceString or device.DeviceName,
            adapter_label=device.DeviceString or "",
            monitor_device_name=monitor_device_name,
            device_id=monitor_device_id or device.DeviceID,
            device_key=device.DeviceKey,
            is_primary=bool(device.StateFlags & DISPLAY_DEVICE_PRIMARY_DEVICE),
        ))
    devices.sort(key=lambda d: (not d.is_primary, d.label.lower()))
    return devices


def get_current_display_mode(device_name):
    devmode = win32api.EnumDisplaySettings(device_name, win32con.ENUM_CURRENT_SETTINGS)
    return _display_mode_from_devmode(devmode)


def _get_display_modes(device_name):
    modes = []
    index = 0
    while True:
        try:
            devmode = win32api.EnumDisplaySettings(device_name, index)
        except Exception:
            break
        modes.append(_display_mode_from_devmode(devmode))
        index += 1
    return modes


def get_supported_refresh_rates(device_name):
    current = get_current_display_mode(device_name)
    return _supported_refresh_rates_for_modes(current, _get_display_modes(device_name))


def set_display_refresh_rate(device_name, hz):
    current_devmode = win32api.EnumDisplaySettings(device_name, win32con.ENUM_CURRENT_SETTINGS)
    current_devmode.DisplayFrequency = int(hz)
    current_devmode.Fields = (
        win32con.DM_PELSWIDTH
        | win32con.DM_PELSHEIGHT
        | win32con.DM_BITSPERPEL
        | win32con.DM_DISPLAYFREQUENCY
    )

    test_code = win32api.ChangeDisplaySettingsEx(device_name, current_devmode, win32con.CDS_TEST)
    if test_code != win32con.DISP_CHANGE_SUCCESSFUL:
        return DisplayChangeResult(
            success=False,
            code=test_code,
            message=_result_message(test_code),
            requires_restart=(test_code == win32con.DISP_CHANGE_RESTART),
        )

    apply_code = win32api.ChangeDisplaySettingsEx(device_name, current_devmode, win32con.CDS_UPDATEREGISTRY)
    return DisplayChangeResult(
        success=apply_code in (win32con.DISP_CHANGE_SUCCESSFUL, win32con.DISP_CHANGE_RESTART),
        code=apply_code,
        message=_result_message(apply_code),
        requires_restart=(apply_code == win32con.DISP_CHANGE_RESTART),
    )


# ---------------------------------------------------------------------------
# Startup items (read-only listing)
# ---------------------------------------------------------------------------

_RUN_KEYS = [
    (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run"),
    (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Run"),
    (winreg.HKEY_LOCAL_MACHINE, r"Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Run"),
]

_STARTUP_FOLDERS = [
    os.path.join(os.environ.get("APPDATA", ""), r"Microsoft\Windows\Start Menu\Programs\Startup"),
    os.path.join(os.environ.get("PROGRAMDATA", ""), r"Microsoft\Windows\Start Menu\Programs\Startup"),
]


def get_startup_items():
    items = []
    for hive, subkey in _RUN_KEYS:
        hive_name = "HKCU" if hive == winreg.HKEY_CURRENT_USER else "HKLM"
        try:
            with winreg.OpenKey(hive, subkey, 0, winreg.KEY_READ) as key:
                i = 0
                while True:
                    try:
                        name, value, _ = winreg.EnumValue(key, i)
                        items.append({
                            "name": name,
                            "command": value,
                            "source": f"{hive_name}\\...\\Run",
                        })
                        i += 1
                    except OSError:
                        break
        except FileNotFoundError:
            continue
        except PermissionError:
            continue

    for folder in _STARTUP_FOLDERS:
        if not folder or not os.path.isdir(folder):
            continue
        try:
            for fname in os.listdir(folder):
                if fname.lower() == "desktop.ini":
                    continue
                items.append({
                    "name": fname,
                    "command": os.path.join(folder, fname),
                    "source": "Startup folder",
                })
        except PermissionError:
            continue

    return items


# ---------------------------------------------------------------------------
# Installed programs (read-only listing)
# ---------------------------------------------------------------------------

_UNINSTALL_KEYS = [
    (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
    (winreg.HKEY_LOCAL_MACHINE, r"Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
    (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
]


def _read_value(key, name, default=None):
    try:
        return winreg.QueryValueEx(key, name)[0]
    except OSError:
        return default


def get_installed_programs():
    programs = []
    seen = set()
    for hive, subkey in _UNINSTALL_KEYS:
        try:
            with winreg.OpenKey(hive, subkey, 0, winreg.KEY_READ) as root:
                i = 0
                while True:
                    try:
                        sub_name = winreg.EnumKey(root, i)
                    except OSError:
                        break
                    i += 1
                    try:
                        with winreg.OpenKey(root, sub_name, 0, winreg.KEY_READ) as entry:
                            display_name = _read_value(entry, "DisplayName")
                            if not display_name:
                                continue
                            if _read_value(entry, "SystemComponent", 0) == 1:
                                continue
                            if display_name in seen:
                                continue
                            seen.add(display_name)
                            size_kb = _read_value(entry, "EstimatedSize", 0) or 0
                            programs.append({
                                "name": display_name,
                                "version": _read_value(entry, "DisplayVersion", ""),
                                "publisher": _read_value(entry, "Publisher", ""),
                                "install_date": _read_value(entry, "InstallDate", ""),
                                "size_bytes": int(size_kb) * 1024,
                            })
                    except OSError:
                        continue
        except FileNotFoundError:
            continue
        except PermissionError:
            continue

    programs.sort(key=lambda p: p["name"].lower())
    return programs


# ---------------------------------------------------------------------------
# Safe cleanup: scan-only by default, delete only on explicit confirmation
# ---------------------------------------------------------------------------

@dataclass
class CleanupCategory:
    key: str
    label: str
    description: str
    paths: list = field(default_factory=list)
    size_bytes: int = 0
    file_count: int = 0
    is_recycle_bin: bool = False
    scan_error: str = ""


def _dir_size(path):
    total = 0
    count = 0
    for root, dirs, files in os.walk(path, topdown=True, onerror=lambda e: None):
        for fname in files:
            fpath = os.path.join(root, fname)
            try:
                total += os.path.getsize(fpath)
                count += 1
            except OSError:
                continue
    return total, count


def _recycle_bin_size():
    output = _run_powershell_command_capture(
        "(Get-ChildItem -Path (Join-Path $env:SystemDrive '$Recycle.Bin') -Recurse -Force "
        "-ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum"
    )
    try:
        return int(float(output.strip())) if output and output.strip() else 0
    except ValueError:
        return 0


def _run_powershell_command_capture(command, timeout=30):
    try:
        proc = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy", "Bypass",
                "-Command", command,
            ],
            capture_output=True,
            text=True,
            timeout=timeout,
            startupinfo=_STARTUPINFO,
            creationflags=_CREATIONFLAGS,
        )
        return proc.stdout
    except Exception:
        return ""


def _candidate_dirs():
    local = os.environ.get("LOCALAPPDATA", "")
    candidates = {
        "user_temp": ("User Temp Files", "Temporary files left behind by apps and installers.",
                      [os.environ.get("TEMP", ""), os.environ.get("TMP", "")]),
        "windows_temp": ("Windows Temp Files", "System-wide temporary files in C:\\Windows\\Temp.",
                          [r"C:\Windows\Temp"]),
        "thumbnail_cache": ("Thumbnail Cache", "Cached thumbnail images; Windows regenerates these automatically.",
                             [os.path.join(local, "Microsoft", "Windows", "Explorer")]),
        "chrome_cache": ("Chrome Browser Cache", "Cached web content for Google Chrome.",
                          [os.path.join(local, "Google", "Chrome", "User Data", "Default", "Cache"),
                           os.path.join(local, "Google", "Chrome", "User Data", "Default", "Code Cache")]),
        "edge_cache": ("Edge Browser Cache", "Cached web content for Microsoft Edge.",
                        [os.path.join(local, "Microsoft", "Edge", "User Data", "Default", "Cache"),
                         os.path.join(local, "Microsoft", "Edge", "User Data", "Default", "Code Cache")]),
        "firefox_cache": ("Firefox Browser Cache", "Cached web content for Mozilla Firefox.",
                           _firefox_cache_dirs(local)),
    }
    return candidates


def _firefox_cache_dirs(local):
    base = os.path.join(local, "Mozilla", "Firefox", "Profiles")
    dirs = []
    if os.path.isdir(base):
        try:
            for profile in os.listdir(base):
                cache_dir = os.path.join(base, profile, "cache2")
                if os.path.isdir(cache_dir):
                    dirs.append(cache_dir)
        except PermissionError:
            pass
    return dirs


def scan_cleanup_targets():
    """Read-only scan. Returns a list of CleanupCategory with sizes computed."""
    categories = []

    for key, (label, desc, paths) in _candidate_dirs().items():
        existing = [p for p in paths if p and os.path.isdir(p)]
        if not existing:
            continue
        total = 0
        count = 0
        for p in existing:
            size, cnt = _dir_size(p)
            total += size
            count += cnt
        if total > 0:
            categories.append(CleanupCategory(
                key=key, label=label, description=desc,
                paths=existing, size_bytes=total, file_count=count,
            ))

    recycle_size = _recycle_bin_size()
    if recycle_size > 0:
        categories.append(CleanupCategory(
            key="recycle_bin", label="Recycle Bin", description="Files you've already deleted.",
            paths=[], size_bytes=recycle_size, file_count=0, is_recycle_bin=True,
        ))

    categories.sort(key=lambda c: c.size_bytes, reverse=True)
    return categories


def delete_cleanup_items(categories):
    """Delete only the given, already-scanned categories. Returns (bytes_freed, errors)."""
    bytes_freed = 0
    errors = []

    for cat in categories:
        if cat.is_recycle_bin:
            ok = _run_powershell_command("Clear-RecycleBin -Force -ErrorAction SilentlyContinue")
            if ok:
                bytes_freed += cat.size_bytes
            else:
                errors.append(f"{cat.label}: could not empty Recycle Bin")
            continue

        for path in cat.paths:
            for root, dirs, files in os.walk(path, topdown=False, onerror=lambda e: None):
                for fname in files:
                    fpath = os.path.join(root, fname)
                    try:
                        size = os.path.getsize(fpath)
                        os.remove(fpath)
                        bytes_freed += size
                    except OSError:
                        continue
                for dname in dirs:
                    dpath = os.path.join(root, dname)
                    try:
                        os.rmdir(dpath)
                    except OSError:
                        continue

    return bytes_freed, errors


def format_bytes(n):
    n = float(n)
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"
