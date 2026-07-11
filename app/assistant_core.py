import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from uuid import uuid4

from app import system_info as sysinfo
from app import toolbox, tool_history


@dataclass
class AssistantSnapshot:
    timestamp: datetime
    cpu: dict | None = None
    memory: dict | None = None
    disks: list = field(default_factory=list)
    network: dict | None = None
    hardware_summary: dict = field(default_factory=dict)
    startup_items: list = field(default_factory=list)
    installed_programs_summary: dict = field(default_factory=dict)
    top_cpu_processes: list = field(default_factory=list)
    top_memory_processes: list = field(default_factory=list)
    displays: list = field(default_factory=list)
    audio_devices: list = field(default_factory=list)
    audio_sessions: list = field(default_factory=list)
    saved_layouts: list = field(default_factory=list)
    cleanup_categories: list = field(default_factory=list)
    unavailable: list = field(default_factory=list)


@dataclass
class AssistantTurn:
    user: str
    assistant: str
    timestamp: datetime
    action_ids: list = field(default_factory=list)


@dataclass
class AssistantAction:
    id: str
    kind: str
    title: str
    description: str
    risk: str
    payload: dict = field(default_factory=dict)
    confirm_label: str = "Confirm"
    cancel_label: str = "Cancel"
    requires_confirmation: bool = False
    handler: str = "local"


@dataclass
class AssistantActionResult:
    success: bool
    message: str
    errors: list = field(default_factory=list)


@dataclass(frozen=True)
class AssistantTool:
    kind: str
    title: str
    description: str
    risk: str = "Read-only"
    handler: str = "local"
    requires_confirmation: bool = False
    payload_schema: dict = field(default_factory=dict)
    confirm_label: str = "Run"
    keywords: tuple = field(default_factory=tuple)


@dataclass(frozen=True)
class AssistantSkill:
    name: str
    description: str
    input_schema: dict
    risk: str
    requires_confirmation: bool
    action_kind: str
    examples: tuple = field(default_factory=tuple)
    enabled: bool = True


@dataclass
class SkillValidationResult:
    success: bool
    message: str = ""


READ_ONLY = "Read-only"
LOW_RISK = "Low"
MEDIUM_RISK = "Medium"
HIGH_RISK = "High"

ASSISTANT_TOOLS = {
    "refresh_snapshot": AssistantTool(
        "refresh_snapshot",
        "Refresh PC snapshot",
        "Collect fresh CPU, RAM, disk, startup, process, display, network, hardware, audio, and layout details.",
        confirm_label="Refresh",
        keywords=("health", "slow", "cpu", "ram", "memory", "disk", "space", "snapshot", "status"),
    ),
    "inspect_top_processes": AssistantTool(
        "inspect_top_processes",
        "Show top CPU/RAM processes",
        "Refresh the process list so the assistant can focus on the busiest apps.",
        confirm_label="Inspect",
        keywords=("process", "processes", "task", "tasks", "cpu", "ram", "memory", "slow"),
    ),
    "refresh_network": AssistantTool(
        "refresh_network",
        "Refresh network activity",
        "Collect current sent and received network counters.",
        confirm_label="Refresh",
        keywords=("network", "internet", "wifi", "ethernet", "upload", "download"),
    ),
    "refresh_hardware": AssistantTool(
        "refresh_hardware",
        "Refresh hardware summary",
        "Collect a high-level CPU, GPU, memory, disk, motherboard, BIOS, and OS summary.",
        confirm_label="Refresh",
        keywords=("hardware", "gpu", "bios", "motherboard", "pc setup", "spec", "specs"),
    ),
    "refresh_startup": AssistantTool(
        "refresh_startup",
        "Refresh startup and programs",
        "Reload startup entries and installed-program summary.",
        confirm_label="Refresh",
        keywords=("startup", "program", "programs", "installed", "launch", "boot"),
    ),
    "refresh_displays": AssistantTool(
        "refresh_displays",
        "Refresh display information",
        "Reload connected monitors, current modes, and supported refresh rates.",
        handler="tab",
        confirm_label="Refresh",
        keywords=("display", "monitor", "refresh rate", "screen"),
    ),
    "refresh_audio": AssistantTool(
        "refresh_audio",
        "Refresh audio information",
        "Reload playback devices and active app audio sessions.",
        handler="tab",
        confirm_label="Refresh",
        keywords=("audio", "sound", "speaker", "volume", "mute", "route"),
    ),
    "refresh_layouts": AssistantTool(
        "refresh_layouts",
        "Refresh layouts",
        "Reload open windows and saved window layouts.",
        handler="tab",
        confirm_label="Refresh",
        keywords=("layout", "layouts", "window", "windows", "desktop"),
    ),
    "scan_cleanup": AssistantTool(
        "scan_cleanup",
        "Scan safe cleanup locations",
        "Scan known temp, browser cache, thumbnail cache, and Recycle Bin locations.",
        confirm_label="Scan",
        keywords=("clean", "cleanup", "junk", "temp", "cache", "free space"),
    ),
    "clean_cleanup_candidates": AssistantTool(
        "clean_cleanup_candidates",
        "Clean scanned safe categories",
        "Delete only cleanup categories that were already scanned and shown to you.",
        risk=MEDIUM_RISK,
        requires_confirmation=True,
        payload_schema={"category_keys": "list[str]"},
        confirm_label="Clean",
        keywords=("clean", "cleanup", "delete", "junk", "temp", "cache", "free space"),
    ),
    "set_display_refresh_rate": AssistantTool(
        "set_display_refresh_rate",
        "Change display refresh rate",
        "Change only the selected monitor refresh rate, leaving resolution and scaling untouched.",
        risk=MEDIUM_RISK,
        requires_confirmation=True,
        payload_schema={"device_name": "str", "hz": "int"},
        confirm_label="Change",
        keywords=("refresh rate", "hz", "hertz", "monitor"),
    ),
    "audio_set_volume": AssistantTool(
        "audio_set_volume",
        "Set app volume",
        "Set one active audio session to the requested volume.",
        risk=LOW_RISK,
        requires_confirmation=True,
        payload_schema={"pid": "int", "level": "float"},
        confirm_label="Set Volume",
        keywords=("volume", "louder", "quieter"),
    ),
    "audio_mute_session": AssistantTool(
        "audio_mute_session",
        "Mute app audio",
        "Mute one active audio session.",
        risk=LOW_RISK,
        requires_confirmation=True,
        payload_schema={"pid": "int", "muted": "bool"},
        confirm_label="Mute",
        keywords=("mute", "silence"),
    ),
    "audio_route_session": AssistantTool(
        "audio_route_session",
        "Route app audio",
        "Route one active audio session to a specific playback device.",
        risk=LOW_RISK,
        requires_confirmation=True,
        payload_schema={"pid": "int", "process_name": "str", "device_id": "str"},
        confirm_label="Route",
        keywords=("route", "speaker", "headphone", "output"),
    ),
    "load_saved_layout": AssistantTool(
        "load_saved_layout",
        "Load saved layout",
        "Move matching windows and launch missing apps when possible for a saved layout.",
        risk=MEDIUM_RISK,
        requires_confirmation=True,
        payload_schema={"layout_id": "str"},
        confirm_label="Load",
        keywords=("load layout", "restore layout", "arrange windows"),
    ),
    "check_windows_updates": AssistantTool(
        "check_windows_updates",
        "Check Windows Update",
        "Read pending Windows Update, reboot, and recent hotfix status.",
        confirm_label="Check",
        keywords=("windows update", "updates", "pending update", "reboot pending"),
    ),
    "check_disk_health": AssistantTool(
        "check_disk_health",
        "Check disk health",
        "Read physical disk health, media type, operational status, and size.",
        confirm_label="Check",
        keywords=("disk health", "smart", "drive health", "ssd", "hdd"),
    ),
    "scan_event_log_errors": AssistantTool(
        "scan_event_log_errors",
        "Scan event log errors",
        "Summarize recent critical and error events from System and Application logs.",
        payload_schema={"hours": "int?"},
        confirm_label="Scan",
        keywords=("event log", "errors", "crash", "critical event", "blue screen"),
    ),
    "check_network_health": AssistantTool(
        "check_network_health",
        "Check network health",
        "Check local IPs, active adapters, DNS servers, and basic internet reachability.",
        confirm_label="Check",
        keywords=("network health", "internet", "wifi", "dns", "connection"),
    ),
    "flush_dns_cache": AssistantTool(
        "flush_dns_cache",
        "Flush DNS cache",
        "Clear the Windows DNS resolver cache.",
        risk=LOW_RISK,
        requires_confirmation=True,
        confirm_label="Flush DNS",
        keywords=("flush dns", "clear dns", "dns cache"),
    ),
    "restart_network_adapter": AssistantTool(
        "restart_network_adapter",
        "Restart network adapter",
        "Restart one named network adapter.",
        risk=MEDIUM_RISK,
        requires_confirmation=True,
        payload_schema={"adapter_name": "str"},
        confirm_label="Restart",
        keywords=("restart adapter", "restart network", "reset wifi", "reset ethernet"),
    ),
    "check_power_plan": AssistantTool(
        "check_power_plan",
        "Check power plan",
        "Read the active Windows power plan and available schemes.",
        confirm_label="Check",
        keywords=("power plan", "battery", "performance mode"),
    ),
    "set_power_plan": AssistantTool(
        "set_power_plan",
        "Set power plan",
        "Switch the active Windows power plan to Balanced, High Performance, or Power Saver.",
        risk=LOW_RISK,
        requires_confirmation=True,
        payload_schema={"plan_name": "str"},
        confirm_label="Set Plan",
        keywords=("set power plan", "high performance", "balanced", "power saver"),
    ),
    "review_startup_impact": AssistantTool(
        "review_startup_impact",
        "Review startup impact",
        "Classify startup entries with conservative keep/review/optional hints.",
        confirm_label="Review",
        keywords=("startup impact", "startup review", "boot apps"),
    ),
    "check_windows_security": AssistantTool(
        "check_windows_security",
        "Check Windows Security",
        "Read Defender and firewall status.",
        confirm_label="Check",
        keywords=("windows security", "defender", "firewall", "antivirus"),
    ),
    "scan_large_files": AssistantTool(
        "scan_large_files",
        "Scan large files",
        "Find large files under a selected root without deleting anything.",
        payload_schema={"root": "str?", "min_size_mb": "int?"},
        confirm_label="Scan",
        keywords=("large files", "big files", "find space", "disk space"),
    ),
    "create_restore_point": AssistantTool(
        "create_restore_point",
        "Create restore point",
        "Ask Windows to create a system restore point before higher-risk changes.",
        risk=MEDIUM_RISK,
        requires_confirmation=True,
        payload_schema={"description": "str?"},
        confirm_label="Create",
        keywords=("restore point", "system restore"),
    ),
    "export_pc_report": AssistantTool(
        "export_pc_report",
        "Export PC report",
        "Write a local diagnostic report with system summary and recommendations.",
        confirm_label="Export",
        keywords=("report", "export", "diagnostic report"),
    ),
}

