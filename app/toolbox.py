"""Conservative Windows toolbox helpers for PC health and repair workflows.

The functions in this module are intentionally named, narrow operations. There
is no arbitrary shell execution surface here; assistant actions and UI buttons
call these helpers through fixed code paths.
"""
from __future__ import annotations

import json
import os
import platform
import socket
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import psutil

from app import system_info as sysinfo


PROJECT_ROOT = Path(__file__).resolve().parent.parent
REPORTS_DIR = PROJECT_ROOT / "reports"


@dataclass
class ToolResult:
    success: bool
    title: str
    summary: str
    details: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def is_windows():
    return platform.system().lower() == "windows"


def windows_only_result(title):
    return ToolResult(
        False,
        title,
        "This tool is available only on Windows.",
        errors=["Unsupported platform"],
    )


def _startupinfo():
    if not is_windows():
        return None, 0
    try:
        info = subprocess.STARTUPINFO()
        info.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        return info, subprocess.CREATE_NO_WINDOW
    except Exception:
        return None, 0


def _run_command(args, timeout=30):
    startupinfo, creationflags = _startupinfo()
    try:
        proc = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
            startupinfo=startupinfo,
            creationflags=creationflags,
        )
        return proc.returncode, proc.stdout.strip(), proc.stderr.strip()
    except Exception as exc:
        return -1, "", str(exc)


def _run_powershell(command, timeout=30):
    if not is_windows():
        return -1, "", "Windows PowerShell is not available on this platform."
    return _run_command(
        [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            command,
        ],
        timeout=timeout,
    )


def _run_json_powershell(command, timeout=30):
    code, stdout, stderr = _run_powershell(command, timeout=timeout)
    if code != 0:
        return None, stderr or stdout or f"PowerShell exited with code {code}."
    if not stdout:
        return None, ""
    try:
        return json.loads(stdout), ""
    except json.JSONDecodeError as exc:
        return None, f"Could not parse PowerShell JSON: {exc}"


def _as_list(value):
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def check_windows_updates():
    title = "Windows Update"
    if not is_windows():
        return windows_only_result(title)

    pending_data, pending_error = _run_json_powershell(
        "$session = New-Object -ComObject Microsoft.Update.Session; "
        "$searcher = $session.CreateUpdateSearcher(); "
        "$result = $searcher.Search('IsInstalled=0 and Type=''Software'''); "
        "[pscustomobject]@{Pending=$result.Updates.Count} | ConvertTo-Json -Compress",
        timeout=45,
    )
    hotfix_data, hotfix_error = _run_json_powershell(
        "Get-HotFix | Sort-Object InstalledOn -Descending | Select-Object -First 1 "
        "HotFixID,InstalledOn,Description | ConvertTo-Json -Compress",
        timeout=30,
    )
    reboot_data, reboot_error = _run_json_powershell(
        "$paths = @("
        "'HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Component Based Servicing\\RebootPending',"
        "'HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\WindowsUpdate\\Auto Update\\RebootRequired'"
        "); "
        "[pscustomobject]@{RebootPending=($paths | Where-Object { Test-Path $_ } | Measure-Object).Count -gt 0} "
        "| ConvertTo-Json -Compress",
        timeout=10,
    )

    details = []
    errors = [err for err in (pending_error, hotfix_error, reboot_error) if err]
    pending = pending_data.get("Pending") if isinstance(pending_data, dict) else None
    reboot = reboot_data.get("RebootPending") if isinstance(reboot_data, dict) else None
    if pending is not None:
        details.append(f"Pending software updates: {pending}")
    if reboot is not None:
        details.append(f"Reboot pending: {'yes' if reboot else 'no'}")
    if isinstance(hotfix_data, dict) and hotfix_data.get("HotFixID"):
        installed_on = str(hotfix_data.get("InstalledOn", "")).split("T", 1)[0]
        details.append(f"Last installed hotfix: {hotfix_data['HotFixID']} {installed_on}".strip())

    if not details:
        return ToolResult(False, title, "Could not read Windows Update status.", errors=errors)
    summary = "Windows Update status checked."
    if pending:
        summary = f"{pending} pending update(s) found."
    elif reboot:
        summary = "No pending update count found, but a reboot appears pending."
    return ToolResult(not errors, title, summary, details, errors)


