from dataclasses import dataclass, field
from datetime import datetime
from uuid import uuid4

from app import system_info as sysinfo


@dataclass
class AssistantSnapshot:
    timestamp: datetime
    cpu: dict | None = None
    memory: dict | None = None
    disks: list = field(default_factory=list)
    startup_items: list = field(default_factory=list)
    top_cpu_processes: list = field(default_factory=list)
    top_memory_processes: list = field(default_factory=list)
    displays: list = field(default_factory=list)
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


@dataclass
class AssistantActionResult:
    success: bool
    message: str
    errors: list = field(default_factory=list)


def _action(kind, title, description, risk="Low", payload=None, confirm_label="Confirm"):
    return AssistantAction(
        id=str(uuid4()),
        kind=kind,
        title=title,
        description=description,
        risk=risk,
        payload=payload or {},
        confirm_label=confirm_label,
    )


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
        snapshot.startup_items = sysinfo.get_startup_items()
    except Exception:
        snapshot.unavailable.append("startup apps")

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
            try:
                mode = sysinfo.get_current_display_mode(device.name)
                mode_text = f"{mode.width}x{mode.height} @ {mode.refresh_hz} Hz"
            except Exception:
                mode_text = "mode unavailable"
            displays.append({
                "name": device.name,
                "label": device.label,
                "primary": bool(device.is_primary),
                "mode": mode_text,
            })
        snapshot.displays = displays
    except Exception:
        snapshot.unavailable.append("displays")

    if include_cleanup:
        try:
            snapshot.cleanup_categories = sysinfo.scan_cleanup_targets()
        except Exception:
            snapshot.unavailable.append("cleanup candidates")

    return snapshot


def snapshot_has_useful_data(snapshot):
    return any([
        snapshot.cpu,
        snapshot.memory,
        snapshot.disks,
        snapshot.startup_items,
        snapshot.top_cpu_processes,
        snapshot.top_memory_processes,
        snapshot.displays,
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

    if "startup apps" in snapshot.unavailable:
        lines.append("Startup apps: unavailable")
    else:
        lines.append(f"Startup apps: {len(snapshot.startup_items)} detected")
        for item in snapshot.startup_items[:5]:
            lines.append(f"- Startup: {item['name']} ({item['source']})")

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
    rows.append(("Displays", f"{len(snapshot.displays)} connected"))

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

    if any(word in lowered for word in ("health", "slow", "cpu", "ram", "memory", "disk", "space")):
        actions.append(_action(
            "refresh_snapshot",
            "Refresh PC snapshot",
            "Collect fresh CPU, RAM, disk, startup, process, and display details for the assistant.",
            confirm_label="Refresh",
        ))

    if any(word in lowered for word in ("clean", "cleanup", "junk", "temp", "cache", "free space")):
        if snapshot and snapshot.cleanup_categories:
            total = sum(cat.size_bytes for cat in snapshot.cleanup_categories)
            actions.append(_action(
                "clean_cleanup_candidates",
                "Clean scanned safe categories",
                f"Delete the scanned temp/cache categories shown in the snapshot ({sysinfo.format_bytes(total)}).",
                risk="Medium",
                payload={"category_keys": [cat.key for cat in snapshot.cleanup_categories]},
                confirm_label="Clean",
            ))
        else:
            actions.append(_action(
                "scan_cleanup",
                "Scan safe cleanup locations",
                "Scan known temp, browser cache, thumbnail cache, and Recycle Bin locations.",
                confirm_label="Scan",
            ))

    if "startup" in lowered:
        actions.append(_action(
            "refresh_startup",
            "Refresh startup apps",
            "Reload startup entries so the assistant can review the latest list.",
            confirm_label="Refresh",
        ))

    if "display" in lowered or "refresh rate" in lowered or "monitor" in lowered:
        actions.append(_action(
            "refresh_displays",
            "Refresh display information",
            "Reload connected monitors and current display modes.",
            confirm_label="Refresh",
        ))

    if "audio" in lowered or "sound" in lowered or "speaker" in lowered:
        actions.append(_action(
            "refresh_audio",
            "Refresh audio information",
            "Ask the Audio tab to reload devices and active app sessions.",
            confirm_label="Refresh",
        ))

    if "layout" in lowered or "window" in lowered:
        actions.append(_action(
            "refresh_layouts",
            "Refresh layouts",
            "Ask the Layouts tab to rescan open windows and saved layouts.",
            confirm_label="Refresh",
        ))

    return actions