ASSISTANT_SKILLS = {
    "diagnose_pc_health": AssistantSkill(
        "diagnose_pc_health",
        "Refresh the PC snapshot and summarize overall health.",
        {},
        ASSISTANT_TOOLS["refresh_snapshot"].risk,
        ASSISTANT_TOOLS["refresh_snapshot"].requires_confirmation,
        "refresh_snapshot",
        examples=({"type": "skill_request", "skill": "diagnose_pc_health", "arguments": {}},),
    ),
    "inspect_top_processes": AssistantSkill(
        "inspect_top_processes",
        "Refresh the top CPU and RAM process lists.",
        {},
        ASSISTANT_TOOLS["inspect_top_processes"].risk,
        ASSISTANT_TOOLS["inspect_top_processes"].requires_confirmation,
        "inspect_top_processes",
    ),
    "refresh_network": AssistantSkill(
        "refresh_network",
        "Refresh network sent/received counters.",
        {},
        ASSISTANT_TOOLS["refresh_network"].risk,
        ASSISTANT_TOOLS["refresh_network"].requires_confirmation,
        "refresh_network",
    ),
    "refresh_hardware": AssistantSkill(
        "refresh_hardware",
        "Refresh the hardware summary.",
        {},
        ASSISTANT_TOOLS["refresh_hardware"].risk,
        ASSISTANT_TOOLS["refresh_hardware"].requires_confirmation,
        "refresh_hardware",
    ),
    "refresh_startup_programs": AssistantSkill(
        "refresh_startup_programs",
        "Refresh startup items and installed-program summary.",
        {},
        ASSISTANT_TOOLS["refresh_startup"].risk,
        ASSISTANT_TOOLS["refresh_startup"].requires_confirmation,
        "refresh_startup",
    ),
    "scan_cleanup": AssistantSkill(
        "scan_cleanup",
        "Scan safe cleanup locations before any deletion.",
        {},
        ASSISTANT_TOOLS["scan_cleanup"].risk,
        ASSISTANT_TOOLS["scan_cleanup"].requires_confirmation,
        "scan_cleanup",
        examples=({"type": "skill_request", "skill": "scan_cleanup", "arguments": {}},),
    ),
    "clean_scanned_cleanup": AssistantSkill(
        "clean_scanned_cleanup",
        "Clean cleanup categories that were already scanned.",
        {"category_keys": "list[str]?"},
        ASSISTANT_TOOLS["clean_cleanup_candidates"].risk,
        ASSISTANT_TOOLS["clean_cleanup_candidates"].requires_confirmation,
        "clean_cleanup_candidates",
    ),
    "refresh_displays": AssistantSkill(
        "refresh_displays",
        "Refresh connected display information.",
        {},
        ASSISTANT_TOOLS["refresh_displays"].risk,
        ASSISTANT_TOOLS["refresh_displays"].requires_confirmation,
        "refresh_displays",
    ),
    "set_display_refresh_rate": AssistantSkill(
        "set_display_refresh_rate",
        "Change a display refresh rate after Python resolves a display target.",
        {"hz": "int", "device_name": "str?", "display_label": "str?"},
        ASSISTANT_TOOLS["set_display_refresh_rate"].risk,
        ASSISTANT_TOOLS["set_display_refresh_rate"].requires_confirmation,
        "set_display_refresh_rate",
        examples=({"type": "skill_request", "skill": "set_display_refresh_rate", "arguments": {"display_label": "Dell", "hz": 144}},),
    ),
    "refresh_audio": AssistantSkill(
        "refresh_audio",
        "Refresh playback devices and active app audio sessions.",
        {},
        ASSISTANT_TOOLS["refresh_audio"].risk,
        ASSISTANT_TOOLS["refresh_audio"].requires_confirmation,
        "refresh_audio",
    ),
    "set_app_volume": AssistantSkill(
        "set_app_volume",
        "Set one app audio session volume after Python resolves the app target.",
        {"level": "float", "pid": "int?", "process_name": "str?", "app": "str?"},
        ASSISTANT_TOOLS["audio_set_volume"].risk,
        ASSISTANT_TOOLS["audio_set_volume"].requires_confirmation,
        "audio_set_volume",
        examples=({"type": "skill_request", "skill": "set_app_volume", "arguments": {"app": "chrome", "level": 0.35}},),
    ),
    "mute_app_audio": AssistantSkill(
        "mute_app_audio",
        "Mute or unmute one app audio session after Python resolves the app target.",
        {"muted": "bool", "pid": "int?", "process_name": "str?", "app": "str?"},
        ASSISTANT_TOOLS["audio_mute_session"].risk,
        ASSISTANT_TOOLS["audio_mute_session"].requires_confirmation,
        "audio_mute_session",
    ),
    "route_app_audio": AssistantSkill(
        "route_app_audio",
        "Route one app audio session to a playback device after Python resolves both targets.",
        {"pid": "int?", "process_name": "str?", "app": "str?", "device_id": "str?", "device_name": "str?"},
        ASSISTANT_TOOLS["audio_route_session"].risk,
        ASSISTANT_TOOLS["audio_route_session"].requires_confirmation,
        "audio_route_session",
    ),
    "refresh_layouts": AssistantSkill(
        "refresh_layouts",
        "Refresh current windows and saved layouts.",
        {},
        ASSISTANT_TOOLS["refresh_layouts"].risk,
        ASSISTANT_TOOLS["refresh_layouts"].requires_confirmation,
        "refresh_layouts",
    ),
    "load_saved_layout": AssistantSkill(
        "load_saved_layout",
        "Load a saved window layout after Python resolves the layout target.",
        {"layout_id": "str?", "layout_name": "str?"},
        ASSISTANT_TOOLS["load_saved_layout"].risk,
        ASSISTANT_TOOLS["load_saved_layout"].requires_confirmation,
        "load_saved_layout",
    ),
    "check_windows_updates": AssistantSkill(
        "check_windows_updates",
        "Read Windows Update pending update, reboot, and last hotfix status.",
        {},
        ASSISTANT_TOOLS["check_windows_updates"].risk,
        ASSISTANT_TOOLS["check_windows_updates"].requires_confirmation,
        "check_windows_updates",
    ),
    "check_disk_health": AssistantSkill(
        "check_disk_health",
        "Read physical disk health and operational status.",
        {},
        ASSISTANT_TOOLS["check_disk_health"].risk,
        ASSISTANT_TOOLS["check_disk_health"].requires_confirmation,
        "check_disk_health",
    ),
    "scan_event_log_errors": AssistantSkill(
        "scan_event_log_errors",
        "Summarize recent Windows critical and error events.",
        {"hours": "int?"},
        ASSISTANT_TOOLS["scan_event_log_errors"].risk,
        ASSISTANT_TOOLS["scan_event_log_errors"].requires_confirmation,
        "scan_event_log_errors",
    ),
    "check_network_health": AssistantSkill(
        "check_network_health",
        "Check local adapters, DNS, and basic internet reachability.",
        {},
        ASSISTANT_TOOLS["check_network_health"].risk,
        ASSISTANT_TOOLS["check_network_health"].requires_confirmation,
        "check_network_health",
    ),
    "flush_dns_cache": AssistantSkill(
        "flush_dns_cache",
        "Clear the Windows DNS resolver cache.",
        {},
        ASSISTANT_TOOLS["flush_dns_cache"].risk,
        ASSISTANT_TOOLS["flush_dns_cache"].requires_confirmation,
        "flush_dns_cache",
    ),
    "restart_network_adapter": AssistantSkill(
        "restart_network_adapter",
        "Restart one named network adapter.",
        {"adapter_name": "str"},
        ASSISTANT_TOOLS["restart_network_adapter"].risk,
        ASSISTANT_TOOLS["restart_network_adapter"].requires_confirmation,
        "restart_network_adapter",
    ),
    "check_power_plan": AssistantSkill(
        "check_power_plan",
        "Read the active Windows power plan.",
        {},
        ASSISTANT_TOOLS["check_power_plan"].risk,
        ASSISTANT_TOOLS["check_power_plan"].requires_confirmation,
        "check_power_plan",
    ),
    "set_power_plan": AssistantSkill(
        "set_power_plan",
        "Switch the active Windows power plan.",
        {"plan_name": "str"},
        ASSISTANT_TOOLS["set_power_plan"].risk,
        ASSISTANT_TOOLS["set_power_plan"].requires_confirmation,
        "set_power_plan",
    ),
    "review_startup_impact": AssistantSkill(
        "review_startup_impact",
        "Classify startup items with conservative keep/review/optional hints.",
        {},
        ASSISTANT_TOOLS["review_startup_impact"].risk,
        ASSISTANT_TOOLS["review_startup_impact"].requires_confirmation,
        "review_startup_impact",
    ),
    "check_windows_security": AssistantSkill(
        "check_windows_security",
        "Read Defender and firewall status.",
        {},
        ASSISTANT_TOOLS["check_windows_security"].risk,
        ASSISTANT_TOOLS["check_windows_security"].requires_confirmation,
        "check_windows_security",
    ),
    "scan_large_files": AssistantSkill(
        "scan_large_files",
        "Find large files without deleting anything.",
        {"root": "str?", "min_size_mb": "int?"},
        ASSISTANT_TOOLS["scan_large_files"].risk,
        ASSISTANT_TOOLS["scan_large_files"].requires_confirmation,
        "scan_large_files",
    ),
    "create_restore_point": AssistantSkill(
        "create_restore_point",
        "Create a Windows restore point.",
        {"description": "str?"},
        ASSISTANT_TOOLS["create_restore_point"].risk,
        ASSISTANT_TOOLS["create_restore_point"].requires_confirmation,
        "create_restore_point",
    ),
    "export_pc_report": AssistantSkill(
        "export_pc_report",
        "Export a local PC diagnostic report.",
        {},
        ASSISTANT_TOOLS["export_pc_report"].risk,
        ASSISTANT_TOOLS["export_pc_report"].requires_confirmation,
        "export_pc_report",
    ),
}

