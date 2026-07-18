# Assistant Skills List

This file documents what the PC Fix assistant can request through LLM chat. The model can ask for these skills by emitting validated `skill_request` JSON, but Python converts them into safe app actions. The LLM does not execute commands directly.

## Safety Rules

- System-changing skills must become confirmation cards before they run.
- The assistant cannot run arbitrary shell commands, arbitrary Python, registry edits, unrestricted PowerShell, or arbitrary file deletion.
- Target-based skills are resolved by Python from the current PC snapshot. If the target is missing or ambiguous, the action is skipped or a safe refresh action is suggested.
- Keep this file updated whenever `ASSISTANT_SKILLS` or related action behavior changes in `app/assistant_core.py`.

## Skills

| Skill | Action | Risk | Confirmation | What It Does |
| --- | --- | --- | --- | --- |
| `diagnose_pc_health` | `refresh_snapshot` | Read-only | No | Refreshes the full PC snapshot so the assistant can review CPU, RAM, disks, startup items, processes, displays, network, hardware, audio, layouts, and cleanup state. |
| `inspect_top_processes` | `inspect_top_processes` | Read-only | No | Refreshes top CPU and RAM process lists for performance troubleshooting. |
| `refresh_network` | `refresh_network` | Read-only | No | Refreshes network sent and received counters. |
| `refresh_hardware` | `refresh_hardware` | Read-only | No | Refreshes a high-level hardware summary such as CPU, GPU, core counts, system, board, BIOS, disks, and memory modules. |
| `refresh_startup_programs` | `refresh_startup` | Read-only | No | Refreshes startup entries and installed-program summary. |
| `scan_cleanup` | `scan_cleanup` | Read-only | No | Scans known safe cleanup locations such as temp folders, browser caches, thumbnail cache, and Recycle Bin. It does not delete files. |
| `clean_scanned_cleanup` | `clean_cleanup_candidates` | Medium | Yes | Deletes only cleanup categories that were already scanned and shown to the user. If no category keys are provided, Python uses the currently scanned categories. |
| `refresh_displays` | `refresh_displays` | Read-only | No | Refreshes connected display information and current/supported refresh-rate details. |
| `set_display_refresh_rate` | `set_display_refresh_rate` | Medium | Yes | Changes one display's refresh rate after Python resolves the display target and validates the requested Hz. Resolution and scaling are left untouched. |
| `refresh_audio` | `refresh_audio` | Read-only | No | Refreshes playback devices and active app audio sessions. |
| `set_app_volume` | `audio_set_volume` | Low | Yes | Sets one active app audio session volume after Python resolves the app target from `pid`, `process_name`, or friendly `app` text. |
| `mute_app_audio` | `audio_mute_session` | Low | Yes | Mutes or unmutes one active app audio session after Python resolves the app target. |
| `route_app_audio` | `audio_route_session` | Low | Yes | Routes one active app audio session to a playback device after Python resolves both the app and device targets. |
| `refresh_layouts` | `refresh_layouts` | Read-only | No | Refreshes open-window layout information and saved layouts. |
| `load_saved_layout` | `load_saved_layout` | Medium | Yes | Loads a saved window layout after Python resolves the layout target by id or name. It may move matching windows and launch missing apps when possible. |
| `check_windows_updates` | `check_windows_updates` | Read-only | No | Reads pending Windows Update count, reboot-pending status, and recent hotfix information. |
| `check_disk_health` | `check_disk_health` | Read-only | No | Reads physical disk health, operational status, media type, and size where Windows exposes it. |
| `scan_event_log_errors` | `scan_event_log_errors` | Read-only | No | Summarizes recent critical and error events from the Windows System and Application event logs. |
| `check_network_health` | `check_network_health` | Read-only | No | Checks local IPs, active adapters, DNS servers, and basic internet reachability. |
| `flush_dns_cache` | `flush_dns_cache` | Low | Yes | Clears the Windows DNS resolver cache. |
| `restart_network_adapter` | `restart_network_adapter` | Medium | Yes | Restarts one named network adapter. This can briefly disconnect the network. |
| `check_power_plan` | `check_power_plan` | Read-only | No | Reads the active Windows power plan and available schemes. |
| `set_power_plan` | `set_power_plan` | Low | Yes | Switches the active Windows power plan to Balanced, High Performance, or Power Saver. |
| `review_startup_impact` | `review_startup_impact` | Read-only | No | Classifies startup entries with conservative keep/review/optional hints. It does not disable startup items by itself. |
| `check_windows_security` | `check_windows_security` | Read-only | No | Reads Defender and firewall status where Windows exposes it. |
| `scan_large_files` | `scan_large_files` | Read-only | No | Finds large files under a selected root without deleting anything. |
| `scan_folder_sizes` | `scan_folder_sizes` | Read-only | No | Breaks down folder sizes under common user locations such as Downloads, Desktop, and Documents. It does not delete anything. |
| `scan_duplicate_files` | `scan_duplicate_files` | Read-only | No | Finds duplicate file groups by size and content hash. Report only; it does not delete files. |
| `end_process` | `end_process` | Medium | Yes | Ends one non-protected process by PID. Protected system processes are rejected in Python. |
| `set_startup_item_enabled` | `set_startup_item_enabled` | Medium | Yes | Enables or disables one allowlisted startup Run value or Startup-folder shortcut after Python resolves name + source. |
| `renew_ip_address` | `renew_ip_address` | Low | Yes | Releases and renews the Windows IP address configuration. |
| `reset_winsock` | `reset_winsock` | Medium | Yes | Resets the Windows Winsock catalog. A reboot may be required afterward. |
| `check_pending_reboot` | `check_pending_reboot` | Read-only | No | Checks whether Windows reports a pending reboot. |
| `check_battery_report` | `check_battery_report` | Read-only | No | Reads laptop battery charge and capacity signals when a battery is present. |
| `restart_explorer` | `restart_explorer` | Low | Yes | Restarts Windows Explorer to recover a frozen taskbar or desktop shell. |
| `open_windows_settings` | `open_windows_settings` | Low | No | Opens one allowlisted Windows Settings page (`display`, `network`, `windows_update`, `apps`, `sound`). |
| `open_known_folder` | `open_known_folder` | Low | No | Opens one allowlisted known folder (`temp`, `downloads`, `startup`, `local_appdata`, `recycle_bin`). |
| `create_restore_point` | `create_restore_point` | Medium | Yes | Requests a Windows system restore point before higher-risk repair operations. |
| `export_pc_report` | `export_pc_report` | Read-only | No | Writes a local diagnostic report with system summary and startup review details. |

