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