TAB_ACTION_KINDS = {
    kind
    for kind, tool in ASSISTANT_TOOLS.items()
    if tool.handler == "tab"
}


def _tool(kind):
    return ASSISTANT_TOOLS[kind]


def _action(kind, title=None, description=None, risk=None, payload=None, confirm_label=None):
    tool = _tool(kind)
    return AssistantAction(
        id=str(uuid4()),
        kind=kind,
        title=title or tool.title,
        description=description or tool.description,
        risk=risk or tool.risk,
        payload=payload or {},
        confirm_label=confirm_label or tool.confirm_label,
        requires_confirmation=tool.requires_confirmation,
        handler=tool.handler,
    )


def get_assistant_tools():
    return dict(ASSISTANT_TOOLS)


def get_assistant_skills():
    return dict(ASSISTANT_SKILLS)


def render_skill_catalog():
    lines = [
        "Available assistant skills:",
        "When useful, include one or more fenced JSON skill requests exactly like:",
        '```json\n{"type":"skill_request","skill":"scan_cleanup","arguments":{}}\n```',
        "Never invent skills. Never request shell commands, arbitrary code, registry edits, or arbitrary file deletion.",
    ]
    for skill in ASSISTANT_SKILLS.values():
        if not skill.enabled:
            continue
        args = ", ".join(f"{name}: {kind}" for name, kind in skill.input_schema.items()) or "none"
        confirmation = "confirmation required" if skill.requires_confirmation else "read-only action card"
        lines.append(
            f"- {skill.name}: {skill.description} Args: {args}. "
            f"Risk: {skill.risk}; {confirmation}."
        )
    return "\n".join(lines)


