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