def check_disk_health():
    title = "Disk Health"
    if not is_windows():
        return windows_only_result(title)
    data, error = _run_json_powershell(
        "Get-PhysicalDisk | Select-Object FriendlyName,MediaType,HealthStatus,OperationalStatus,Size "
        "| ConvertTo-Json -Compress",
        timeout=30,
    )
    disks = _as_list(data)
    if not disks:
        return ToolResult(False, title, "No physical disk health data was returned.", errors=[error] if error else [])
    details = []
    warnings = 0
    for disk in disks:
        status = str(disk.get("HealthStatus", "Unknown"))
        operational = disk.get("OperationalStatus", "")
        size = sysinfo.format_bytes(disk.get("Size") or 0)
        details.append(
            f"{disk.get('FriendlyName', 'Disk')}: {status}, {operational}, "
            f"{disk.get('MediaType', 'Unknown media')}, {size}"
        )
        if status.lower() not in {"healthy", "ok"}:
            warnings += 1
    summary = "All reported disks look healthy." if warnings == 0 else f"{warnings} disk(s) need attention."
    return ToolResult(warnings == 0 and not error, title, summary, details, [error] if error else [])


def scan_event_log_errors(hours=24, max_events=12):
    title = "Event Log Errors"
    if not is_windows():
        return windows_only_result(title)
    hours = max(1, min(int(hours), 168))
    max_events = max(1, min(int(max_events), 50))
    command = (
        f"$start=(Get-Date).AddHours(-{hours}); "
        "Get-WinEvent -FilterHashtable @{LogName=@('System','Application'); Level=1,2; StartTime=$start} "
        f"-MaxEvents {max_events} | Select-Object TimeCreated,LogName,ProviderName,Id,LevelDisplayName,Message "
        "| ConvertTo-Json -Compress"
    )
    data, error = _run_json_powershell(command, timeout=45)
    events = _as_list(data)
    if not events:
        summary = f"No critical/error events found in the last {hours} hour(s)."
        return ToolResult(not error, title, summary, errors=[error] if error else [])
    details = []
    for event in events:
        message = str(event.get("Message", "")).replace("\r", " ").replace("\n", " ")
        if len(message) > 140:
            message = message[:137] + "..."
        details.append(
            f"{event.get('TimeCreated', '')} {event.get('LogName', '')} "
            f"{event.get('ProviderName', '')} #{event.get('Id', '')}: {message}"
        )
    return ToolResult(False, title, f"{len(events)} recent critical/error event(s) found.", details, [error] if error else [])


def check_network_health():
    title = "Network Health"
    details = []
    errors = []

    try:
        hostname = socket.gethostname()
        addresses = socket.gethostbyname_ex(hostname)[2]
        details.append(f"Host: {hostname}")
        details.append(f"Local IPs: {', '.join(addresses) if addresses else 'none'}")
    except Exception as exc:
        errors.append(f"Hostname/IP lookup failed: {exc}")

    active_adapters = []
    for name, stats in psutil.net_if_stats().items():
        if stats.isup:
            active_adapters.append(name)
    details.append(f"Active adapters: {', '.join(active_adapters) if active_adapters else 'none'}")

    if is_windows():
        code, stdout, stderr = _run_powershell(
            "Test-Connection -ComputerName 1.1.1.1 -Count 2 -Quiet",
            timeout=15,
        )
        if code == 0:
            details.append(f"Internet ping: {'reachable' if stdout.strip().lower() == 'true' else 'failed'}")
        else:
            errors.append(stderr or "Internet ping failed.")
        data, error = _run_json_powershell(
            "Get-DnsClientServerAddress -AddressFamily IPv4 | "
            "Where-Object {$_.ServerAddresses.Count -gt 0} | "
            "Select-Object InterfaceAlias,ServerAddresses | ConvertTo-Json -Compress",
            timeout=15,
        )
        if error:
            errors.append(error)
        for entry in _as_list(data):
            servers = entry.get("ServerAddresses", [])
            if isinstance(servers, str):
                servers = [servers]
            details.append(f"DNS {entry.get('InterfaceAlias', '')}: {', '.join(servers)}")

    summary = "Network basics look available." if active_adapters and not errors else "Network check found items to review."
    return ToolResult(not errors and bool(active_adapters), title, summary, details, errors)


_DNS_PING_HOSTS = frozenset({
    "one.one.one.one",
    "1.1.1.1",
    "dns.google",
    "8.8.8.8",
    "cloudflare.com",
    "microsoft.com",
    "www.microsoft.com",
})


def list_network_adapter_names():
    """Lightweight adapter list for assistant snapshot targeting."""
    adapters = []
    try:
        stats_map = psutil.net_if_stats()
    except Exception:
        return adapters
    for name, stats in stats_map.items():
        adapters.append({"name": name, "is_up": bool(getattr(stats, "isup", False))})
    return adapters


def list_network_adapters():
    title = "Network Adapters"
    adapters = list_network_adapter_names()
    if not adapters:
        return ToolResult(False, title, "No network adapters were found.")
    details = [
        f"{item['name']} ({'up' if item.get('is_up') else 'down'})"
        for item in adapters
    ]
    return ToolResult(True, title, f"{len(adapters)} network adapter(s) found.", details)