def collect_assistant_snapshot(include_cleanup=False):
    snapshot = AssistantSnapshot(timestamp=datetime.now())

    try:
        sysinfo.prime_process_cpu_percent()
    except Exception:
        pass

    try:
        snapshot.cpu = sysinfo.get_cpu_stats()
    except Exception:
        snapshot.unavailable.append("CPU")

    try:
        snapshot.memory = sysinfo.get_memory_stats()
    except Exception:
        snapshot.unavailable.append("RAM")

    try:
        snapshot.disks = sysinfo.get_disk_usage()[:4]
    except Exception:
        snapshot.unavailable.append("disks")

    try:
        snapshot.network = sysinfo.get_network_counters()
    except Exception:
        snapshot.unavailable.append("network")

    try:
        hardware = sysinfo.get_hardware_info()
        snapshot.hardware_summary = _hardware_summary(hardware)
    except Exception:
        snapshot.unavailable.append("hardware")

    try:
        snapshot.startup_items = sysinfo.get_startup_items()
    except Exception:
        snapshot.unavailable.append("startup apps")

    try:
        programs = sysinfo.get_installed_programs()
        snapshot.installed_programs_summary = _program_summary(programs)
    except Exception:
        snapshot.unavailable.append("installed programs")

    try:
        snapshot.top_cpu_processes = sysinfo.get_top_processes(limit=5, sort_by="cpu")
    except Exception:
        snapshot.unavailable.append("CPU processes")

    try:
        snapshot.top_memory_processes = sysinfo.get_top_processes(limit=3, sort_by="mem")
    except Exception:
        snapshot.unavailable.append("RAM processes")

    try:
        displays = []
        for device in sysinfo.get_display_devices()[:3]:
            mode = None
            try:
                mode = sysinfo.get_current_display_mode(device.name)
                mode_text = f"{mode.width}x{mode.height} @ {mode.refresh_hz} Hz"
            except Exception:
                mode_text = "mode unavailable"
            try:
                rates = sysinfo.get_supported_refresh_rates(device.name)
            except Exception:
                rates = []
            displays.append({
                "name": device.name,
                "label": device.label,
                "primary": bool(device.is_primary),
                "mode": mode_text,
                "current_hz": mode.refresh_hz if mode else None,
                "supported_rates": rates,
            })
        snapshot.displays = displays
    except Exception:
        snapshot.unavailable.append("displays")

    try:
        snapshot.audio_devices, snapshot.audio_sessions = _audio_snapshot()
    except Exception:
        snapshot.unavailable.append("audio")

    try:
        snapshot.saved_layouts = _layout_snapshot()
    except Exception:
        snapshot.unavailable.append("layouts")

    if include_cleanup:
        try:
            snapshot.cleanup_categories = sysinfo.scan_cleanup_targets()
        except Exception:
            snapshot.unavailable.append("cleanup candidates")

    return snapshot


def _hardware_summary(hardware):
    def first_name(items, *keys):
        for item in items or []:
            for key in keys:
                value = item.get(key) if isinstance(item, dict) else None
                if value:
                    return str(value)
        return ""

    disks = hardware.get("disk_drives") or hardware.get("physical_disks") or []
    memory_modules = hardware.get("memory_modules") or []
    return {
        "cpu": first_name(hardware.get("cpu"), "Name", "name"),
        "gpu": first_name(hardware.get("gpu"), "Name", "name"),
        "system": first_name(hardware.get("system"), "Model", "Name", "model", "name"),
        "board": first_name(hardware.get("board"), "Product", "Name", "product", "name"),
        "bios": first_name(hardware.get("bios"), "SMBIOSBIOSVersion", "Name", "Version", "version"),
        "os": first_name(hardware.get("os"), "Caption", "Name", "caption", "name"),
        "logical_cores": hardware.get("logical_cores"),
        "physical_cores": hardware.get("physical_cores"),
        "disk_count": len(disks),
        "memory_module_count": len(memory_modules),
    }


def _program_summary(programs):
    publishers = {}
    for program in programs:
        publisher = str(program.get("publisher") or "Unknown")
        publishers[publisher] = publishers.get(publisher, 0) + 1
    top_publishers = sorted(publishers.items(), key=lambda item: item[1], reverse=True)[:3]
    largest = sorted(programs, key=lambda item: item.get("size_bytes") or 0, reverse=True)[:3]
    return {
        "count": len(programs),
        "top_publishers": top_publishers,
        "largest": [
            {
                "name": item.get("name", ""),
                "size_bytes": item.get("size_bytes") or 0,
            }
            for item in largest
            if item.get("size_bytes")
        ],
    }


def _audio_snapshot():
    from app import audio_control

    devices = [
        {"id": device.id, "name": device.name, "is_default": bool(device.is_default)}
        for device in audio_control.list_output_devices()
    ]
    sessions = [
        {
            "pid": session.pid,
            "process_name": session.process_name,
            "display_name": session.display_name,
            "device_id": session.device_id,
            "device_name": session.device_name,
            "volume": session.volume,
            "muted": session.muted,
        }
        for session in audio_control.list_output_sessions()
    ]
    return devices, sessions


def _layout_snapshot():
    from app import window_layouts

    layouts = []
    for layout in window_layouts.load_layouts()[:8]:
        layouts.append({
            "id": layout.get("id", ""),
            "name": layout.get("name", "Untitled Layout"),
            "windows": len(layout.get("windows", [])),
            "displays": len(layout.get("displays", [])),
            "updated_at": layout.get("updated_at", ""),
        })
    return layouts


def snapshot_has_useful_data(snapshot):
    return any([
        snapshot.cpu,
        snapshot.memory,
        snapshot.disks,
        snapshot.startup_items,
        snapshot.top_cpu_processes,
        snapshot.top_memory_processes,
        snapshot.network,
        snapshot.hardware_summary,
        snapshot.installed_programs_summary,
        snapshot.displays,
        snapshot.audio_devices,
        snapshot.audio_sessions,
        snapshot.saved_layouts,
        snapshot.cleanup_categories,
    ])