## Skill Request Format

The LLM may request a skill with fenced JSON:

```json
{"type":"skill_request","skill":"scan_cleanup","arguments":{}}
```

Target-based examples:

```json
{"type":"skill_request","skill":"set_app_volume","arguments":{"app":"chrome","level":0.35}}
```

```json
{"type":"skill_request","skill":"set_display_refresh_rate","arguments":{"display_label":"Dell","hz":144}}
```

```json
{"type":"skill_request","skill":"load_saved_layout","arguments":{"layout_name":"Work"}}
```

## Accepted Friendly Arguments

- Audio app targets: `pid`, `process_name`, or `app`.
- Audio device targets: `device_id` or `device_name`.
- Display targets: `device_name` or `display_label`; if omitted, Python uses the primary display when unambiguous.
- Layout targets: `layout_id` or `layout_name`; if omitted, Python only uses the layout when exactly one saved layout exists.
- Cleanup targets: optional `category_keys`; if omitted, Python uses currently scanned cleanup categories.
- Network adapter targets: `adapter_name`.
- Power plan targets: `plan_name` with `balanced`, `high_performance`, or `power_saver`.
- Event log scan options: optional `hours`.
- Large-file scan options: optional `root` and `min_size_mb`.
- Folder-size scan options: optional `max_entries`.
- Duplicate scan options: optional `min_size_mb` and `limit_groups`.
- End process targets: required `pid` (protected processes are rejected).
- Startup toggle targets: required `name`, `source`, and `enabled`; optional `command` when re-enabling.
- Settings page targets: `page` with `display`, `network`, `windows_update`, `apps`, or `sound`.
- Known folder targets: `folder` with `temp`, `downloads`, `startup`, `local_appdata`, or `recycle_bin`.
- Restore point options: optional `description`.
