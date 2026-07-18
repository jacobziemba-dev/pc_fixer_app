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
    network_adapters: list = field(default_factory=list)
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
        keywords=("layout", "layouts", "window layout", "arrange", "desktop layout"),
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
    "scan_folder_sizes": AssistantTool(
        "scan_folder_sizes",
        "Scan folder sizes",
        "Break down folder sizes under common user locations without deleting anything.",
        payload_schema={"max_entries": "int?"},
        confirm_label="Scan",
        keywords=("folder size", "what's using space", "disk usage", "largest folders"),
    ),
    "scan_duplicate_files": AssistantTool(
        "scan_duplicate_files",
        "Scan duplicate files",
        "Find duplicate file groups by size and content hash. Report only; does not delete.",
        payload_schema={"min_size_mb": "int?", "limit_groups": "int?"},
        confirm_label="Scan",
        keywords=("duplicates", "duplicate files", "copy of", "same file"),
    ),
    "end_process": AssistantTool(
        "end_process",
        "End process",
        "End one non-protected process by PID after confirmation.",
        risk=MEDIUM_RISK,
        requires_confirmation=True,
        payload_schema={"pid": "int"},
        confirm_label="End Process",
        keywords=("end process", "kill process", "close process", "task manager"),
    ),
    "set_startup_item_enabled": AssistantTool(
        "set_startup_item_enabled",
        "Enable or disable startup item",
        "Enable or disable one allowlisted startup Run value or Startup-folder shortcut.",
        risk=MEDIUM_RISK,
        requires_confirmation=True,
        payload_schema={"name": "str", "source": "str", "enabled": "bool", "command": "str?"},
        confirm_label="Apply",
        keywords=("disable startup", "enable startup", "startup apps", "boot programs"),
    ),
    "renew_ip_address": AssistantTool(
        "renew_ip_address",
        "Renew IP address",
        "Release and renew the Windows IP address configuration.",
        risk=LOW_RISK,
        requires_confirmation=True,
        confirm_label="Renew IP",
        keywords=("renew ip", "release renew", "new ip", "ipconfig"),
    ),
    "reset_winsock": AssistantTool(
        "reset_winsock",
        "Reset Winsock",
        "Reset the Windows Winsock catalog. A reboot may be required afterward.",
        risk=MEDIUM_RISK,
        requires_confirmation=True,
        confirm_label="Reset Winsock",
        keywords=("winsock", "reset network stack", "tcp reset"),
    ),
    "check_pending_reboot": AssistantTool(
        "check_pending_reboot",
        "Check pending reboot",
        "Check whether Windows reports a pending reboot.",
        confirm_label="Check",
        keywords=("reboot pending", "restart required", "pending reboot"),
    ),
    "check_battery_report": AssistantTool(
        "check_battery_report",
        "Check battery report",
        "Read laptop battery charge and capacity signals when available.",
        confirm_label="Check",
        keywords=("battery", "battery health", "charge"),
    ),
    "restart_explorer": AssistantTool(
        "restart_explorer",
        "Restart Explorer",
        "Restart Windows Explorer to recover a frozen taskbar or desktop shell.",
        risk=LOW_RISK,
        requires_confirmation=True,
        confirm_label="Restart Explorer",
        keywords=("restart explorer", "frozen taskbar", "desktop frozen"),
    ),
    "open_windows_settings": AssistantTool(
        "open_windows_settings",
        "Open Windows Settings",
        "Open one allowlisted Windows Settings page.",
        risk=LOW_RISK,
        payload_schema={"page": "str"},
        confirm_label="Open",
        keywords=("open settings", "windows settings", "settings page"),
    ),
    "open_known_folder": AssistantTool(
        "open_known_folder",
        "Open known folder",
        "Open one allowlisted known folder such as Temp, Downloads, or Startup.",
        risk=LOW_RISK,
        payload_schema={"folder": "str"},
        confirm_label="Open",
        keywords=("open folder", "temp folder", "downloads folder", "startup folder"),
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
    "get_recycle_bin_size": AssistantTool(
        "get_recycle_bin_size",
        "Recycle Bin size",
        "Read how much space the Recycle Bin is using.",
        confirm_label="Check",
        keywords=("recycle", "recycle bin", "trash"),
    ),
    "empty_recycle_bin": AssistantTool(
        "empty_recycle_bin",
        "Empty Recycle Bin",
        "Empty the Windows Recycle Bin only.",
        risk=MEDIUM_RISK,
        requires_confirmation=True,
        confirm_label="Empty",
        keywords=("empty recycle", "empty trash", "clear recycle"),
    ),
    "clean_temp_files": AssistantTool(
        "clean_temp_files",
        "Clean temp files",
        "Delete scanned user/Windows temp cleanup categories only.",
        risk=MEDIUM_RISK,
        requires_confirmation=True,
        confirm_label="Clean Temp",
        keywords=("temp files", "clean temp", "temporary files"),
    ),
    "clean_browser_cache": AssistantTool(
        "clean_browser_cache",
        "Clean browser cache",
        "Delete scanned Chrome/Edge/Firefox cache categories only.",
        risk=MEDIUM_RISK,
        requires_confirmation=True,
        confirm_label="Clean Cache",
        keywords=("browser cache", "chrome cache", "edge cache", "firefox cache"),
    ),
    "clean_thumbnail_cache": AssistantTool(
        "clean_thumbnail_cache",
        "Clean thumbnail cache",
        "Delete the scanned thumbnail cache category only.",
        risk=LOW_RISK,
        requires_confirmation=True,
        confirm_label="Clean Thumbnails",
        keywords=("thumbnail", "thumbnails"),
    ),
    "scan_downloads_large_files": AssistantTool(
        "scan_downloads_large_files",
        "Scan Downloads for large files",
        "Find large files under the Downloads folder without deleting anything.",
        confirm_label="Scan Downloads",
        keywords=("downloads", "large downloads"),
    ),
    "scan_desktop_large_files": AssistantTool(
        "scan_desktop_large_files",
        "Scan Desktop for large files",
        "Find large files under the Desktop folder without deleting anything.",
        confirm_label="Scan Desktop",
        keywords=("desktop files", "large desktop"),
    ),
    "list_network_adapters": AssistantTool(
        "list_network_adapters",
        "List network adapters",
        "List adapter names and up/down status for targeting network repairs.",
        confirm_label="List",
        keywords=("adapters", "network adapters", "wifi adapter"),
    ),
    "check_dns_resolve": AssistantTool(
        "check_dns_resolve",
        "Check DNS resolve",
        "Resolve one allowlisted hostname to IP addresses.",
        payload_schema={"host": "str?"},
        confirm_label="Resolve",
        keywords=("dns", "resolve", "dns lookup"),
    ),
    "ping_host": AssistantTool(
        "ping_host",
        "Ping host",
        "Ping one allowlisted host with a small count cap.",
        payload_schema={"host": "str?", "count": "int?"},
        confirm_label="Ping",
        keywords=("ping",),
    ),
    "check_default_gateway": AssistantTool(
        "check_default_gateway",
        "Check default gateway",
        "Read default gateway / route summary for no-internet triage.",
        confirm_label="Check Gateway",
        keywords=("gateway", "default gateway", "route"),
    ),
    "show_wifi_status": AssistantTool(
        "show_wifi_status",
        "Show Wi-Fi status",
        "Read connected SSID/signal/state when available. Never reads passwords.",
        confirm_label="Wi-Fi Status",
        keywords=("wifi status", "ssid", "wireless"),
    ),
    "check_system_uptime": AssistantTool(
        "check_system_uptime",
        "Check system uptime",
        "Read boot time and uptime for slow-PC advice.",
        confirm_label="Uptime",
        keywords=("uptime", "boot time", "how long"),
    ),
    "check_memory_pressure": AssistantTool(
        "check_memory_pressure",
        "Check memory pressure",
        "Read RAM and pagefile/swap pressure signals.",
        confirm_label="Memory",
        keywords=("memory pressure", "pagefile", "swap", "ram pressure"),
    ),
    "list_installed_gpus": AssistantTool(
        "list_installed_gpus",
        "List GPUs",
        "List installed GPU names from the hardware summary.",
        confirm_label="List GPUs",
        keywords=("gpu", "graphics", "video card"),
    ),
    "check_smart_status": AssistantTool(
        "check_smart_status",
        "Check disk SMART/health",
        "Read physical disk health status (same conservative disk health path).",
        confirm_label="Disk Health",
        keywords=("smart", "disk health", "drive health"),
    ),
    "open_task_manager": AssistantTool(
        "open_task_manager",
        "Open Task Manager",
        "Launch Windows Task Manager.",
        risk=LOW_RISK,
        confirm_label="Open",
        keywords=("task manager",),
    ),
    "open_resource_monitor": AssistantTool(
        "open_resource_monitor",
        "Open Resource Monitor",
        "Launch Windows Resource Monitor.",
        risk=LOW_RISK,
        confirm_label="Open",
        keywords=("resource monitor",),
    ),
    "open_device_manager": AssistantTool(
        "open_device_manager",
        "Open Device Manager",
        "Launch Windows Device Manager.",
        risk=LOW_RISK,
        confirm_label="Open",
        keywords=("device manager",),
    ),
    "capture_layout_snapshot": AssistantTool(
        "capture_layout_snapshot",
        "Capture window layout",
        "Save the current window layout for later restore.",
        risk=LOW_RISK,
        requires_confirmation=True,
        payload_schema={"name": "str?"},
        confirm_label="Capture",
        keywords=("save layout", "capture layout", "snapshot layout"),
    ),
    "set_default_audio_device": AssistantTool(
        "set_default_audio_device",
        "Set default audio device",
        "Set the default playback device after Python resolves the device target.",
        risk=LOW_RISK,
        requires_confirmation=True,
        payload_schema={"device_id": "str"},
        confirm_label="Set Default",
        keywords=("default speaker", "default audio", "default sound"),
    ),
    "clear_app_audio_route": AssistantTool(
        "clear_app_audio_route",
        "Clear app audio route",
        "Restore one app audio session to the system default playback device.",
        risk=LOW_RISK,
        requires_confirmation=True,
        payload_schema={"pid": "int", "process_name": "str?"},
        confirm_label="Clear Route",
        keywords=("clear audio route", "system default audio", "reset app audio"),
    ),
    "delete_saved_layout": AssistantTool(
        "delete_saved_layout",
        "Delete saved layout",
        "Delete one saved window layout after Python resolves the layout target.",
        risk=MEDIUM_RISK,
        requires_confirmation=True,
        payload_schema={"layout_id": "str"},
        confirm_label="Delete",
        keywords=("delete layout", "remove layout"),
    ),
    "list_saved_layouts": AssistantTool(
        "list_saved_layouts",
        "List saved layouts",
        "List saved window layout names and ids.",
        keywords=("saved layouts", "list layouts"),
    ),
    "check_disk_free_space": AssistantTool(
        "check_disk_free_space",
        "Check disk free space",
        "Report free and used space for mounted volumes.",
        keywords=("free space", "disk space", "storage space"),
    ),
    "list_printers": AssistantTool(
        "list_printers",
        "List printers",
        "List installed printers and default/online status where available.",
        keywords=("printers", "printer"),
    ),
    "list_usb_devices": AssistantTool(
        "list_usb_devices",
        "List USB devices",
        "List present USB devices and their status.",
        keywords=("usb", "usb devices"),
    ),
    "list_running_services": AssistantTool(
        "list_running_services",
        "List running services",
        "List a capped set of currently running Windows services.",
        keywords=("services", "running services"),
    ),
    "list_third_party_services": AssistantTool(
        "list_third_party_services",
        "List third-party services",
        "List running services whose binaries are outside Windows system folders.",
        keywords=("third party services", "non microsoft services"),
    ),
    "check_service_status": AssistantTool(
        "check_service_status",
        "Check service status",
        "Read status for one allowlisted Windows service key.",
        payload_schema={"service": "str"},
        keywords=("service status", "spooler status"),
    ),
    "list_problem_devices": AssistantTool(
        "list_problem_devices",
        "List problem devices",
        "List Plug and Play devices that are not reporting OK status.",
        keywords=("problem devices", "device errors", "yellow bang"),
    ),
    "check_listening_ports": AssistantTool(
        "check_listening_ports",
        "Check listening ports",
        "List top listening TCP/UDP endpoints and owning processes (report only).",
        keywords=("listening ports", "open ports", "ports"),
    ),
    "check_bluetooth_status": AssistantTool(
        "check_bluetooth_status",
        "Check Bluetooth status",
        "Read Bluetooth radio and service status when Windows exposes it.",
        keywords=("bluetooth", "bt status"),
    ),
    "check_unexpected_shutdowns": AssistantTool(
        "check_unexpected_shutdowns",
        "Check unexpected shutdowns",
        "Summarize recent unexpected or dirty shutdown events.",
        payload_schema={"hours": "int?"},
        keywords=("unexpected shutdown", "crash reboot", "dirty shutdown"),
    ),
    "check_component_store_health": AssistantTool(
        "check_component_store_health",
        "Check component store health",
        "Run DISM CheckHealth only (read-only; does not restore the image).",
        keywords=("dism", "component store", "checkhealth"),
    ),
    "scan_volume_errors": AssistantTool(
        "scan_volume_errors",
        "Scan volume errors",
        "Run an online read-only chkdsk /scan on an allowlisted volume.",
        payload_schema={"volume": "str?"},
        keywords=("chkdsk", "disk errors", "volume scan"),
    ),
    "restart_print_spooler": AssistantTool(
        "restart_print_spooler",
        "Restart print spooler",
        "Restart only the Windows Print Spooler service.",
        risk=MEDIUM_RISK,
        requires_confirmation=True,
        confirm_label="Restart Spooler",
        keywords=("print spooler", "printer spooler", "restart spooler"),
    ),
    "start_sfc_scan": AssistantTool(
        "start_sfc_scan",
        "Start SFC scan",
        "Run sfc /scannow. Needs elevation and can take several minutes.",
        risk=MEDIUM_RISK,
        requires_confirmation=True,
        confirm_label="Run SFC",
        keywords=("sfc", "system file checker", "scannow"),
    ),
    "open_services_manager": AssistantTool(
        "open_services_manager",
        "Open Services",
        "Launch the Windows Services manager.",
        risk=LOW_RISK,
        confirm_label="Open",
        keywords=("services.msc", "open services"),
    ),
    "open_disk_cleanup": AssistantTool(
        "open_disk_cleanup",
        "Open Disk Cleanup",
        "Launch the Windows Disk Cleanup UI without deleting anything automatically.",
        risk=LOW_RISK,
        confirm_label="Open",
        keywords=("disk cleanup", "cleanmgr"),
    ),
    "open_windows_troubleshooter": AssistantTool(
        "open_windows_troubleshooter",
        "Open Windows troubleshooter",
        "Open one allowlisted built-in Windows troubleshooter.",
        risk=LOW_RISK,
        payload_schema={"troubleshooter": "str"},
        confirm_label="Open",
        keywords=("troubleshooter", "troubleshoot"),
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
        "Restart one named network adapter after Python resolves the adapter target.",
        {"adapter_name": "str?"},
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
    "scan_folder_sizes": AssistantSkill(
        "scan_folder_sizes",
        "Break down folder sizes under common user locations.",
        {"max_entries": "int?"},
        ASSISTANT_TOOLS["scan_folder_sizes"].risk,
        ASSISTANT_TOOLS["scan_folder_sizes"].requires_confirmation,
        "scan_folder_sizes",
    ),
    "scan_duplicate_files": AssistantSkill(
        "scan_duplicate_files",
        "Find duplicate file groups without deleting anything.",
        {"min_size_mb": "int?", "limit_groups": "int?"},
        ASSISTANT_TOOLS["scan_duplicate_files"].risk,
        ASSISTANT_TOOLS["scan_duplicate_files"].requires_confirmation,
        "scan_duplicate_files",
    ),
    "end_process": AssistantSkill(
        "end_process",
        "End one non-protected process by PID or friendly process name from the snapshot.",
        {"pid": "int?", "process_name": "str?", "app": "str?"},
        ASSISTANT_TOOLS["end_process"].risk,
        ASSISTANT_TOOLS["end_process"].requires_confirmation,
        "end_process",
    ),
    "set_startup_item_enabled": AssistantSkill(
        "set_startup_item_enabled",
        "Enable or disable one allowlisted startup item after Python resolves it from the snapshot.",
        {"name": "str?", "source": "str?", "enabled": "bool", "command": "str?"},
        ASSISTANT_TOOLS["set_startup_item_enabled"].risk,
        ASSISTANT_TOOLS["set_startup_item_enabled"].requires_confirmation,
        "set_startup_item_enabled",
    ),
    "renew_ip_address": AssistantSkill(
        "renew_ip_address",
        "Release and renew the Windows IP address.",
        {},
        ASSISTANT_TOOLS["renew_ip_address"].risk,
        ASSISTANT_TOOLS["renew_ip_address"].requires_confirmation,
        "renew_ip_address",
    ),
    "reset_winsock": AssistantSkill(
        "reset_winsock",
        "Reset the Windows Winsock catalog.",
        {},
        ASSISTANT_TOOLS["reset_winsock"].risk,
        ASSISTANT_TOOLS["reset_winsock"].requires_confirmation,
        "reset_winsock",
    ),
    "check_pending_reboot": AssistantSkill(
        "check_pending_reboot",
        "Check whether Windows reports a pending reboot.",
        {},
        ASSISTANT_TOOLS["check_pending_reboot"].risk,
        ASSISTANT_TOOLS["check_pending_reboot"].requires_confirmation,
        "check_pending_reboot",
    ),
    "check_battery_report": AssistantSkill(
        "check_battery_report",
        "Read laptop battery status when available.",
        {},
        ASSISTANT_TOOLS["check_battery_report"].risk,
        ASSISTANT_TOOLS["check_battery_report"].requires_confirmation,
        "check_battery_report",
    ),
    "restart_explorer": AssistantSkill(
        "restart_explorer",
        "Restart Windows Explorer.",
        {},
        ASSISTANT_TOOLS["restart_explorer"].risk,
        ASSISTANT_TOOLS["restart_explorer"].requires_confirmation,
        "restart_explorer",
    ),
    "open_windows_settings": AssistantSkill(
        "open_windows_settings",
        "Open one allowlisted Windows Settings page.",
        {"page": "str"},
        ASSISTANT_TOOLS["open_windows_settings"].risk,
        ASSISTANT_TOOLS["open_windows_settings"].requires_confirmation,
        "open_windows_settings",
    ),
    "open_known_folder": AssistantSkill(
        "open_known_folder",
        "Open one allowlisted known folder.",
        {"folder": "str"},
        ASSISTANT_TOOLS["open_known_folder"].risk,
        ASSISTANT_TOOLS["open_known_folder"].requires_confirmation,
        "open_known_folder",
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
    "get_recycle_bin_size": AssistantSkill(
        "get_recycle_bin_size",
        "Read Recycle Bin size without deleting anything.",
        {},
        ASSISTANT_TOOLS["get_recycle_bin_size"].risk,
        ASSISTANT_TOOLS["get_recycle_bin_size"].requires_confirmation,
        "get_recycle_bin_size",
    ),
    "empty_recycle_bin": AssistantSkill(
        "empty_recycle_bin",
        "Empty the Windows Recycle Bin only.",
        {},
        ASSISTANT_TOOLS["empty_recycle_bin"].risk,
        ASSISTANT_TOOLS["empty_recycle_bin"].requires_confirmation,
        "empty_recycle_bin",
    ),
    "clean_temp_files": AssistantSkill(
        "clean_temp_files",
        "Clean scanned temp cleanup categories only.",
        {},
        ASSISTANT_TOOLS["clean_temp_files"].risk,
        ASSISTANT_TOOLS["clean_temp_files"].requires_confirmation,
        "clean_temp_files",
    ),
    "clean_browser_cache": AssistantSkill(
        "clean_browser_cache",
        "Clean scanned browser-cache cleanup categories only.",
        {},
        ASSISTANT_TOOLS["clean_browser_cache"].risk,
        ASSISTANT_TOOLS["clean_browser_cache"].requires_confirmation,
        "clean_browser_cache",
    ),
    "clean_thumbnail_cache": AssistantSkill(
        "clean_thumbnail_cache",
        "Clean the scanned thumbnail cache category only.",
        {},
        ASSISTANT_TOOLS["clean_thumbnail_cache"].risk,
        ASSISTANT_TOOLS["clean_thumbnail_cache"].requires_confirmation,
        "clean_thumbnail_cache",
    ),
    "scan_downloads_large_files": AssistantSkill(
        "scan_downloads_large_files",
        "Find large files under Downloads without deleting anything.",
        {"min_size_mb": "int?"},
        ASSISTANT_TOOLS["scan_downloads_large_files"].risk,
        ASSISTANT_TOOLS["scan_downloads_large_files"].requires_confirmation,
        "scan_downloads_large_files",
    ),
    "scan_desktop_large_files": AssistantSkill(
        "scan_desktop_large_files",
        "Find large files under Desktop without deleting anything.",
        {"min_size_mb": "int?"},
        ASSISTANT_TOOLS["scan_desktop_large_files"].risk,
        ASSISTANT_TOOLS["scan_desktop_large_files"].requires_confirmation,
        "scan_desktop_large_files",
    ),
    "list_network_adapters": AssistantSkill(
        "list_network_adapters",
        "List network adapter names and status.",
        {},
        ASSISTANT_TOOLS["list_network_adapters"].risk,
        ASSISTANT_TOOLS["list_network_adapters"].requires_confirmation,
        "list_network_adapters",
    ),
    "check_dns_resolve": AssistantSkill(
        "check_dns_resolve",
        "Resolve an allowlisted hostname.",
        {"host": "str?"},
        ASSISTANT_TOOLS["check_dns_resolve"].risk,
        ASSISTANT_TOOLS["check_dns_resolve"].requires_confirmation,
        "check_dns_resolve",
    ),
    "ping_host": AssistantSkill(
        "ping_host",
        "Ping an allowlisted host.",
        {"host": "str?", "count": "int?"},
        ASSISTANT_TOOLS["ping_host"].risk,
        ASSISTANT_TOOLS["ping_host"].requires_confirmation,
        "ping_host",
    ),
    "check_default_gateway": AssistantSkill(
        "check_default_gateway",
        "Read default gateway details.",
        {},
        ASSISTANT_TOOLS["check_default_gateway"].risk,
        ASSISTANT_TOOLS["check_default_gateway"].requires_confirmation,
        "check_default_gateway",
    ),
    "show_wifi_status": AssistantSkill(
        "show_wifi_status",
        "Read Wi-Fi SSID/signal/state when available.",
        {},
        ASSISTANT_TOOLS["show_wifi_status"].risk,
        ASSISTANT_TOOLS["show_wifi_status"].requires_confirmation,
        "show_wifi_status",
    ),
    "check_system_uptime": AssistantSkill(
        "check_system_uptime",
        "Read boot time and uptime.",
        {},
        ASSISTANT_TOOLS["check_system_uptime"].risk,
        ASSISTANT_TOOLS["check_system_uptime"].requires_confirmation,
        "check_system_uptime",
    ),
    "check_memory_pressure": AssistantSkill(
        "check_memory_pressure",
        "Read RAM and pagefile pressure.",
        {},
        ASSISTANT_TOOLS["check_memory_pressure"].risk,
        ASSISTANT_TOOLS["check_memory_pressure"].requires_confirmation,
        "check_memory_pressure",
    ),
    "list_installed_gpus": AssistantSkill(
        "list_installed_gpus",
        "List installed GPU names.",
        {},
        ASSISTANT_TOOLS["list_installed_gpus"].risk,
        ASSISTANT_TOOLS["list_installed_gpus"].requires_confirmation,
        "list_installed_gpus",
    ),
    "check_smart_status": AssistantSkill(
        "check_smart_status",
        "Read physical disk health status.",
        {},
        ASSISTANT_TOOLS["check_smart_status"].risk,
        ASSISTANT_TOOLS["check_smart_status"].requires_confirmation,
        "check_disk_health",
    ),
    "open_task_manager": AssistantSkill(
        "open_task_manager",
        "Open Windows Task Manager.",
        {},
        ASSISTANT_TOOLS["open_task_manager"].risk,
        ASSISTANT_TOOLS["open_task_manager"].requires_confirmation,
        "open_task_manager",
    ),
    "open_resource_monitor": AssistantSkill(
        "open_resource_monitor",
        "Open Windows Resource Monitor.",
        {},
        ASSISTANT_TOOLS["open_resource_monitor"].risk,
        ASSISTANT_TOOLS["open_resource_monitor"].requires_confirmation,
        "open_resource_monitor",
    ),
    "open_device_manager": AssistantSkill(
        "open_device_manager",
        "Open Windows Device Manager.",
        {},
        ASSISTANT_TOOLS["open_device_manager"].risk,
        ASSISTANT_TOOLS["open_device_manager"].requires_confirmation,
        "open_device_manager",
    ),
    "capture_layout_snapshot": AssistantSkill(
        "capture_layout_snapshot",
        "Save the current window layout.",
        {"name": "str?"},
        ASSISTANT_TOOLS["capture_layout_snapshot"].risk,
        ASSISTANT_TOOLS["capture_layout_snapshot"].requires_confirmation,
        "capture_layout_snapshot",
    ),
    "set_default_audio_device": AssistantSkill(
        "set_default_audio_device",
        "Set the default playback device after Python resolves the device.",
        {"device_id": "str?", "device_name": "str?"},
        ASSISTANT_TOOLS["set_default_audio_device"].risk,
        ASSISTANT_TOOLS["set_default_audio_device"].requires_confirmation,
        "set_default_audio_device",
    ),
    "clear_app_audio_route": AssistantSkill(
        "clear_app_audio_route",
        "Restore one app audio session to the system default device.",
        {"pid": "int?", "process_name": "str?", "app": "str?"},
        ASSISTANT_TOOLS["clear_app_audio_route"].risk,
        ASSISTANT_TOOLS["clear_app_audio_route"].requires_confirmation,
        "clear_app_audio_route",
    ),
    "delete_saved_layout": AssistantSkill(
        "delete_saved_layout",
        "Delete one saved window layout after Python resolves the layout target.",
        {"layout_id": "str?", "layout_name": "str?"},
        ASSISTANT_TOOLS["delete_saved_layout"].risk,
        ASSISTANT_TOOLS["delete_saved_layout"].requires_confirmation,
        "delete_saved_layout",
    ),
    "list_saved_layouts": AssistantSkill(
        "list_saved_layouts",
        "List saved window layout names and ids.",
        {},
        ASSISTANT_TOOLS["list_saved_layouts"].risk,
        ASSISTANT_TOOLS["list_saved_layouts"].requires_confirmation,
        "list_saved_layouts",
    ),
    "check_disk_free_space": AssistantSkill(
        "check_disk_free_space",
        "Report free and used space for mounted volumes.",
        {},
        ASSISTANT_TOOLS["check_disk_free_space"].risk,
        ASSISTANT_TOOLS["check_disk_free_space"].requires_confirmation,
        "check_disk_free_space",
    ),
    "list_printers": AssistantSkill(
        "list_printers",
        "List installed printers and status.",
        {},
        ASSISTANT_TOOLS["list_printers"].risk,
        ASSISTANT_TOOLS["list_printers"].requires_confirmation,
        "list_printers",
    ),
    "list_usb_devices": AssistantSkill(
        "list_usb_devices",
        "List present USB devices.",
        {},
        ASSISTANT_TOOLS["list_usb_devices"].risk,
        ASSISTANT_TOOLS["list_usb_devices"].requires_confirmation,
        "list_usb_devices",
    ),
    "list_running_services": AssistantSkill(
        "list_running_services",
        "List currently running Windows services (capped).",
        {},
        ASSISTANT_TOOLS["list_running_services"].risk,
        ASSISTANT_TOOLS["list_running_services"].requires_confirmation,
        "list_running_services",
    ),
    "list_third_party_services": AssistantSkill(
        "list_third_party_services",
        "List running third-party services outside Windows system folders.",
        {},
        ASSISTANT_TOOLS["list_third_party_services"].risk,
        ASSISTANT_TOOLS["list_third_party_services"].requires_confirmation,
        "list_third_party_services",
    ),
    "check_service_status": AssistantSkill(
        "check_service_status",
        "Check status of one allowlisted Windows service key.",
        {"service": "str"},
        ASSISTANT_TOOLS["check_service_status"].risk,
        ASSISTANT_TOOLS["check_service_status"].requires_confirmation,
        "check_service_status",
    ),
    "list_problem_devices": AssistantSkill(
        "list_problem_devices",
        "List devices that are not reporting OK status.",
        {},
        ASSISTANT_TOOLS["list_problem_devices"].risk,
        ASSISTANT_TOOLS["list_problem_devices"].requires_confirmation,
        "list_problem_devices",
    ),
    "check_listening_ports": AssistantSkill(
        "check_listening_ports",
        "List listening ports and owning processes (report only).",
        {},
        ASSISTANT_TOOLS["check_listening_ports"].risk,
        ASSISTANT_TOOLS["check_listening_ports"].requires_confirmation,
        "check_listening_ports",
    ),
    "check_bluetooth_status": AssistantSkill(
        "check_bluetooth_status",
        "Read Bluetooth adapter and service status.",
        {},
        ASSISTANT_TOOLS["check_bluetooth_status"].risk,
        ASSISTANT_TOOLS["check_bluetooth_status"].requires_confirmation,
        "check_bluetooth_status",
    ),
    "check_unexpected_shutdowns": AssistantSkill(
        "check_unexpected_shutdowns",
        "Summarize recent unexpected shutdown events.",
        {"hours": "int?"},
        ASSISTANT_TOOLS["check_unexpected_shutdowns"].risk,
        ASSISTANT_TOOLS["check_unexpected_shutdowns"].requires_confirmation,
        "check_unexpected_shutdowns",
    ),
    "check_component_store_health": AssistantSkill(
        "check_component_store_health",
        "Run DISM CheckHealth only (does not restore the image).",
        {},
        ASSISTANT_TOOLS["check_component_store_health"].risk,
        ASSISTANT_TOOLS["check_component_store_health"].requires_confirmation,
        "check_component_store_health",
    ),
    "scan_volume_errors": AssistantSkill(
        "scan_volume_errors",
        "Run read-only chkdsk /scan on an allowlisted volume.",
        {"volume": "str?"},
        ASSISTANT_TOOLS["scan_volume_errors"].risk,
        ASSISTANT_TOOLS["scan_volume_errors"].requires_confirmation,
        "scan_volume_errors",
    ),
    "restart_print_spooler": AssistantSkill(
        "restart_print_spooler",
        "Restart the Windows Print Spooler service.",
        {},
        ASSISTANT_TOOLS["restart_print_spooler"].risk,
        ASSISTANT_TOOLS["restart_print_spooler"].requires_confirmation,
        "restart_print_spooler",
    ),
    "start_sfc_scan": AssistantSkill(
        "start_sfc_scan",
        "Run sfc /scannow (needs elevation; may take several minutes).",
        {},
        ASSISTANT_TOOLS["start_sfc_scan"].risk,
        ASSISTANT_TOOLS["start_sfc_scan"].requires_confirmation,
        "start_sfc_scan",
    ),
    "open_services_manager": AssistantSkill(
        "open_services_manager",
        "Open the Windows Services manager.",
        {},
        ASSISTANT_TOOLS["open_services_manager"].risk,
        ASSISTANT_TOOLS["open_services_manager"].requires_confirmation,
        "open_services_manager",
    ),
    "open_disk_cleanup": AssistantSkill(
        "open_disk_cleanup",
        "Open the Windows Disk Cleanup UI.",
        {},
        ASSISTANT_TOOLS["open_disk_cleanup"].risk,
        ASSISTANT_TOOLS["open_disk_cleanup"].requires_confirmation,
        "open_disk_cleanup",
    ),
    "open_windows_troubleshooter": AssistantSkill(
        "open_windows_troubleshooter",
        "Open one allowlisted Windows troubleshooter.",
        {"troubleshooter": "str"},
        ASSISTANT_TOOLS["open_windows_troubleshooter"].risk,
        ASSISTANT_TOOLS["open_windows_troubleshooter"].requires_confirmation,
        "open_windows_troubleshooter",
    ),
}

TAB_ACTION_KINDS = {
    kind
    for kind, tool in ASSISTANT_TOOLS.items()
    if tool.handler == "tab"
}

# Always included in the prompt catalog (keeps common triage skills available).
CORE_SKILL_NAMES = frozenset({
    "diagnose_pc_health",
    "inspect_top_processes",
    "scan_cleanup",
    "clean_scanned_cleanup",
    "export_pc_report",
    "check_pending_reboot",
    "open_windows_settings",
    "open_known_folder",
})

SKILL_DOMAIN_KEYWORDS = {
    "network": (
        "network", "internet", "wifi", "wi-fi", "ethernet", "dns", "adapter",
        "ip", "winsock", "ping", "gateway", "offline", "connection",
        "ports", "listening", "proxy", "signal", "latency",
    ),
    "display": ("display", "monitor", "refresh rate", "screen", "hz", "resolution"),
    "audio": (
        "audio", "sound", "speaker", "volume", "mute", "muted", "unmute",
        "route", "headphones", "headset",
    ),
    "layouts": ("layout", "layouts", "arrange", "snap window", "window layout", "desktop layout"),
    "startup": ("startup", "boot", "booting", "launch on start", "startup apps", "startup programs"),
    "storage": (
        "storage", "disk", "drive", "large file", "large files", "duplicate",
        "folder size", "downloads", "desktop files", "space", "chkdsk", "free space",
        "ssd", "hdd", "smart status",
    ),
    "cleanup": (
        "clean", "cleaning", "cleanup", "junk", "temp", "cache", "recycle",
        "free space", "free up", "disk cleanup",
    ),
    "power": ("power", "battery", "power plan", "performance plan", "power saver"),
    "security": (
        "security", "defender", "firewall", "update", "updates", "event log", "error",
        "sfc", "dism", "shutdown", "unexpected", "virus", "malware", "antivirus",
    ),
    "hardware": (
        "hardware", "gpu", "cpu", "bios", "motherboard", "specs", "uptime",
        "memory", "memory pressure", "ram", "usb", "bluetooth",
    ),
    "process": (
        "process", "processes", "task manager", "end process", "kill",
        "cpu hog", "frozen", "not responding", "hung",
    ),
    "system": (
        "settings", "task manager", "resource monitor", "device manager",
        "explorer", "restore point", "open folder", "printer", "spooler",
        "services", "troubleshoot", "troubleshooter",
    ),
}

SKILL_DOMAINS = {
    "diagnose_pc_health": ("hardware", "process"),
    "inspect_top_processes": ("process",),
    "refresh_network": ("network",),
    "refresh_hardware": ("hardware",),
    "refresh_startup_programs": ("startup",),
    "scan_cleanup": ("cleanup", "storage"),
    "clean_scanned_cleanup": ("cleanup",),
    "refresh_displays": ("display",),
    "set_display_refresh_rate": ("display",),
    "refresh_audio": ("audio",),
    "set_app_volume": ("audio",),
    "mute_app_audio": ("audio",),
    "route_app_audio": ("audio",),
    "refresh_layouts": ("layouts",),
    "load_saved_layout": ("layouts",),
    "check_windows_updates": ("security",),
    "check_disk_health": ("storage", "hardware"),
    "scan_event_log_errors": ("security",),
    "check_network_health": ("network",),
    "flush_dns_cache": ("network",),
    "restart_network_adapter": ("network",),
    "check_power_plan": ("power",),
    "set_power_plan": ("power",),
    "review_startup_impact": ("startup",),
    "check_windows_security": ("security",),
    "scan_large_files": ("storage",),
    "scan_folder_sizes": ("storage",),
    "scan_duplicate_files": ("storage",),
    "end_process": ("process",),
    "set_startup_item_enabled": ("startup",),
    "renew_ip_address": ("network",),
    "reset_winsock": ("network",),
    "check_pending_reboot": ("security", "system"),
    "check_battery_report": ("power",),
    "restart_explorer": ("system",),
    "open_windows_settings": ("system",),
    "open_known_folder": ("system", "cleanup"),
    "create_restore_point": ("system", "security"),
    "export_pc_report": ("system",),
    "get_recycle_bin_size": ("cleanup", "storage"),
    "empty_recycle_bin": ("cleanup",),
    "clean_temp_files": ("cleanup",),
    "clean_browser_cache": ("cleanup",),
    "clean_thumbnail_cache": ("cleanup",),
    "scan_downloads_large_files": ("storage", "cleanup"),
    "scan_desktop_large_files": ("storage", "cleanup"),
    "list_network_adapters": ("network",),
    "check_dns_resolve": ("network",),
    "ping_host": ("network",),
    "check_default_gateway": ("network",),
    "show_wifi_status": ("network",),
    "check_system_uptime": ("hardware", "system"),
    "check_memory_pressure": ("hardware", "process"),
    "list_installed_gpus": ("hardware", "display"),
    "check_smart_status": ("storage", "hardware"),
    "open_task_manager": ("system", "process"),
    "open_resource_monitor": ("system", "process"),
    "open_device_manager": ("system", "hardware"),
    "capture_layout_snapshot": ("layouts",),
    "set_default_audio_device": ("audio",),
    "clear_app_audio_route": ("audio",),
    "delete_saved_layout": ("layouts",),
    "list_saved_layouts": ("layouts",),
    "check_disk_free_space": ("storage",),
    "list_printers": ("system",),
    "list_usb_devices": ("hardware",),
    "list_running_services": ("system",),
    "list_third_party_services": ("system",),
    "check_service_status": ("system",),
    "list_problem_devices": ("hardware",),
    "check_listening_ports": ("network",),
    "check_bluetooth_status": ("hardware",),
    "check_unexpected_shutdowns": ("system", "security"),
    "check_component_store_health": ("system", "security"),
    "scan_volume_errors": ("storage",),
    "restart_print_spooler": ("system",),
    "start_sfc_scan": ("system", "security"),
    "open_services_manager": ("system",),
    "open_disk_cleanup": ("system", "cleanup"),
    "open_windows_troubleshooter": ("system",),
}

FULL_CATALOG_PROMPTS = (
    "what can you do",
    "what skills",
    "list skills",
    "available skills",
    "help me with everything",
    "show all skills",
    "what are you able",
)


_KEYWORD_PATTERNS = {}


def _keyword_pattern(keyword):
    """Word-boundary pattern with optional plural, so "ip" stops matching "tips"."""
    pattern = _KEYWORD_PATTERNS.get(keyword)
    if pattern is None:
        if keyword == "hz":
            # "hz" usually rides on a number ("144hz") with no word boundary.
            pattern = re.compile(r"\bhz\b|\dhz\b")
        else:
            pattern = re.compile(rf"\b{re.escape(keyword)}(?:es|s)?\b")
        _KEYWORD_PATTERNS[keyword] = pattern
    return pattern


def detect_skill_domains(user_text):
    lowered = (user_text or "").lower()
    if not lowered.strip():
        return set()
    if any(phrase in lowered for phrase in FULL_CATALOG_PROMPTS):
        return {"*"}
    domains = set()
    for domain, keywords in SKILL_DOMAIN_KEYWORDS.items():
        if any(_keyword_pattern(keyword).search(lowered) for keyword in keywords):
            domains.add(domain)
    return domains


def select_skill_names_for_prompt(user_text=None):
    # No user text: full catalog (docs/tests). Intent filtering applies once Chat passes the question.
    if user_text is None or not str(user_text).strip():
        return [name for name, skill in ASSISTANT_SKILLS.items() if skill.enabled]
    domains = detect_skill_domains(user_text)
    if "*" in domains:
        return [name for name, skill in ASSISTANT_SKILLS.items() if skill.enabled]
    selected = set(CORE_SKILL_NAMES)
    for name, skill_domains in SKILL_DOMAINS.items():
        if name not in ASSISTANT_SKILLS:
            continue
        if domains.intersection(skill_domains):
            selected.add(name)
    return [name for name in ASSISTANT_SKILLS if name in selected and ASSISTANT_SKILLS[name].enabled]


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


def render_skill_catalog(user_text=None, skill_names=None):
    if skill_names is None:
        skill_names = select_skill_names_for_prompt(user_text)
    lines = [
        "Available assistant skills:",
        "When useful, include one fenced JSON skill request exactly like:",
        '```json\n{"type":"skill_request","skill":"scan_cleanup","arguments":{}}\n```',
        "Never invent skills. Never request shell commands, arbitrary code, registry edits, or arbitrary file deletion.",
    ]
    for name in skill_names:
        skill = ASSISTANT_SKILLS.get(name)
        if not skill or not skill.enabled:
            continue
        args = ", ".join(f"{arg_name}: {kind}" for arg_name, kind in skill.input_schema.items()) or "none"
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
        snapshot.network_adapters = toolbox.list_network_adapter_names()
    except Exception:
        snapshot.network_adapters = []

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

    if getattr(snapshot, "network_adapters", None):
        adapter_bits = [
            f"{item.get('name')}({'up' if item.get('is_up') else 'down'})"
            for item in snapshot.network_adapters[:6]
        ]
        if adapter_bits:
            lines.append("Network adapters: " + ", ".join(adapter_bits))

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
    if arguments is None:
        arguments = {}
    if not isinstance(arguments, dict):
        return SkillValidationResult(False, f"Arguments for {name} must be an object.")

    allowed_keys = set(skill.input_schema)
    unknown = sorted(set(arguments) - allowed_keys)
    if unknown:
        return SkillValidationResult(
            False,
            f"Unknown argument(s) for {name}: {', '.join(unknown)}.",
        )

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
    return False


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

    if kind in {
        "audio_set_volume",
        "audio_mute_session",
        "audio_route_session",
        "clear_app_audio_route",
    }:
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
        elif kind == "clear_app_audio_route":
            payload["process_name"] = session.get("process_name", "")
            description = f"Restore {session['display_name']} to the system default audio device."
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

    if kind in {"load_saved_layout", "delete_saved_layout"}:
        layout, message = _resolve_layout(args, snapshot)
        if not layout:
            return None, message
        verb = "Load" if kind == "load_saved_layout" else "Delete"
        return _action(
            kind,
            description=f"{verb} saved layout \"{layout['name']}\".",
            payload={"layout_id": layout["id"]},
        ), ""

    if kind == "restart_network_adapter":
        adapter, message = _resolve_adapter(args, snapshot)
        if not adapter:
            return None, message
        adapter_name = adapter["name"]
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
            root, message = _resolve_allowlisted_scan_root(args.get("root"), snapshot)
            if not root:
                return None, message
            payload["root"] = root
        if args.get("min_size_mb"):
            payload["min_size_mb"] = int(args["min_size_mb"])
        return _action(kind, payload=payload), ""

    if kind in {"scan_downloads_large_files", "scan_desktop_large_files"}:
        folder_name = "Downloads" if kind == "scan_downloads_large_files" else "Desktop"
        from pathlib import Path
        root = str((Path.home() / folder_name).expanduser().resolve())
        payload = {"root": root}
        if args.get("min_size_mb"):
            payload["min_size_mb"] = int(args["min_size_mb"])
        return _action(
            "scan_large_files",
            title=ASSISTANT_TOOLS[kind].title,
            description=ASSISTANT_TOOLS[kind].description,
            payload=payload,
        ), ""

    if kind == "scan_folder_sizes":
        payload = {}
        if args.get("max_entries") is not None:
            payload["max_entries"] = max(1, min(int(args["max_entries"]), 100))
        return _action(kind, payload=payload), ""

    if kind == "scan_duplicate_files":
        payload = {}
        if args.get("min_size_mb") is not None:
            payload["min_size_mb"] = max(1, int(args["min_size_mb"]))
        if args.get("limit_groups") is not None:
            payload["limit_groups"] = max(1, min(int(args["limit_groups"]), 100))
        return _action(kind, payload=payload), ""

    if kind == "end_process":
        process, message = _resolve_process(args, snapshot)
        if not process:
            return None, message
        pid = int(process["pid"])
        allowed, info = sysinfo.is_process_termination_allowed(pid, process.get("name", ""))
        if not allowed:
            return None, info
        return _action(
            kind,
            description=f"End process {process.get('name', 'PID')} (PID {pid}).",
            payload={"pid": pid},
        ), ""

    if kind == "set_startup_item_enabled":
        item, message = _resolve_startup_item(args, snapshot)
        if not item:
            return None, message
        enabled = bool(args.get("enabled"))
        payload = {
            "name": item.get("name", ""),
            "source": item.get("source", ""),
            "enabled": enabled,
        }
        if item.get("command"):
            payload["command"] = str(item["command"])
        verb = "Enable" if enabled else "Disable"
        return _action(
            kind,
            description=f"{verb} startup item \"{payload['name']}\" ({payload['source']}).",
            payload=payload,
        ), ""

    if kind == "open_windows_settings":
        page = str(args.get("page", "")).strip().lower()
        allowed = {
            "display", "network", "windows_update", "apps", "sound",
            "storage", "power", "privacy", "troubleshoot", "about",
        }
        if page not in allowed:
            return None, (
                "Settings page must be display, network, windows_update, apps, sound, "
                "storage, power, privacy, troubleshoot, or about."
            )
        return _action(
            kind,
            description=f"Open Windows Settings page ({page}).",
            payload={"page": page},
        ), ""

    if kind == "open_known_folder":
        folder = str(args.get("folder", "")).strip().lower()
        allowed = {
            "temp", "downloads", "desktop", "documents", "pictures",
            "startup", "local_appdata", "recycle_bin",
        }
        if folder not in allowed:
            return None, (
                "Folder must be temp, downloads, desktop, documents, pictures, "
                "startup, local_appdata, or recycle_bin."
            )
        return _action(
            kind,
            description=f"Open known folder ({folder}).",
            payload={"folder": folder},
        ), ""

    if kind in {"clean_temp_files", "clean_browser_cache", "clean_thumbnail_cache"}:
        key_map = {
            "clean_temp_files": {"user_temp", "windows_temp"},
            "clean_browser_cache": {"chrome_cache", "edge_cache", "firefox_cache"},
            "clean_thumbnail_cache": {"thumbnail_cache"},
        }
        return _action(
            kind,
            description=ASSISTANT_TOOLS[kind].description,
            payload={"category_keys": sorted(key_map[kind])},
        ), ""

    if kind == "check_dns_resolve":
        host = str(args.get("host") or "one.one.one.one").strip().lower()
        if host not in toolbox.DNS_PING_HOSTS:
            return None, (
                f"Host is not on the allowlist. Allowed hosts: "
                f"{', '.join(sorted(toolbox.DNS_PING_HOSTS))}."
            )
        return _action(kind, payload={"host": host}), ""

    if kind == "ping_host":
        host = str(args.get("host") or "one.one.one.one").strip().lower()
        if host not in toolbox.DNS_PING_HOSTS:
            return None, (
                f"Host is not on the allowlist. Allowed hosts: "
                f"{', '.join(sorted(toolbox.DNS_PING_HOSTS))}."
            )
        try:
            count = int(args.get("count", 2))
        except (TypeError, ValueError):
            count = 2
        count = max(1, min(count, 4))
        return _action(kind, payload={"host": host, "count": count}), ""

    if kind == "capture_layout_snapshot":
        name = str(args.get("name") or "Assistant Layout").strip()[:80] or "Assistant Layout"
        return _action(
            kind,
            description=f"Save the current window layout as \"{name}\".",
            payload={"name": name},
        ), ""

    if kind == "set_default_audio_device":
        device, message = _resolve_audio_device(args, snapshot)
        if not device:
            return None, message
        return _action(
            kind,
            description=f"Set default playback device to {device['name']}.",
            payload={"device_id": device["id"]},
        ), ""

    if kind in {
        "open_task_manager",
        "open_resource_monitor",
        "open_device_manager",
        "open_services_manager",
        "open_disk_cleanup",
    }:
        return _action(kind, payload={"tool": kind.replace("open_", "")}), ""

    if kind == "check_service_status":
        service = str(args.get("service", "")).strip().lower()
        if service not in toolbox.SERVICE_STATUS_KEYS:
            return None, (
                "Service key is not on the allowlist. Allowed keys: "
                f"{', '.join(sorted(set(toolbox.SERVICE_STATUS_KEYS)))}."
            )
        return _action(
            kind,
            description=f"Check status of service key \"{service}\".",
            payload={"service": service},
        ), ""

    if kind == "open_windows_troubleshooter":
        key = str(args.get("troubleshooter", "")).strip().lower()
        if key not in toolbox.TROUBLESHOOTER_KEYS:
            return None, (
                "Troubleshooter must be internet, network_adapter, audio, printer, "
                "bluetooth, or windows_update."
            )
        label = toolbox.TROUBLESHOOTER_KEYS[key][1]
        return _action(
            kind,
            description=f"Open the {label} troubleshooter.",
            payload={"troubleshooter": key},
        ), ""

    if kind == "check_unexpected_shutdowns":
        hours = int(args.get("hours", 72))
        hours = max(1, min(hours, 168))
        return _action(
            kind,
            description=f"Check unexpected shutdowns from the last {hours} hour(s).",
            payload={"hours": hours},
        ), ""

    if kind == "scan_volume_errors":
        volume = str(args.get("volume") or "").strip()
        payload = {}
        if volume:
            payload["volume"] = volume
        return _action(
            kind,
            description="Run a read-only online volume error scan.",
            payload=payload,
        ), ""

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


def _allowlisted_scan_roots(snapshot=None):
    from pathlib import Path
    import os

    candidates = [
        Path.home(),
        Path.home() / "Downloads",
        Path.home() / "Desktop",
        Path.home() / "Documents",
        Path.home() / "Pictures",
        Path(os.environ.get("TEMP") or os.environ.get("TMP") or ""),
    ]
    roots = []
    for path in candidates:
        try:
            resolved = str(path.expanduser().resolve())
        except OSError:
            continue
        if resolved and os.path.isdir(resolved):
            roots.append(os.path.normcase(resolved))
    if snapshot:
        for cat in getattr(snapshot, "cleanup_categories", []) or []:
            for cleanup_path in getattr(cat, "paths", []) or []:
                try:
                    resolved = os.path.normcase(str(Path(cleanup_path).expanduser().resolve()))
                except OSError:
                    continue
                if resolved and os.path.isdir(resolved):
                    roots.append(resolved)
    return sorted(set(roots))


def _resolve_allowlisted_scan_root(root, snapshot=None):
    import os
    from pathlib import Path

    if not root:
        return None, "No scan root was provided."
    try:
        resolved = str(Path(root).expanduser().resolve())
    except OSError:
        return None, "That scan root could not be resolved."
    if not os.path.isdir(resolved):
        return None, "That scan root does not exist."
    normalized = os.path.normcase(resolved)
    for allowed in _allowlisted_scan_roots(snapshot):
        try:
            if os.path.commonpath([normalized, allowed]) == allowed:
                return resolved, ""
        except ValueError:
            continue
    return None, "Scan root must be under an allowlisted folder (home, Downloads, Desktop, Documents, Pictures, temp, or scanned cleanup paths)."


def _resolve_adapter(args, snapshot):
    adapters = getattr(snapshot, "network_adapters", []) if snapshot else []
    if not adapters:
        adapters = toolbox.list_network_adapter_names()
    if not adapters:
        return None, "No network adapters were found. Refresh network information first."
    needle = str(args.get("adapter_name") or "").strip().lower()
    if not needle:
        up = [item for item in adapters if item.get("is_up")]
        if len(up) == 1:
            matches = up
        elif len(adapters) == 1:
            matches = adapters
        elif len(up) > 1:
            matches = up
        else:
            matches = adapters if len(adapters) > 1 else []
    else:
        matches = [item for item in adapters if needle in str(item.get("name", "")).lower()]
    return _single_match(matches, "network adapter")


def _resolve_startup_item(args, snapshot):
    items = getattr(snapshot, "startup_items", []) if snapshot else []
    if not items:
        return None, "Refresh startup programs before changing a startup item."
    name = str(args.get("name") or "").strip().lower()
    source = str(args.get("source") or "").strip().lower()
    matches = items
    if name:
        matches = [item for item in matches if name in str(item.get("name", "")).lower()]
    if source:
        matches = [item for item in matches if source in str(item.get("source", "")).lower()]
    if not name and not source:
        return None, "Provide a startup item name (and source if needed)."
    return _single_match(matches, "startup item")


def _resolve_process(args, snapshot):
    processes = []
    if snapshot:
        processes.extend(getattr(snapshot, "top_cpu_processes", []) or [])
        processes.extend(getattr(snapshot, "top_memory_processes", []) or [])
    # Dedupe by pid
    by_pid = {}
    for process in processes:
        try:
            by_pid[int(process.get("pid"))] = process
        except (TypeError, ValueError):
            continue
    processes = list(by_pid.values())
    if args.get("pid") is not None:
        pid = int(args["pid"])
        match = by_pid.get(pid)
        if match:
            return match, ""
        return None, (
            "That process is not in the current snapshot. "
            "Refresh top processes before ending a process."
        )
    needle = str(args.get("process_name") or args.get("app") or "").strip().lower()
    if not needle:
        return None, "Provide a process pid or process name from the snapshot."
    if not processes:
        return None, "Refresh top processes before ending a process by name."
    matches = [
        process for process in processes
        if needle in str(process.get("name", "")).lower()
    ]
    return _single_match(matches, "process")


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
        return None, "Refresh layouts before targeting a saved layout."
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

    if kind in {
        "audio_set_volume",
        "audio_mute_session",
        "audio_route_session",
        "clear_app_audio_route",
    }:
        result = _execute_audio_action(action)
        refreshed = collect_assistant_snapshot(include_cleanup=False) if result.success else snapshot
        return result, refreshed

    if kind in {"load_saved_layout", "delete_saved_layout"}:
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
    if kind == "scan_folder_sizes":
        return toolbox.scan_folder_sizes(max_entries=payload.get("max_entries", 40))
    if kind == "scan_duplicate_files":
        return toolbox.scan_duplicate_files(
            min_size_mb=payload.get("min_size_mb", 1),
            limit_groups=payload.get("limit_groups", 25),
        )
    if kind == "end_process":
        return toolbox.end_process(payload.get("pid"))
    if kind == "set_startup_item_enabled":
        return toolbox.set_startup_item_enabled(
            payload.get("name", ""),
            payload.get("source", ""),
            bool(payload.get("enabled")),
            command=payload.get("command", ""),
        )
    if kind == "renew_ip_address":
        return toolbox.renew_ip_address()
    if kind == "reset_winsock":
        return toolbox.reset_winsock()
    if kind == "check_pending_reboot":
        return toolbox.check_pending_reboot()
    if kind == "check_battery_report":
        return toolbox.check_battery_report()
    if kind == "restart_explorer":
        return toolbox.restart_explorer()
    if kind == "open_windows_settings":
        return toolbox.open_windows_settings(payload.get("page", ""))
    if kind == "open_known_folder":
        return toolbox.open_known_folder(payload.get("folder", ""))
    if kind == "create_restore_point":
        return toolbox.create_restore_point(payload.get("description", "PC Fix restore point"))
    if kind == "export_pc_report":
        return toolbox.export_pc_report()
    if kind == "get_recycle_bin_size":
        return toolbox.get_recycle_bin_size()
    if kind == "empty_recycle_bin":
        return toolbox.empty_recycle_bin()
    if kind in {"clean_temp_files", "clean_browser_cache", "clean_thumbnail_cache"}:
        return toolbox.clean_cleanup_categories_by_keys(payload.get("category_keys", []))
    if kind == "list_network_adapters":
        return toolbox.list_network_adapters()
    if kind == "check_dns_resolve":
        return toolbox.check_dns_resolve(payload.get("host", "one.one.one.one"))
    if kind == "ping_host":
        return toolbox.ping_host(payload.get("host", "one.one.one.one"), payload.get("count", 2))
    if kind == "check_default_gateway":
        return toolbox.check_default_gateway()
    if kind == "show_wifi_status":
        return toolbox.show_wifi_status()
    if kind == "check_system_uptime":
        return toolbox.check_system_uptime()
    if kind == "check_memory_pressure":
        return toolbox.check_memory_pressure()
    if kind == "list_installed_gpus":
        return toolbox.list_installed_gpus()
    if kind == "open_task_manager":
        return toolbox.open_system_tool("task_manager")
    if kind == "open_resource_monitor":
        return toolbox.open_system_tool("resource_monitor")
    if kind == "open_device_manager":
        return toolbox.open_system_tool("device_manager")
    if kind == "open_services_manager":
        return toolbox.open_system_tool("services")
    if kind == "open_disk_cleanup":
        return toolbox.open_system_tool("disk_cleanup")
    if kind == "capture_layout_snapshot":
        return toolbox.capture_window_layout(payload.get("name", "Assistant Layout"))
    if kind == "set_default_audio_device":
        return toolbox.set_default_audio_device(payload.get("device_id", ""))
    if kind == "list_saved_layouts":
        return toolbox.list_saved_layouts()
    if kind == "check_disk_free_space":
        return toolbox.check_disk_free_space()
    if kind == "list_printers":
        return toolbox.list_printers()
    if kind == "list_usb_devices":
        return toolbox.list_usb_devices()
    if kind == "list_running_services":
        return toolbox.list_running_services()
    if kind == "list_third_party_services":
        return toolbox.list_third_party_services()
    if kind == "check_service_status":
        return toolbox.check_service_status(payload.get("service", ""))
    if kind == "list_problem_devices":
        return toolbox.list_problem_devices()
    if kind == "check_listening_ports":
        return toolbox.check_listening_ports()
    if kind == "check_bluetooth_status":
        return toolbox.check_bluetooth_status()
    if kind == "check_unexpected_shutdowns":
        return toolbox.check_unexpected_shutdowns(hours=payload.get("hours", 72))
    if kind == "check_component_store_health":
        return toolbox.check_component_store_health()
    if kind == "scan_volume_errors":
        return toolbox.scan_volume_errors(volume=payload.get("volume"))
    if kind == "restart_print_spooler":
        return toolbox.restart_print_spooler()
    if kind == "start_sfc_scan":
        return toolbox.start_sfc_scan()
    if kind == "open_windows_troubleshooter":
        return toolbox.open_windows_troubleshooter(payload.get("troubleshooter", ""))
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

    if action.kind == "clear_app_audio_route":
        process_name = action.payload.get("process_name", "")
        route = audio_control.clear_app_output_device(
            process_id=pid,
            process_name=process_name or None,
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

    if action.kind == "delete_saved_layout":
        result = toolbox.delete_saved_layout(layout.get("id", ""))
        return AssistantActionResult(result.success, result.summary, result.errors)

    result = window_layouts.apply_layout(layout, launch_missing=True)
    parts = [f"Moved {result.moved} window(s)"]
    if result.launched:
        parts.append(f"launched {len(result.launched)} app(s)")
    if result.missing:
        parts.append(f"{len(result.missing)} window(s) missing")
    errors = list(result.errors)
    return AssistantActionResult(not errors, "Layout loaded: " + ", ".join(parts) + ".", errors)