def render_snapshot_context(snapshot):
    lines = []

    if snapshot.cpu:
        cpu_percent = snapshot.cpu.get("percent")
        if cpu_percent is not None:
            lines.append(f"CPU: {cpu_percent:.0f}%")
        if snapshot.cpu.get("freq_mhz"):
            lines.append(f"CPU speed: {snapshot.cpu['freq_mhz']:.0f} MHz")
    else:
        lines.append("CPU: unavailable")

    if snapshot.memory:
        mem = snapshot.memory
        lines.append(
            f"RAM: {sysinfo.format_bytes(mem['used'])} / "
            f"{sysinfo.format_bytes(mem['total'])} ({mem['percent']:.0f}%)"
        )
    else:
        lines.append("RAM: unavailable")

    if snapshot.disks:
        for drive in snapshot.disks:
            lines.append(
                f"Disk {drive['mountpoint']}: "
                f"{sysinfo.format_bytes(drive['free'])} free of "
                f"{sysinfo.format_bytes(drive['total'])} "
                f"({drive['percent']:.0f}% used)"
            )
    else:
        lines.append("Disk: unavailable")

    if snapshot.network:
        lines.append(
            f"Network counters: sent {sysinfo.format_bytes(snapshot.network['bytes_sent'])}, "
            f"received {sysinfo.format_bytes(snapshot.network['bytes_recv'])}"
        )
    elif "network" in snapshot.unavailable:
        lines.append("Network: unavailable")

    if snapshot.hardware_summary:
        hardware = snapshot.hardware_summary
        if hardware.get("cpu"):
            lines.append(f"Hardware CPU: {hardware['cpu']}")
        if hardware.get("gpu"):
            lines.append(f"Hardware GPU: {hardware['gpu']}")
        if hardware.get("logical_cores"):
            lines.append(
                f"CPU cores: {hardware.get('physical_cores') or '?'} physical, "
                f"{hardware['logical_cores']} logical"
            )
    elif "hardware" in snapshot.unavailable:
        lines.append("Hardware: unavailable")

    if "startup apps" in snapshot.unavailable:
        lines.append("Startup apps: unavailable")
    else:
        lines.append(f"Startup apps: {len(snapshot.startup_items)} detected")
        for item in snapshot.startup_items[:5]:
            lines.append(f"- Startup: {item['name']} ({item['source']})")

    if snapshot.installed_programs_summary:
        program_count = snapshot.installed_programs_summary.get("count", 0)
        lines.append(f"Installed programs: {program_count} detected")
        for program in snapshot.installed_programs_summary.get("largest", [])[:3]:
            lines.append(
                f"- Large program: {program['name']} ({sysinfo.format_bytes(program['size_bytes'])})"
            )
    elif "installed programs" in snapshot.unavailable:
        lines.append("Installed programs: unavailable")

    if snapshot.top_cpu_processes:
        lines.append("Top processes (by CPU):")
        for proc in snapshot.top_cpu_processes:
            lines.append(
                f"- {proc['name']}: {proc['cpu']:.1f}% CPU, "
                f"{sysinfo.format_bytes(proc['mem'])}"
            )
    else:
        lines.append("Processes: unavailable")

    if snapshot.top_memory_processes:
        lines.append("Top processes (by RAM):")
        for proc in snapshot.top_memory_processes:
            lines.append(
                f"- {proc['name']}: {sysinfo.format_bytes(proc['mem'])}, "
                f"{proc['cpu']:.1f}% CPU"
            )

    if snapshot.displays:
        lines.append(f"Displays: {len(snapshot.displays)} connected")
        for display in snapshot.displays:
            primary = "primary" if display["primary"] else "secondary"
            lines.append(f"- Display: {display['label']} ({primary}), {display['mode']}")
    elif "displays" in snapshot.unavailable:
        lines.append("Displays: unavailable")
    else:
        lines.append("Displays: 0 connected")

    if snapshot.audio_devices or snapshot.audio_sessions:
        lines.append(
            f"Audio: {len(snapshot.audio_devices)} playback device(s), "
            f"{len(snapshot.audio_sessions)} active session(s)"
        )
        for session in snapshot.audio_sessions[:5]:
            muted = "muted" if session.get("muted") else f"{session.get('volume', 0) * 100:.0f}%"
            lines.append(f"- Audio: {session['display_name']} on {session.get('device_name') or 'default'} ({muted})")
    elif "audio" in snapshot.unavailable:
        lines.append("Audio: unavailable")

    if snapshot.saved_layouts:
        lines.append(f"Saved layouts: {len(snapshot.saved_layouts)} available")
        for layout in snapshot.saved_layouts[:5]:
            lines.append(
                f"- Layout: {layout['name']} ({layout['windows']} windows, {layout['displays']} displays)"
            )
    elif "layouts" in snapshot.unavailable:
        lines.append("Layouts: unavailable")

    if snapshot.cleanup_categories:
        total = sum(cat.size_bytes for cat in snapshot.cleanup_categories)
        lines.append(
            f"Cleanup candidates: {len(snapshot.cleanup_categories)} categories, "
            f"{sysinfo.format_bytes(total)} found"
        )
        for cat in snapshot.cleanup_categories[:5]:
            lines.append(
                f"- Cleanup: {cat.label}, {sysinfo.format_bytes(cat.size_bytes)}, "
                f"{cat.file_count} files"
            )
    elif "cleanup candidates" in snapshot.unavailable:
        lines.append("Cleanup candidates: unavailable")

    warnings = snapshot_warnings(snapshot)
    if warnings:
        lines.append("Warnings:")
        lines.extend(f"- {warning}" for warning in warnings)

    return "\n".join(lines)


def snapshot_warnings(snapshot):
    warnings = []
    if snapshot.cpu and snapshot.cpu.get("percent", 0) >= 85:
        warnings.append(f"High CPU load ({snapshot.cpu['percent']:.0f}%).")
    if snapshot.memory and snapshot.memory.get("percent", 0) >= 85:
        warnings.append(f"High RAM use ({snapshot.memory['percent']:.0f}%).")
    for drive in snapshot.disks:
        if drive.get("percent", 0) >= 90:
            warnings.append(
                f"Drive {drive['mountpoint']} is nearly full ({drive['percent']:.0f}% used)."
            )
    return warnings


def snapshot_summary_rows(snapshot):
    rows = []
    if snapshot.cpu and snapshot.cpu.get("percent") is not None:
        rows.append(("CPU", f"{snapshot.cpu['percent']:.0f}%"))
    else:
        rows.append(("CPU", "Unavailable"))

    if snapshot.memory:
        rows.append(("RAM", f"{snapshot.memory['percent']:.0f}% used"))
    else:
        rows.append(("RAM", "Unavailable"))

    if snapshot.disks:
        for drive in snapshot.disks:
            rows.append((f"Disk {drive['mountpoint']}", f"{drive['percent']:.0f}% used"))
    else:
        rows.append(("Disks", "Unavailable"))

    rows.append(("Startup", f"{len(snapshot.startup_items)} item(s)"))
    if snapshot.installed_programs_summary:
        rows.append(("Programs", f"{snapshot.installed_programs_summary.get('count', 0)} installed"))
    if snapshot.network:
        rows.append(("Network", f"{sysinfo.format_bytes(snapshot.network['bytes_recv'])} received"))
    if snapshot.hardware_summary:
        cpu = snapshot.hardware_summary.get("cpu") or "Available"
        rows.append(("Hardware", cpu))
    rows.append(("Displays", f"{len(snapshot.displays)} connected"))
    rows.append(("Audio", f"{len(snapshot.audio_sessions)} session(s)"))
    rows.append(("Layouts", f"{len(snapshot.saved_layouts)} saved"))

    if snapshot.cleanup_categories:
        total = sum(cat.size_bytes for cat in snapshot.cleanup_categories)
        rows.append(("Cleanup", f"{sysinfo.format_bytes(total)} found"))
    else:
        rows.append(("Cleanup", "Not scanned"))

    warnings = snapshot_warnings(snapshot)
    if warnings:
        rows.append(("Warnings", " ".join(warnings)))

    if snapshot.unavailable:
        rows.append(("Unavailable", ", ".join(snapshot.unavailable)))

    return rows


