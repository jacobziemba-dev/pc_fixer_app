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
| `restart_network_adapter` | `restart_network_adapter` | Medium | Yes | Restarts one network adapter after Python resolves the adapter from the snapshot. This can briefly disconnect the network. |
| `check_power_plan` | `check_power_plan` | Read-only | No | Reads the active Windows power plan and available schemes. |
| `set_power_plan` | `set_power_plan` | Low | Yes | Switches the active Windows power plan to Balanced, High Performance, or Power Saver. |
| `review_startup_impact` | `review_startup_impact` | Read-only | No | Classifies startup entries with conservative keep/review/optional hints. It does not disable startup items by itself. |
| `check_windows_security` | `check_windows_security` | Read-only | No | Reads Defender and firewall status where Windows exposes it. |
| `scan_large_files` | `scan_large_files` | Read-only | No | Finds large files under an allowlisted root without deleting anything. |
| `scan_folder_sizes` | `scan_folder_sizes` | Read-only | No | Breaks down folder sizes under common user locations such as Downloads, Desktop, and Documents. It does not delete anything. |
| `scan_duplicate_files` | `scan_duplicate_files` | Read-only | No | Finds duplicate file groups by size and content hash. Report only; it does not delete files. |
| `end_process` | `end_process` | Medium | Yes | Ends one non-protected process by PID or friendly name from the live snapshot. Protected system processes are rejected in Python. |
| `set_startup_item_enabled` | `set_startup_item_enabled` | Medium | Yes | Enables or disables one allowlisted startup Run value or Startup-folder shortcut after Python resolves name + source from the snapshot. |
| `renew_ip_address` | `renew_ip_address` | Low | Yes | Releases and renews the Windows IP address configuration. |
| `reset_winsock` | `reset_winsock` | Medium | Yes | Resets the Windows Winsock catalog. A reboot may be required afterward. |
| `check_pending_reboot` | `check_pending_reboot` | Read-only | No | Checks whether Windows reports a pending reboot. |
| `check_battery_report` | `check_battery_report` | Read-only | No | Reads laptop battery charge and capacity signals when a battery is present. |
| `restart_explorer` | `restart_explorer` | Low | Yes | Restarts Windows Explorer to recover a frozen taskbar or desktop shell. |
| `open_windows_settings` | `open_windows_settings` | Low | No | Opens one allowlisted Windows Settings page (`display`, `network`, `windows_update`, `apps`, `sound`, `storage`, `power`, `privacy`, `troubleshoot`, `about`). |
| `open_known_folder` | `open_known_folder` | Low | No | Opens one allowlisted known folder (`temp`, `downloads`, `desktop`, `documents`, `pictures`, `startup`, `local_appdata`, `recycle_bin`). |
| `create_restore_point` | `create_restore_point` | Medium | Yes | Requests a Windows system restore point before higher-risk repair operations. |
| `export_pc_report` | `export_pc_report` | Read-only | No | Writes a local diagnostic report with system summary and startup review details. |
| `get_recycle_bin_size` | `get_recycle_bin_size` | Read-only | No | Reports how much space the Recycle Bin is using. |
| `empty_recycle_bin` | `empty_recycle_bin` | Medium | Yes | Empties the Windows Recycle Bin only. |
| `clean_temp_files` | `clean_temp_files` | Medium | Yes | Deletes scanned user/Windows temp cleanup categories only. |
| `clean_browser_cache` | `clean_browser_cache` | Medium | Yes | Deletes scanned Chrome/Edge/Firefox cache categories only. |
| `clean_thumbnail_cache` | `clean_thumbnail_cache` | Low | Yes | Deletes the scanned thumbnail cache category only. |
| `scan_downloads_large_files` | `scan_large_files` | Read-only | No | Convenience large-file scan rooted at Downloads. |
| `scan_desktop_large_files` | `scan_large_files` | Read-only | No | Convenience large-file scan rooted at Desktop. |
| `list_network_adapters` | `list_network_adapters` | Read-only | No | Lists adapter names and up/down status for safer network targeting. |
| `check_dns_resolve` | `check_dns_resolve` | Read-only | No | Resolves one allowlisted hostname (`one.one.one.one`, `dns.google`, etc.). |
| `ping_host` | `ping_host` | Read-only | No | Pings one allowlisted host with a small count cap. |
| `check_default_gateway` | `check_default_gateway` | Read-only | No | Reads default gateway / route summary for no-internet triage. |
| `show_wifi_status` | `show_wifi_status` | Read-only | No | Reads Wi-Fi SSID/signal/state when available. Never reads passwords. |
| `check_system_uptime` | `check_system_uptime` | Read-only | No | Reads boot time and uptime. |
| `check_memory_pressure` | `check_memory_pressure` | Read-only | No | Reads RAM and pagefile/swap pressure signals. |
| `list_installed_gpus` | `list_installed_gpus` | Read-only | No | Lists installed GPU names from hardware discovery. |
| `check_smart_status` | `check_disk_health` | Read-only | No | Thin wrapper around physical disk health status. |
| `open_task_manager` | `open_task_manager` | Low | No | Opens Windows Task Manager. |
| `open_resource_monitor` | `open_resource_monitor` | Low | No | Opens Windows Resource Monitor. |
| `open_device_manager` | `open_device_manager` | Low | No | Opens Windows Device Manager. |
| `capture_layout_snapshot` | `capture_layout_snapshot` | Low | Yes | Saves the current window layout for later restore. |
| `set_default_audio_device` | `set_default_audio_device` | Low | Yes | Sets the default playback device after Python resolves the device from the snapshot. |
| `clear_app_audio_route` | `clear_app_audio_route` | Low | Yes | Restores one app audio session to the system default playback device after Python resolves the app target. |
| `delete_saved_layout` | `delete_saved_layout` | Medium | Yes | Deletes one saved window layout after Python resolves the layout by id or name. |
| `list_saved_layouts` | `list_saved_layouts` | Read-only | No | Lists saved window layout names and ids. |
| `check_disk_free_space` | `check_disk_free_space` | Read-only | No | Reports free/used space for mounted volumes. |
| `list_printers` | `list_printers` | Read-only | No | Lists installed printers and default/status signals where available. |
| `list_usb_devices` | `list_usb_devices` | Read-only | No | Lists present USB devices and status. |
| `list_running_services` | `list_running_services` | Read-only | No | Lists a capped set of currently running Windows services. |
| `list_third_party_services` | `list_third_party_services` | Read-only | No | Lists running services whose binaries are outside Windows system folders. |
| `check_service_status` | `check_service_status` | Read-only | No | Reads status for one allowlisted service key (`spooler`, `wuauserv`, `bits`, `audio`, `dhcp`, `dnscache`, `themes`, `bluetooth`, `defender`, `firewall`, `schedule`). |
| `list_problem_devices` | `list_problem_devices` | Read-only | No | Lists Plug and Play devices that are not reporting OK status. |
| `check_listening_ports` | `check_listening_ports` | Read-only | No | Lists top listening endpoints and owning processes. Report only; no firewall changes. |
| `check_bluetooth_status` | `check_bluetooth_status` | Read-only | No | Reads Bluetooth radio/service status when Windows exposes it. |
| `check_unexpected_shutdowns` | `check_unexpected_shutdowns` | Read-only | No | Summarizes recent unexpected/dirty shutdown events. |
| `check_component_store_health` | `check_component_store_health` | Read-only | No | Runs `DISM /Online /Cleanup-Image /CheckHealth` only. Does not restore the image. |
| `scan_volume_errors` | `scan_volume_errors` | Read-only | No | Runs online `chkdsk /scan` on an allowlisted volume (system drive by default). Does not use `/f` or `/r`. |
| `restart_print_spooler` | `restart_print_spooler` | Medium | Yes | Restarts only the Windows Print Spooler service. |
| `start_sfc_scan` | `start_sfc_scan` | Medium | Yes | Runs `sfc /scannow`. Needs elevation and can take several minutes. |
| `open_services_manager` | `open_services_manager` | Low | No | Opens the Windows Services manager (`services.msc`). |
| `open_disk_cleanup` | `open_disk_cleanup` | Low | No | Opens the Windows Disk Cleanup UI without deleting anything automatically. |
| `open_windows_troubleshooter` | `open_windows_troubleshooter` | Low | No | Opens one allowlisted troubleshooter (`internet`, `network_adapter`, `audio`, `printer`, `bluetooth`, `windows_update`). |

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
- Network adapter targets: optional `adapter_name`; if omitted, Python uses a single unambiguous up adapter from the snapshot.
- Power plan targets: `plan_name` with `balanced`, `high_performance`, or `power_saver`.
- Event log scan options: optional `hours`.
- Large-file scan options: optional allowlisted `root` and `min_size_mb`.
- Folder-size scan options: optional `max_entries`.
- Duplicate scan options: optional `min_size_mb` and `limit_groups`.
- End process targets: `pid`, or `process_name` / `app` matched from the snapshot top-process lists.
- Startup toggle targets: `enabled` plus `name` and/or `source` resolved from the snapshot; optional `command` when re-enabling.
- Settings page targets: `page` with `display`, `network`, `windows_update`, `apps`, `sound`, `storage`, `power`, `privacy`, `troubleshoot`, or `about`.
- Known folder targets: `folder` with `temp`, `downloads`, `desktop`, `documents`, `pictures`, `startup`, `local_appdata`, or `recycle_bin`.
- DNS/ping hosts: allowlisted only (`one.one.one.one`, `1.1.1.1`, `dns.google`, `8.8.8.8`, `cloudflare.com`, `microsoft.com`, `www.microsoft.com`).
- Restore point options: optional `description`.
- Layout capture options: optional `name`.
- Clear audio route targets: `pid`, `process_name`, or `app` (same as other audio session skills).
- Delete layout targets: `layout_id` or `layout_name` (same as load layout).
- Service status keys: `spooler`, `wuauserv`, `bits`, `audio`/`audiosrv`, `dhcp`, `dnscache`, `themes`, `bluetooth`/`bthserv`, `defender`, `firewall`, `schedule`.
- Troubleshooter keys: `internet`, `network_adapter`, `audio`, `printer`, `bluetooth`, `windows_update`.
- Unexpected shutdown options: optional `hours` (1–168, default 72).
- Volume scan options: optional drive letter `volume` such as `C` or `C:`; defaults to the system drive.