def check_dns_resolve(host="one.one.one.one"):
    title = "DNS Resolve"
    key = str(host or "").strip().lower()
    if key not in _DNS_PING_HOSTS:
        return ToolResult(
            False,
            title,
            "Host is not on the allowlist.",
            errors=[f"Allowed hosts: {', '.join(sorted(_DNS_PING_HOSTS))}"],
        )
    try:
        infos = socket.getaddrinfo(key, None)
        addresses = sorted({item[4][0] for item in infos if item and item[4]})
    except OSError as exc:
        return ToolResult(False, title, f"Could not resolve {key}.", errors=[str(exc)])
    return ToolResult(
        True,
        title,
        f"Resolved {key} to {', '.join(addresses[:4]) or 'no addresses'}.",
        addresses[:8],
    )


def ping_host(host="one.one.one.one", count=2):
    title = "Ping Host"
    key = str(host or "").strip().lower()
    if key not in _DNS_PING_HOSTS:
        return ToolResult(
            False,
            title,
            "Host is not on the allowlist.",
            errors=[f"Allowed hosts: {', '.join(sorted(_DNS_PING_HOSTS))}"],
        )
    count = max(1, min(int(count or 2), 4))
    if is_windows():
        code, stdout, stderr = _run_command(["ping", "-n", str(count), key], timeout=20)
    else:
        code, stdout, stderr = _run_command(["ping", "-c", str(count), key], timeout=20)
    success = code == 0
    details = [line for line in (stdout or "").splitlines() if line.strip()][:8]
    return ToolResult(
        success,
        title,
        f"Ping {key} {'succeeded' if success else 'failed'}.",
        details,
        [stderr] if stderr and not success else [],
    )


def check_default_gateway():
    title = "Default Gateway"
    details = []
    errors = []
    try:
        gateway_map = psutil.net_if_stats()
        active = [name for name, stats in gateway_map.items() if stats.isup]
        details.append(f"Active adapters: {', '.join(active) if active else 'none'}")
    except Exception as exc:
        errors.append(f"Adapter status failed: {exc}")
    if is_windows():
        data, error = _run_json_powershell(
            "Get-NetRoute -DestinationPrefix '0.0.0.0/0' -ErrorAction SilentlyContinue | "
            "Select-Object -First 3 InterfaceAlias,NextHop,RouteMetric | ConvertTo-Json -Compress",
            timeout=15,
        )
        if error:
            errors.append(error)
        for entry in _as_list(data):
            details.append(
                f"Gateway {entry.get('InterfaceAlias', '')}: {entry.get('NextHop', '')} "
                f"(metric {entry.get('RouteMetric', '?')})"
            )
    summary = "Default gateway details collected." if details and not errors else "Gateway check needs review."
    return ToolResult(bool(details) and not errors, title, summary, details, errors)


def show_wifi_status():
    title = "Wi-Fi Status"
    if not is_windows():
        return windows_only_result(title)
    code, stdout, stderr = _run_command(["netsh", "wlan", "show", "interfaces"], timeout=15)
    if code != 0:
        return ToolResult(False, title, "Could not read Wi-Fi status.", errors=[stderr or stdout])
    details = []
    for line in (stdout or "").splitlines():
        stripped = line.strip()
        lowered = stripped.lower()
        if lowered.startswith(("ssid", "state", "signal", "radio", "profile", "name")):
            # Never capture keys/security material beyond SSID/state/signal.
            if "key content" in lowered or "password" in lowered:
                continue
            details.append(stripped)
    if not details:
        details = [line.strip() for line in (stdout or "").splitlines() if line.strip()][:8]
    return ToolResult(True, title, "Wi-Fi status collected.", details[:12])


def get_recycle_bin_size():
    title = "Recycle Bin Size"
    try:
        size = sysinfo._recycle_bin_size()
    except Exception as exc:
        return ToolResult(False, title, "Could not read Recycle Bin size.", errors=[str(exc)])
    return ToolResult(True, title, f"Recycle Bin is using {sysinfo.format_bytes(size)}.", [sysinfo.format_bytes(size)])


def empty_recycle_bin():
    title = "Empty Recycle Bin"
    if not is_windows():
        return windows_only_result(title)
    ok = sysinfo._run_powershell_command("Clear-RecycleBin -Force -ErrorAction SilentlyContinue")
    if ok:
        return ToolResult(True, title, "Recycle Bin emptied.")
    return ToolResult(False, title, "Could not empty the Recycle Bin.")