def propose_actions(user_text, snapshot=None):
    lowered = user_text.lower()
    actions = []
    added = set()

    def add(kind, **kwargs):
        if kind in added:
            return
        actions.append(_action(kind, **kwargs))
        added.add(kind)

    for kind, tool in ASSISTANT_TOOLS.items():
        if kind in {
            "clean_cleanup_candidates",
            "set_display_refresh_rate",
            "audio_set_volume",
            "audio_mute_session",
            "audio_route_session",
            "load_saved_layout",
            "restart_network_adapter",
            "set_power_plan",
        }:
            continue
        if _matches_any(lowered, tool.keywords):
            add(kind)

    if _matches_any(lowered, ("clean", "cleanup", "junk", "temp", "cache", "free space")):
        if snapshot and snapshot.cleanup_categories:
            total = sum(cat.size_bytes for cat in snapshot.cleanup_categories)
            add(
                "clean_cleanup_candidates",
                description=f"Delete the scanned temp/cache categories shown in the snapshot ({sysinfo.format_bytes(total)}).",
                payload={"category_keys": [cat.key for cat in snapshot.cleanup_categories]},
            )
        else:
            add("scan_cleanup")

    if snapshot:
        display_action = _display_refresh_action(lowered, snapshot)
        if display_action:
            add(display_action.kind, description=display_action.description, payload=display_action.payload)

        audio_action = _audio_action(lowered, snapshot)
        if audio_action:
            add(audio_action.kind, description=audio_action.description, payload=audio_action.payload)

        layout_action = _layout_action(lowered, snapshot)
        if layout_action:
            add(layout_action.kind, description=layout_action.description, payload=layout_action.payload)

    return actions


def _matches_any(text, keywords):
    return any(keyword in text for keyword in keywords)


def _display_refresh_action(lowered, snapshot):
    if not _matches_any(lowered, ("highest refresh", "max refresh", "maximum refresh", "change refresh", "set refresh")):
        return None
    displays = [display for display in snapshot.displays if display.get("supported_rates")]
    if not displays:
        return None
    display = next((item for item in displays if item.get("primary")), displays[0])
    current_hz = display.get("current_hz")
    target_hz = max(display.get("supported_rates") or [])
    if current_hz and int(target_hz) == int(current_hz):
        return None
    return _action(
        "set_display_refresh_rate",
        description=f"Change {display['label']} to {target_hz} Hz.",
        payload={"device_name": display["name"], "hz": int(target_hz)},
    )


def _audio_action(lowered, snapshot):
    sessions = snapshot.audio_sessions
    if len(sessions) != 1:
        return None
    session = sessions[0]
    if "unmute" in lowered:
        return _action(
            "audio_mute_session",
            title="Unmute app audio",
            description=f"Unmute {session['display_name']}.",
            payload={"pid": session["pid"], "muted": False},
            confirm_label="Unmute",
        )
    if "mute" in lowered or "silence" in lowered:
        return _action(
            "audio_mute_session",
            description=f"Mute {session['display_name']}.",
            payload={"pid": session["pid"], "muted": True},
        )
    volume = _requested_volume(lowered)
    if volume is not None:
        return _action(
            "audio_set_volume",
            description=f"Set {session['display_name']} volume to {int(volume * 100)}%.",
            payload={"pid": session["pid"], "level": volume},
        )
    if "route" in lowered and len(snapshot.audio_devices) == 1:
        device = snapshot.audio_devices[0]
        return _action(
            "audio_route_session",
            description=f"Route {session['display_name']} to {device['name']}.",
            payload={
                "pid": session["pid"],
                "process_name": session["process_name"],
                "device_id": device["id"],
            },
        )
    return None


def _requested_volume(text):
    match = re.search(r"(\d{1,3})\s*%", text)
    if not match:
        return None
    value = max(0, min(100, int(match.group(1))))
    return value / 100.0


def _layout_action(lowered, snapshot):
    if not _matches_any(lowered, ("load layout", "restore layout", "arrange windows")):
        return None
    if not snapshot.saved_layouts:
        return None
    layout = snapshot.saved_layouts[0]
    return _action(
        "load_saved_layout",
        description=f"Load saved layout \"{layout['name']}\".",
        payload={"layout_id": layout["id"]},
    )


def extract_skill_requests(text):
    requests = []
    seen_spans = []

    for match in re.finditer(r"```(?:json)?\s*(.*?)```", text or "", re.IGNORECASE | re.DOTALL):
        seen_spans.append(match.span())
        requests.extend(_skill_requests_from_json_text(match.group(1)))

    decoder = json.JSONDecoder()
    index = 0
    text = text or ""
    while index < len(text):
        if any(start <= index < end for start, end in seen_spans):
            index += 1
            continue
        if text[index] != "{":
            index += 1
            continue
        try:
            value, end = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            index += 1
            continue
        requests.extend(_skill_requests_from_value(value))
        index += max(end, 1)

    return requests


def _skill_requests_from_json_text(text):
    try:
        value = json.loads((text or "").strip())
    except (TypeError, json.JSONDecodeError):
        return []
    return _skill_requests_from_value(value)


def _skill_requests_from_value(value):
    if isinstance(value, dict) and value.get("type") == "skill_request":
        return [value]
    if isinstance(value, list):
        requests = []
        for item in value:
            requests.extend(_skill_requests_from_value(item))
        return requests
    return []


def strip_skill_requests(text):
    def replace_fenced(match):
        requests = _skill_requests_from_json_text(match.group(1))
        return "" if requests else match.group(0)

    stripped = re.sub(r"```(?:json)?\s*(.*?)```", replace_fenced, text or "", flags=re.IGNORECASE | re.DOTALL)
    stripped = _strip_raw_skill_json(stripped)
    if _looks_like_only_skill_json(stripped):
        stripped = ""
    return re.sub(r"\n{3,}", "\n\n", stripped).strip()


def _strip_raw_skill_json(text):
    decoder = json.JSONDecoder()
    spans = []
    index = 0
    text = text or ""
    while index < len(text):
        if text[index] != "{":
            index += 1
            continue
        try:
            value, end = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            index += 1
            continue
        if _skill_requests_from_value(value):
            spans.append((index, index + end))
        index += max(end, 1)
    if not spans:
        return text
    parts = []
    last = 0
    for start, end in spans:
        parts.append(text[last:start])
        last = end
    parts.append(text[last:])
    return "".join(parts)


def _looks_like_only_skill_json(text):
    compact = (text or "").strip()
    if not compact:
        return False
    try:
        value = json.loads(compact)
    except json.JSONDecodeError:
        return False
    return bool(_skill_requests_from_value(value))


def validate_skill_request(request, snapshot=None):
    if not isinstance(request, dict):
        return SkillValidationResult(False, "Skill request was not an object.")
    if request.get("type") != "skill_request":
        return SkillValidationResult(False, "Skill request type was not skill_request.")
    name = request.get("skill")
    skill = ASSISTANT_SKILLS.get(name)
    if not skill:
        return SkillValidationResult(False, f"Unknown skill: {name or 'missing'}.")
    if not skill.enabled:
        return SkillValidationResult(False, f"Skill is disabled: {name}.")
    arguments = request.get("arguments", {})
    if not isinstance(arguments, dict):
        return SkillValidationResult(False, f"Arguments for {name} must be an object.")

    for field_name, expected in skill.input_schema.items():
        optional = str(expected).endswith("?")
        base_type = str(expected).rstrip("?")
        if field_name not in arguments:
            if optional:
                continue
            return SkillValidationResult(False, f"Missing required argument: {field_name}.")
        if not _value_matches_schema(arguments[field_name], base_type):
            return SkillValidationResult(False, f"Argument {field_name} must be {base_type}.")

    if name == "clean_scanned_cleanup" and not getattr(snapshot, "cleanup_categories", None):
        return SkillValidationResult(False, "Run a cleanup scan before cleaning.")

    return SkillValidationResult(True)


def _value_matches_schema(value, expected):
    if expected == "str":
        return isinstance(value, str)
    if expected == "int":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "float":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "bool":
        return isinstance(value, bool)
    if expected == "list[str]":
        return isinstance(value, list) and all(isinstance(item, str) for item in value)
    return True


def skill_request_to_action(request, snapshot=None):
    validation = validate_skill_request(request, snapshot)
    if not validation.success:
        return None, validation.message

    skill = ASSISTANT_SKILLS[request["skill"]]
    args = dict(request.get("arguments") or {})
    kind = skill.action_kind

    if kind == "clean_cleanup_candidates":
        keys = args.get("category_keys")
        if not keys and snapshot:
            keys = [cat.key for cat in snapshot.cleanup_categories]
        if not keys:
            return None, "No scanned cleanup categories are available."
        categories = [
            cat for cat in (snapshot.cleanup_categories if snapshot else [])
            if cat.key in set(keys)
        ]
        if not categories:
            return None, "No matching cleanup categories are available."
        total = sum(cat.size_bytes for cat in categories)
        return _action(
            kind,
            description=f"Delete scanned cleanup categories ({sysinfo.format_bytes(total)}).",
            payload={"category_keys": [cat.key for cat in categories]},
        ), ""

    if kind == "set_display_refresh_rate":
        display, message = _resolve_display(args, snapshot)
        if not display:
            return None, message
        hz = int(args["hz"])
        supported = display.get("supported_rates") or []
        if supported and hz not in [int(rate) for rate in supported]:
            return None, f"{hz} Hz is not listed as supported for {display.get('label', 'that display')}."
        return _action(
            kind,
            description=f"Change {display.get('label', display['name'])} to {hz} Hz.",
            payload={"device_name": display["name"], "hz": hz},
        ), ""

    if kind in {"audio_set_volume", "audio_mute_session", "audio_route_session"}:
        session, message = _resolve_audio_session(args, snapshot)
        if not session:
            return None, message
        payload = {"pid": session["pid"]}
        if kind == "audio_set_volume":
            level = max(0.0, min(1.0, float(args["level"])))
            payload["level"] = level
            description = f"Set {session['display_name']} volume to {int(level * 100)}%."
        elif kind == "audio_mute_session":
            muted = bool(args["muted"])
            payload["muted"] = muted
            description = f"{'Mute' if muted else 'Unmute'} {session['display_name']}."
        else:
            device, message = _resolve_audio_device(args, snapshot)
            if not device:
                return None, message
            payload.update({
                "process_name": session.get("process_name", ""),
                "device_id": device["id"],
            })
            description = f"Route {session['display_name']} to {device['name']}."
        return _action(kind, description=description, payload=payload), ""

    if kind == "load_saved_layout":
        layout, message = _resolve_layout(args, snapshot)
        if not layout:
            return None, message
        return _action(
            kind,
            description=f"Load saved layout \"{layout['name']}\".",
            payload={"layout_id": layout["id"]},
        ), ""

    if kind == "restart_network_adapter":
        adapter_name = str(args.get("adapter_name", "")).strip()
        if not adapter_name:
            return None, "No network adapter was selected."
        return _action(
            kind,
            description=f"Restart network adapter {adapter_name}.",
            payload={"adapter_name": adapter_name},
        ), ""

    if kind == "set_power_plan":
        plan_name = str(args.get("plan_name", "")).strip()
        allowed = {"balanced", "high_performance", "high performance", "power_saver", "power saver"}
        if plan_name.lower() not in allowed:
            return None, "Power plan must be balanced, high_performance, or power_saver."
        return _action(
            kind,
            description=f"Switch the active Windows power plan to {plan_name}.",
            payload={"plan_name": plan_name},
        ), ""

    if kind == "scan_event_log_errors":
        hours = int(args.get("hours", 24))
        hours = max(1, min(hours, 168))
        return _action(
            kind,
            description=f"Scan recent event log errors from the last {hours} hour(s).",
            payload={"hours": hours},
        ), ""

    if kind == "scan_large_files":
        payload = {}
        if args.get("root"):
            payload["root"] = str(args["root"])
        if args.get("min_size_mb"):
            payload["min_size_mb"] = int(args["min_size_mb"])
        return _action(kind, payload=payload), ""

    if kind == "create_restore_point":
        description = str(args.get("description") or "PC Fix restore point")
        return _action(
            kind,
            description=f"Create a Windows restore point named \"{description}\".",
            payload={"description": description},
        ), ""

    return _action(kind, payload={}), ""


def skill_requests_to_actions(text, snapshot=None):
    actions = []
    messages = []
    for request in extract_skill_requests(text):
        action, message = skill_request_to_action(request, snapshot)
        if action:
            actions.append(action)
        elif message:
            messages.append(message)
    return dedupe_actions(actions), messages


def dedupe_actions(actions):
    deduped = []
    seen = set()
    for action in actions:
        key = (action.kind, json.dumps(action.payload, sort_keys=True, default=str))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(action)
    return deduped


def merge_action_lists(*action_lists):
    merged = []
    for actions in action_lists:
        merged.extend(actions or [])
    return dedupe_actions(merged)


def _resolve_display(args, snapshot):
    displays = getattr(snapshot, "displays", []) if snapshot else []
    if not displays:
        return None, "Refresh display information before changing a refresh rate."
    if args.get("device_name"):
        matches = [display for display in displays if display.get("name") == args["device_name"]]
    elif args.get("display_label"):
        needle = str(args["display_label"]).lower()
        matches = [display for display in displays if needle in str(display.get("label", "")).lower()]
    else:
        matches = [display for display in displays if display.get("primary")] or displays
    return _single_match(matches, "display")


def _resolve_audio_session(args, snapshot):
    sessions = getattr(snapshot, "audio_sessions", []) if snapshot else []
    if not sessions:
        return None, "Refresh audio information before changing app audio."
    if args.get("pid"):
        matches = [session for session in sessions if int(session.get("pid", 0)) == int(args["pid"])]
    else:
        needle = str(args.get("process_name") or args.get("app") or "").lower()
        if not needle and len(sessions) == 1:
            matches = sessions
        else:
            matches = [
                session for session in sessions
                if needle
                and (
                    needle in str(session.get("process_name", "")).lower()
                    or needle in str(session.get("display_name", "")).lower()
                )
            ]
    return _single_match(matches, "audio session")


def _resolve_audio_device(args, snapshot):
    devices = getattr(snapshot, "audio_devices", []) if snapshot else []
    if not devices:
        return None, "Refresh audio information before routing app audio."
    if args.get("device_id"):
        matches = [device for device in devices if device.get("id") == args["device_id"]]
    else:
        needle = str(args.get("device_name") or "").lower()
        if not needle and len(devices) == 1:
            matches = devices
        else:
            matches = [device for device in devices if needle and needle in str(device.get("name", "")).lower()]
    return _single_match(matches, "audio device")