def clean_cleanup_categories_by_keys(category_keys):
    title = "Clean Categories"
    wanted = {str(key) for key in (category_keys or []) if str(key).strip()}
    if not wanted:
        return ToolResult(False, title, "No cleanup categories were selected.")
    try:
        scanned = sysinfo.scan_cleanup_targets()
    except Exception as exc:
        return ToolResult(False, title, "Cleanup scan failed.", errors=[str(exc)])
    categories = [cat for cat in scanned if cat.key in wanted]
    if not categories:
        return ToolResult(False, title, "No matching scanned cleanup categories were found.")
    bytes_freed, errors = sysinfo.delete_cleanup_items(categories)
    return ToolResult(
        not errors,
        title,
        f"Freed {sysinfo.format_bytes(bytes_freed)}.",
        [f"{cat.label}: {sysinfo.format_bytes(cat.size_bytes)}" for cat in categories],
        errors,
    )


def check_system_uptime():
    title = "System Uptime"
    try:
        boot = datetime.fromtimestamp(psutil.boot_time())
        uptime = datetime.now() - boot
        hours = int(uptime.total_seconds() // 3600)
        minutes = int((uptime.total_seconds() % 3600) // 60)
        details = [f"Boot time: {boot.isoformat(sep=' ', timespec='seconds')}", f"Uptime: {hours}h {minutes}m"]
        return ToolResult(True, title, f"PC has been up for {hours}h {minutes}m.", details)
    except Exception as exc:
        return ToolResult(False, title, "Could not read system uptime.", errors=[str(exc)])


def check_memory_pressure():
    title = "Memory Pressure"
    try:
        mem = psutil.virtual_memory()
        swap = psutil.swap_memory()
        details = [
            f"RAM used: {sysinfo.format_bytes(mem.used)} / {sysinfo.format_bytes(mem.total)} ({mem.percent:.0f}%)",
            f"RAM available: {sysinfo.format_bytes(mem.available)}",
            f"Pagefile/swap used: {sysinfo.format_bytes(swap.used)} / {sysinfo.format_bytes(swap.total)} ({swap.percent:.0f}%)",
        ]
        stressed = mem.percent >= 85 or swap.percent >= 70
        summary = "Memory pressure looks high." if stressed else "Memory pressure looks moderate."
        return ToolResult(True, title, summary, details)
    except Exception as exc:
        return ToolResult(False, title, "Could not read memory pressure.", errors=[str(exc)])


def list_installed_gpus():
    title = "Installed GPUs"
    try:
        hardware = sysinfo.get_hardware_info()
        gpus = hardware.get("gpu") or []
    except Exception as exc:
        return ToolResult(False, title, "Could not read GPU information.", errors=[str(exc)])
    names = []
    for item in gpus:
        if isinstance(item, dict):
            name = item.get("Name") or item.get("name")
            if name:
                names.append(str(name))
    if not names:
        return ToolResult(False, title, "No GPU entries were found.")
    return ToolResult(True, title, f"{len(names)} GPU(s) found.", names)


def open_system_tool(tool_key):
    title = "Open System Tool"
    if not is_windows():
        return windows_only_result(title)
    mapping = {
        "task_manager": ["taskmgr.exe"],
        "resource_monitor": ["resmon.exe"],
        "device_manager": ["devmgmt.msc"],
    }
    key = str(tool_key or "").strip().lower()
    command = mapping.get(key)
    if not command:
        return ToolResult(
            False,
            title,
            "Unsupported system tool.",
            errors=[f"Allowed tools: {', '.join(sorted(mapping))}"],
        )
    try:
        if key == "device_manager":
            os.startfile(command[0])  # noqa: S606 - fixed allowlist only
        else:
            code, _stdout, stderr = _run_command(command, timeout=10)
            if code != 0:
                return ToolResult(False, title, f"Could not open {key}.", errors=[stderr] if stderr else [])
    except OSError as exc:
        return ToolResult(False, title, f"Could not open {key}.", errors=[str(exc)])
    return ToolResult(True, title, f"Opened {key}.", command)


def capture_window_layout(name="Assistant Layout"):
    title = "Capture Layout"
    from app import window_layouts

    safe_name = str(name or "Assistant Layout").strip()[:80] or "Assistant Layout"
    try:
        layout = window_layouts.capture_current_layout(safe_name)
        layouts = window_layouts.load_layouts()
        layouts.append(layout)
        window_layouts.save_layouts(layouts)
    except Exception as exc:
        return ToolResult(False, title, "Could not capture the current layout.", errors=[str(exc)])
    layout_id = (layout or {}).get("id", "")
    return ToolResult(
        True,
        title,
        f"Saved layout \"{safe_name}\".",
        [f"id={layout_id}"] if layout_id else [],
    )


def set_default_audio_device(device_id):
    title = "Set Default Audio Device"
    from app import audio_control

    ok, message = audio_control.set_default_output_device(str(device_id or ""))
    return ToolResult(ok, title, message)


def flush_dns_cache():
    title = "Flush DNS Cache"
    if not is_windows():
        return windows_only_result(title)
    code, stdout, stderr = _run_command(["ipconfig", "/flushdns"], timeout=15)
    success = code == 0
    return ToolResult(
        success,
        title,
        "DNS resolver cache flushed." if success else "Could not flush DNS resolver cache.",
        [stdout] if stdout else [],
        [stderr] if stderr else [],
    )


def restart_network_adapter(adapter_name):
    title = "Restart Network Adapter"
    adapter_name = str(adapter_name or "").strip()
    if not adapter_name:
        return ToolResult(False, title, "No network adapter was selected.", errors=["Missing adapter name"])
    if not is_windows():
        return windows_only_result(title)
    safe_name = adapter_name.replace("'", "''")
    code, stdout, stderr = _run_powershell(
        f"Restart-NetAdapter -Name '{safe_name}' -Confirm:$false -ErrorAction Stop",
        timeout=30,
    )
    success = code == 0
    return ToolResult(
        success,
        title,
        f"Restarted network adapter {adapter_name}." if success else f"Could not restart {adapter_name}.",
        [stdout] if stdout else [],
        [stderr] if stderr else [],
    )


def check_power_plan():
    title = "Power Plan"
    if not is_windows():
        return windows_only_result(title)
    code, stdout, stderr = _run_command(["powercfg", "/GETACTIVESCHEME"], timeout=10)
    if code != 0:
        return ToolResult(False, title, "Could not read the active power plan.", errors=[stderr or stdout])
    list_code, list_stdout, list_stderr = _run_command(["powercfg", "/LIST"], timeout=10)
    details = [stdout]
    if list_code == 0 and list_stdout:
        details.extend(line.strip() for line in list_stdout.splitlines() if line.strip())
    errors = [list_stderr] if list_code != 0 and list_stderr else []
    return ToolResult(True, title, "Active power plan checked.", details, errors)


def set_power_plan(plan_name):
    title = "Set Power Plan"
    if not is_windows():
        return windows_only_result(title)
    aliases = {
        "balanced": "SCHEME_BALANCED",
        "high_performance": "SCHEME_MIN",
        "high performance": "SCHEME_MIN",
        "power_saver": "SCHEME_MAX",
        "power saver": "SCHEME_MAX",
    }
    key = str(plan_name or "").strip().lower()
    scheme = aliases.get(key)
    if not scheme:
        return ToolResult(False, title, "Unsupported power plan.", errors=[f"Unknown plan: {plan_name}"])
    code, stdout, stderr = _run_command(["powercfg", "/SETACTIVE", scheme], timeout=10)
    success = code == 0
    return ToolResult(
        success,
        title,
        f"Power plan changed to {plan_name}." if success else "Could not change the power plan.",
        [stdout] if stdout else [],
        [stderr] if stderr else [],
    )


def review_startup_impact():
    title = "Startup Impact"
    try:
        items = sysinfo.get_startup_items()
    except Exception as exc:
        return ToolResult(False, title, "Could not read startup items.", errors=[str(exc)])
    details = []
    for item in items:
        command = str(item.get("command", ""))
        lowered = command.lower()
        risk = "Review"
        if any(part in lowered for part in ("onedrive", "teams", "discord", "steam", "updater")):
            risk = "Optional"
        if any(part in lowered for part in ("defender", "security", "driver", "audio", "graphics")):
            risk = "Keep"
        details.append(f"{risk}: {item.get('name', '')} ({item.get('source', '')})")
    summary = f"Reviewed {len(items)} startup item(s)."
    return ToolResult(True, title, summary, details[:50])


def check_windows_security():
    title = "Windows Security"
    if not is_windows():
        return windows_only_result(title)
    data, error = _run_json_powershell(
        "$mp = Get-MpComputerStatus -ErrorAction SilentlyContinue; "
        "$fw = Get-NetFirewallProfile | Select-Object Name,Enabled; "
        "[pscustomobject]@{"
        "AntivirusEnabled=$mp.AntivirusEnabled;"
        "RealTimeProtectionEnabled=$mp.RealTimeProtectionEnabled;"
        "AntispywareEnabled=$mp.AntispywareEnabled;"
        "Firewall=$fw"
        "} | ConvertTo-Json -Depth 4 -Compress",
        timeout=30,
    )
    if not isinstance(data, dict):
        return ToolResult(False, title, "Could not read Windows Security status.", errors=[error] if error else [])
    details = [
        f"Antivirus enabled: {'yes' if data.get('AntivirusEnabled') else 'no'}",
        f"Real-time protection: {'yes' if data.get('RealTimeProtectionEnabled') else 'no'}",
        f"Antispyware enabled: {'yes' if data.get('AntispywareEnabled') else 'no'}",
    ]
    for profile in _as_list(data.get("Firewall")):
        details.append(f"Firewall {profile.get('Name')}: {'on' if profile.get('Enabled') else 'off'}")
    ok = bool(data.get("AntivirusEnabled")) and bool(data.get("RealTimeProtectionEnabled"))
    return ToolResult(ok and not error, title, "Windows Security status checked.", details, [error] if error else [])


def scan_large_files(root=None, min_size_mb=500, limit=25):
    title = "Large Files"
    min_size = max(1, int(min_size_mb)) * 1024 * 1024
    limit = max(1, min(int(limit), 100))
    root_path = Path(root or Path.home())
    try:
        resolved_root = root_path.expanduser().resolve()
    except OSError as exc:
        return ToolResult(False, title, "Could not access scan root.", errors=[str(exc)])
    if not resolved_root.exists() or not resolved_root.is_dir():
        return ToolResult(False, title, "Large-file scan root is not a folder.", errors=[str(resolved_root)])

    found = []
    for current, dirs, files in os.walk(resolved_root, topdown=True, onerror=lambda exc: None):
        dirs[:] = [name for name in dirs if name not in {"venv", ".git", "__pycache__"}]
        for name in files:
            path = Path(current) / name
            try:
                size = path.stat().st_size
            except OSError:
                continue
            if size >= min_size:
                found.append((size, path))
    found.sort(reverse=True, key=lambda item: item[0])
    details = [f"{sysinfo.format_bytes(size)} - {path}" for size, path in found[:limit]]
    summary = f"Found {len(found)} file(s) at least {sysinfo.format_bytes(min_size)}."
    return ToolResult(True, title, summary, details)


def scan_folder_sizes(roots=None, max_entries=40):
    title = "Folder Sizes"
    try:
        entries = sysinfo.scan_folder_size_breakdown(roots=roots, max_entries=max_entries)
    except Exception as exc:
        return ToolResult(False, title, "Could not scan folder sizes.", errors=[str(exc)])
    if not entries:
        return ToolResult(True, title, "No sized folders were found under the default scan roots.")
    details = [
        f"{sysinfo.format_bytes(entry['size_bytes'])} - {entry['path']} ({entry['file_count']} files)"
        for entry in entries
    ]
    total = sum(entry["size_bytes"] for entry in entries)
    return ToolResult(
        True,
        title,
        f"Top {len(entries)} folder(s) total {sysinfo.format_bytes(total)}.",
        details,
    )


def scan_duplicate_files(roots=None, min_size_mb=1, limit_groups=25):
    title = "Duplicate Files"
    try:
        groups = sysinfo.find_duplicate_files(
            roots=roots,
            min_size_mb=min_size_mb,
            limit_groups=limit_groups,
        )
    except Exception as exc:
        return ToolResult(False, title, "Could not scan for duplicate files.", errors=[str(exc)])
    if not groups:
        return ToolResult(True, title, "No duplicate file groups were found.")
    details = []
    for group in groups:
        details.append(
            f"{group['count']} copies × {sysinfo.format_bytes(group['size_bytes'])} "
            f"(hash {group['hash'][:8]}…)"
        )
        details.extend(f"  - {path}" for path in group["paths"][:4])
        if len(group["paths"]) > 4:
            details.append(f"  - …and {len(group['paths']) - 4} more")
    return ToolResult(
        True,
        title,
        f"Found {len(groups)} duplicate group(s). Nothing was deleted.",
        details,
    )


def end_process(pid):
    title = "End Process"
    success, message = sysinfo.terminate_process(pid)
    return ToolResult(success, title, message, errors=[] if success else [message])


def set_startup_item_enabled(name, source, enabled, command=""):
    title = "Startup Item"
    success, message = sysinfo.set_startup_item_enabled(name, source, enabled, command=command)
    return ToolResult(success, title, message, errors=[] if success else [message])


def renew_ip_address():
    title = "Renew IP Address"
    if not is_windows():
        return windows_only_result(title)
    release_code, release_out, release_err = _run_command(["ipconfig", "/release"], timeout=45)
    renew_code, renew_out, renew_err = _run_command(["ipconfig", "/renew"], timeout=60)
    details = [line for line in (release_out, renew_out) if line]
    errors = [line for line in (release_err, renew_err) if line]
    success = renew_code == 0
    if release_code != 0 and renew_code == 0:
        # Some adapters fail release but still renew successfully.
        success = True
    return ToolResult(
        success,
        title,
        "IP address renewed." if success else "Could not renew the IP address.",
        details,
        errors,
    )


def reset_winsock():
    title = "Reset Winsock"
    if not is_windows():
        return windows_only_result(title)
    code, stdout, stderr = _run_command(["netsh", "winsock", "reset"], timeout=45)
    success = code == 0
    details = [line for line in (stdout,) if line]
    details.append("A reboot may be required for Winsock reset to finish applying.")
    return ToolResult(
        success,
        title,
        "Winsock catalog reset requested." if success else "Could not reset Winsock.",
        details,
        [stderr] if stderr else [],
    )


def check_pending_reboot():
    title = "Pending Reboot"
    if not is_windows():
        return windows_only_result(title)
    data, error = _run_json_powershell(
        "$paths = @("
        "'HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Component Based Servicing\\RebootPending',"
        "'HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\WindowsUpdate\\Auto Update\\RebootRequired',"
        "'HKLM:\\SYSTEM\\CurrentControlSet\\Control\\Session Manager\\PendingFileRenameOperations'"
        "); "
        "$hits = @(); "
        "foreach ($p in $paths) { if (Test-Path $p) { $hits += $p } }; "
        "[pscustomobject]@{RebootPending=($hits.Count -gt 0); Paths=$hits} | ConvertTo-Json -Compress",
        timeout=15,
    )
    if not isinstance(data, dict):
        return ToolResult(False, title, "Could not check pending reboot state.", errors=[error] if error else [])
    pending = bool(data.get("RebootPending"))
    details = []
    for path in _as_list(data.get("Paths")):
        details.append(f"Signal: {path}")
    summary = "A reboot appears pending." if pending else "No reboot-pending signals were found."
    return ToolResult(not error, title, summary, details, [error] if error else [])


def check_battery_report():
    title = "Battery Report"
    if not is_windows():
        return windows_only_result(title)
    data, error = _run_json_powershell(
        "$battery = Get-CimInstance -ClassName Win32_Battery -ErrorAction SilentlyContinue; "
        "if (-not $battery) { [pscustomobject]@{Present=$false} | ConvertTo-Json -Compress; return }; "
        "$bat = if ($battery -is [array]) { $battery[0] } else { $battery }; "
        "[pscustomobject]@{"
        "Present=$true;"
        "Name=$bat.Name;"
        "Status=$bat.Status;"
        "EstimatedChargeRemaining=$bat.EstimatedChargeRemaining;"
        "BatteryStatus=$bat.BatteryStatus;"
        "DesignCapacity=$bat.DesignCapacity;"
        "FullChargedCapacity=$bat.FullChargedCapacity"
        "} | ConvertTo-Json -Compress",
        timeout=20,
    )
    if not isinstance(data, dict):
        return ToolResult(False, title, "Could not read battery information.", errors=[error] if error else [])
    if not data.get("Present"):
        return ToolResult(True, title, "No battery was detected (desktop or battery class unavailable).")
    details = [
        f"Name: {data.get('Name') or 'Battery'}",
        f"Status: {data.get('Status') or 'Unknown'}",
        f"Charge remaining: {data.get('EstimatedChargeRemaining', '?')}%",
    ]
    design = data.get("DesignCapacity")
    full = data.get("FullChargedCapacity")
    if design and full:
        try:
            health = (float(full) / float(design)) * 100.0
            details.append(f"Capacity health estimate: {health:.0f}% ({full} / {design})")
        except (TypeError, ValueError, ZeroDivisionError):
            pass
    return ToolResult(not error, title, "Battery status checked.", details, [error] if error else [])


def restart_explorer():
    title = "Restart Explorer"
    if not is_windows():
        return windows_only_result(title)
    kill_code, kill_out, kill_err = _run_command(["taskkill", "/F", "/IM", "explorer.exe"], timeout=20)
    start_code, start_out, start_err = _run_command(
        ["cmd.exe", "/c", "start", "", "explorer.exe"],
        timeout=20,
    )
    details = [line for line in (kill_out, start_out) if line]
    errors = [line for line in (kill_err, start_err) if line]
    # taskkill returns non-zero when Explorer was not running; still try to start it.
    success = start_code == 0
    return ToolResult(
        success,
        title,
        "Windows Explorer restart requested." if success else "Could not restart Windows Explorer.",
        details,
        errors,
    )


_SETTINGS_PAGES = {
    "display": "ms-settings:display",
    "network": "ms-settings:network",
    "windows_update": "ms-settings:windowsupdate",
    "apps": "ms-settings:appsfeatures",
    "sound": "ms-settings:sound",
    "storage": "ms-settings:storagesense",
    "power": "ms-settings:powersleep",
    "privacy": "ms-settings:privacy",
    "troubleshoot": "ms-settings:troubleshoot",
    "about": "ms-settings:about",
}


def open_windows_settings(page):
    title = "Open Settings"
    if not is_windows():
        return windows_only_result(title)
    key = str(page or "").strip().lower()
    uri = _SETTINGS_PAGES.get(key)
    if not uri:
        return ToolResult(
            False,
            title,
            "Unsupported Settings page.",
            errors=[f"Allowed pages: {', '.join(sorted(_SETTINGS_PAGES))}"],
        )
    try:
        os.startfile(uri)  # noqa: S606 - fixed ms-settings allowlist only
    except OSError as exc:
        return ToolResult(False, title, "Could not open Windows Settings.", errors=[str(exc)])
    return ToolResult(True, title, f"Opened Windows Settings ({key}).", [uri])


def _known_folders():
    local = os.environ.get("LOCALAPPDATA", "")
    appdata = os.environ.get("APPDATA", "")
    home = Path.home()
    return {
        "temp": os.environ.get("TEMP") or os.environ.get("TMP") or "",
        "downloads": str(home / "Downloads"),
        "desktop": str(home / "Desktop"),
        "documents": str(home / "Documents"),
        "pictures": str(home / "Pictures"),
        "startup": os.path.join(appdata, r"Microsoft\Windows\Start Menu\Programs\Startup"),
        "local_appdata": local,
        "recycle_bin": "shell:RecycleBinFolder",
    }


def open_known_folder(folder_key):
    title = "Open Folder"
    key = str(folder_key or "").strip().lower()
    folders = _known_folders()
    target = folders.get(key)
    if not target:
        return ToolResult(
            False,
            title,
            "Unsupported folder.",
            errors=[f"Allowed folders: {', '.join(sorted(folders))}"],
        )
    if key != "recycle_bin" and not os.path.isdir(target):
        return ToolResult(False, title, "That folder does not exist on this PC.", errors=[target])
    try:
        if key == "recycle_bin":
            if not is_windows():
                return windows_only_result(title)
            code, _stdout, stderr = _run_command(["explorer.exe", "shell:RecycleBinFolder"], timeout=15)
            if code != 0:
                return ToolResult(False, title, "Could not open Recycle Bin.", errors=[stderr] if stderr else [])
        else:
            os.startfile(target)  # noqa: S606 - fixed known-folder allowlist only
    except OSError as exc:
        return ToolResult(False, title, "Could not open the folder.", errors=[str(exc)])
    return ToolResult(True, title, f"Opened {key}.", [target])


def create_restore_point(description="PC Fix restore point"):
    title = "Create Restore Point"
    if not is_windows():
        return windows_only_result(title)
    safe_description = str(description or "PC Fix restore point").replace("'", "''")[:80]
    code, stdout, stderr = _run_powershell(
        f"Checkpoint-Computer -Description '{safe_description}' -RestorePointType MODIFY_SETTINGS -ErrorAction Stop",
        timeout=60,
    )
    success = code == 0
    return ToolResult(
        success,
        title,
        "Restore point created." if success else "Could not create a restore point.",
        [stdout] if stdout else [],
        [stderr] if stderr else [],
    )


def export_pc_report(path=None):
    title = "Export PC Report"
    target = Path(path) if path else REPORTS_DIR / f"pc_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        snapshot = []
        cpu = sysinfo.get_cpu_stats()
        mem = sysinfo.get_memory_stats()
        disks = sysinfo.get_disk_usage()
        snapshot.append("PC Fix Diagnostic Report")
        snapshot.append(f"Generated: {datetime.now().isoformat(timespec='seconds')}")
        snapshot.append("")
        snapshot.append(f"CPU: {cpu.get('percent', 0):.0f}%")
        snapshot.append(
            f"Memory: {sysinfo.format_bytes(mem.get('used', 0))} / "
            f"{sysinfo.format_bytes(mem.get('total', 0))} ({mem.get('percent', 0):.0f}%)"
        )
        snapshot.append("")
        snapshot.append("Disks:")
        for disk in disks:
            snapshot.append(
                f"- {disk['mountpoint']} {sysinfo.format_bytes(disk['free'])} free "
                f"of {sysinfo.format_bytes(disk['total'])} ({disk['percent']:.0f}% used)"
            )
        snapshot.append("")
        snapshot.append("Startup Review:")
        for line in review_startup_impact().details[:20]:
            snapshot.append(f"- {line}")
        target.write_text("\n".join(snapshot), encoding="utf-8")
    except Exception as exc:
        return ToolResult(False, title, "Could not export the PC report.", errors=[str(exc)])
    return ToolResult(True, title, f"Report exported to {target}.", [str(target)])