def _resolve_layout(args, snapshot):
    layouts = getattr(snapshot, "saved_layouts", []) if snapshot else []
    if not layouts:
        return None, "Refresh layouts before loading a saved layout."
    if args.get("layout_id"):
        matches = [layout for layout in layouts if layout.get("id") == args["layout_id"]]
    elif args.get("layout_name"):
        needle = str(args["layout_name"]).lower()
        matches = [layout for layout in layouts if needle in str(layout.get("name", "")).lower()]
    elif len(layouts) == 1:
        matches = layouts
    else:
        matches = []
    return _single_match(matches, "saved layout")


def _single_match(matches, label):
    if len(matches) == 1:
        return matches[0], ""
    if not matches:
        return None, f"No matching {label} was found."
    return None, f"More than one matching {label} was found; be more specific."


def execute_assistant_action(action, snapshot=None):
    kind = action.kind
    if kind in {
        "refresh_snapshot",
        "inspect_top_processes",
        "refresh_network",
        "refresh_hardware",
        "refresh_startup",
        "refresh_displays",
    }:
        refreshed = collect_assistant_snapshot(include_cleanup=False)
        messages = {
            "refresh_snapshot": "PC snapshot refreshed.",
            "inspect_top_processes": "Top CPU/RAM processes refreshed.",
            "refresh_network": "Network activity refreshed.",
            "refresh_hardware": "Hardware summary refreshed.",
            "refresh_startup": "Startup and installed-program summary refreshed.",
            "refresh_displays": "Display information refreshed.",
        }
        return AssistantActionResult(True, messages[kind]), refreshed

    if kind == "scan_cleanup":
        refreshed = collect_assistant_snapshot(include_cleanup=True)
        total = sum(cat.size_bytes for cat in refreshed.cleanup_categories)
        message = (
            f"Found {sysinfo.format_bytes(total)} across "
            f"{len(refreshed.cleanup_categories)} cleanup categor(ies)."
        )
        return AssistantActionResult(True, message), refreshed

    if kind == "clean_cleanup_candidates":
        if not snapshot:
            return AssistantActionResult(False, "No cleanup scan is available."), snapshot
        keys = set(action.payload.get("category_keys", []))
        categories = [cat for cat in snapshot.cleanup_categories if cat.key in keys]
        if not categories:
            return AssistantActionResult(False, "No matching cleanup categories are available."), snapshot
        bytes_freed, errors = sysinfo.delete_cleanup_items(categories)
        refreshed = collect_assistant_snapshot(include_cleanup=True)
        message = f"Freed {sysinfo.format_bytes(bytes_freed)}."
        return AssistantActionResult(not errors, message, errors), refreshed

    if kind == "set_display_refresh_rate":
        device_name = action.payload.get("device_name", "")
        hz = action.payload.get("hz")
        if not device_name or hz is None:
            return AssistantActionResult(False, "No display and refresh rate were selected."), snapshot
        result = sysinfo.set_display_refresh_rate(device_name, int(hz))
        refreshed = collect_assistant_snapshot(include_cleanup=False) if result.success else snapshot
        return AssistantActionResult(result.success, result.message), refreshed

    if kind in {"audio_set_volume", "audio_mute_session", "audio_route_session"}:
        result = _execute_audio_action(action)
        refreshed = collect_assistant_snapshot(include_cleanup=False) if result.success else snapshot
        return result, refreshed

    if kind == "load_saved_layout":
        result = _execute_layout_action(action, snapshot)
        refreshed = collect_assistant_snapshot(include_cleanup=False) if result.success else snapshot
        return result, refreshed

    toolbox_result = _execute_toolbox_action(action)
    if toolbox_result:
        tool_history.add_result(toolbox_result)
        refreshed = collect_assistant_snapshot(include_cleanup=False) if toolbox_result.success else snapshot
        message = toolbox_result.summary
        if toolbox_result.details:
            message += "\n" + "\n".join(f"- {detail}" for detail in toolbox_result.details[:8])
        return AssistantActionResult(toolbox_result.success, message, toolbox_result.errors), refreshed

    return AssistantActionResult(False, f"Unsupported action: {kind}"), snapshot


def _execute_toolbox_action(action):
    kind = action.kind
    payload = action.payload or {}
    if kind == "check_windows_updates":
        return toolbox.check_windows_updates()
    if kind == "check_disk_health":
        return toolbox.check_disk_health()
    if kind == "scan_event_log_errors":
        return toolbox.scan_event_log_errors(hours=payload.get("hours", 24))
    if kind == "check_network_health":
        return toolbox.check_network_health()
    if kind == "flush_dns_cache":
        return toolbox.flush_dns_cache()
    if kind == "restart_network_adapter":
        return toolbox.restart_network_adapter(payload.get("adapter_name", ""))
    if kind == "check_power_plan":
        return toolbox.check_power_plan()
    if kind == "set_power_plan":
        return toolbox.set_power_plan(payload.get("plan_name", ""))
    if kind == "review_startup_impact":
        return toolbox.review_startup_impact()
    if kind == "check_windows_security":
        return toolbox.check_windows_security()
    if kind == "scan_large_files":
        return toolbox.scan_large_files(
            root=payload.get("root"),
            min_size_mb=payload.get("min_size_mb", 500),
        )
    if kind == "create_restore_point":
        return toolbox.create_restore_point(payload.get("description", "PC Fix restore point"))
    if kind == "export_pc_report":
        return toolbox.export_pc_report()
    return None


def _execute_audio_action(action):
    from app import audio_control

    pid = int(action.payload.get("pid") or 0)
    if pid <= 0:
        return AssistantActionResult(False, "No audio session was selected.")

    if action.kind == "audio_set_volume":
        level = max(0.0, min(1.0, float(action.payload.get("level", 0))))
        if audio_control.set_session_volume(pid, level):
            return AssistantActionResult(True, f"Set app volume to {int(level * 100)}%.")
        return AssistantActionResult(False, "Could not update session volume.")

    if action.kind == "audio_mute_session":
        muted = bool(action.payload.get("muted"))
        if audio_control.set_session_mute(pid, muted):
            return AssistantActionResult(True, "Muted app audio." if muted else "Unmuted app audio.")
        return AssistantActionResult(False, "Could not update session mute.")

    if action.kind == "audio_route_session":
        device_id = action.payload.get("device_id", "")
        process_name = action.payload.get("process_name", "")
        route = audio_control.set_app_output_device(
            process_id=pid,
            process_name=process_name,
            device=device_id,
        )
        return AssistantActionResult(route.success, route.message)

    return AssistantActionResult(False, f"Unsupported audio action: {action.kind}")


def _execute_layout_action(action, snapshot):
    from app import window_layouts

    layout_id = action.payload.get("layout_id", "")
    layouts = window_layouts.load_layouts()
    layout = next((item for item in layouts if item.get("id") == layout_id), None)
    if not layout and snapshot:
        layout_name = action.payload.get("layout_name", "")
        layout = next((item for item in layouts if item.get("name") == layout_name), None)
    if not layout:
        return AssistantActionResult(False, "No saved layout was selected.")
    result = window_layouts.apply_layout(layout, launch_missing=True)
    parts = [f"Moved {result.moved} window(s)"]
    if result.launched:
        parts.append(f"launched {len(result.launched)} app(s)")
    if result.missing:
        parts.append(f"{len(result.missing)} window(s) missing")
    errors = list(result.errors)
    return AssistantActionResult(not errors, "Layout loaded: " + ", ".join(parts) + ".", errors)
