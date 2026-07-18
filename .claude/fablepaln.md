# PC Fix — Assistant Improvements & New Skills Plan

## Context

PC Fix is a Windows-only PySide6 desktop app with an embedded local LLM assistant (Llama 3.2 3B via llama-cpp-python). The assistant can only request predefined, validated skills — never arbitrary commands. The goal: make the assistant smarter/more reliable, fix residual safety and quality gaps, and add new tools/skills.

**Current state (verified):** The old roadmap (`.cursor/plans/ai_tools_roadmap_dc987c57.plan.md`) Phases 1–5 are **already committed** (b5091c7 / f353066, 2026-07-18): 60 skills registered, fail-closed validation, single-confirm ActionCards, Stop wired, JobQueue scopes `assistant-inference`/`assistant-actions`. Working tree clean; **124/124 tests pass**. The roadmap file still claims some of this is pending — it's stale.

Key files:
- `app/assistant_core.py` (~2700 lines) — `ASSISTANT_TOOLS` / `ASSISTANT_SKILLS` registries, validation, target resolution, `execute_assistant_action`
- `app/ai_engine.py` — `EmbeddedAI`, prompts, `render_skill_catalog` consumption, history trimming (n_ctx=4096, max_tokens=320)
- `app/assistant_tab.py` — Chat UI, `InferenceWorker`/`ActionWorker`
- `app/toolbox.py` — fixed named backend actions; `app/system_info.py` — read-only OS data
- `skills_list.md` — must stay in sync with `ASSISTANT_SKILLS` (hard invariant)

**Safety invariant to preserve throughout:** LLM emits only known skill names as fenced JSON → validated against `input_schema` → resolved against live snapshot → confirmation card for mutations → `execute_assistant_action` is the single execution point. No arbitrary shell/registry/file-delete surface. Add-a-skill = 6-step pattern in CLAUDE.md:73-81.

---

## Phase 0 — Baseline & hygiene (quick)

Baseline already verified: clean tree, 124/124 pass.

1. Manual smoke test of the app once: "why is my PC slow?" (small catalog), confirm-then-cancel a `clean_temp_files` card (must NOT show Confirmed), Stop mid-stream, double-submit (JobQueue rejection message).
2. Update `.cursor/plans/ai_tools_roadmap_dc987c57.plan.md` — mark Phases 1–5 complete so it stops claiming pending work.
3. Fix stale CLAUDE.md facts: `assistant_core.py` is ~2700 lines (says ~1700); mention JobQueue scopes `assistant-inference`/`assistant-actions`.

## Phase 1 — Close residual safety gaps (do before new features)

All in `app/assistant_core.py` unless noted:

1. **Host allowlist enforced too late** (`skill_request_to_action` lines 2202–2209): `check_dns_resolve`/`ping_host` accept any host at resolve time; the allowlist (`_DNS_PING_HOSTS`, toolbox.py:263) only rejects at execution — so a bad host becomes a plausible ActionCard that fails later. Fix: rename to public `DNS_PING_HOSTS` in `app/toolbox.py`, import in `assistant_core`, reject at resolve time with the allowed-hosts message. Clamp `count` to 1–4 at resolve time too.
2. **`_resolve_process` fail-open on unknown PID** (line 2388): a PID absent from the snapshot returns `{"pid": pid, "name": ""}` instead of rejecting. Tighten: reject PIDs not in `top_cpu_processes`/`top_memory_processes` with "Refresh top processes first" (matches the name-based branch at 2393).
3. **Domain-keyword false positive** (line 1103): `"windows"` in the layouts keywords makes "check windows updates" pull layout skills into the catalog. Drop bare `"windows"`; keep `"window"`, `"arrange"`, `"layout"`, `"desktop layout"`.

Tests (in `tests/test_assistant_core.py` / `test_assistant_toolbox_skills.py`): disallowed host rejected at resolve; count clamped; unknown-PID `end_process` rejected; "check windows updates" excludes layouts domain.

## Phase 2 — Assistant quality ("make the AI better"), ranked

Grounded in `ai_engine.py` + `render_skill_catalog` (assistant_core.py ~1250):

1. **Compact full-catalog mode.** Capability prompts ("what can you do") inject the full 60-skill catalog: 8,021 chars (~2.3k tokens) — presses against n_ctx=4096. In `render_skill_catalog`, when selection == full catalog, render name + short description only (keep the fenced-JSON instruction lines byte-identical). Better still: intercept capability questions in `AssistantTab._send_message_text` with a canned domain summary — no inference round-trip, deterministic.
2. **Dynamic few-shot example.** Catalog shows one static `scan_cleanup` example. Append one example using a *selected* target-based skill for the detected domain (e.g. audio intent → `set_app_volume` example). One line; big JSON-reliability win on a 3B model. Test: example skill is always in the selection.
3. **Keyword coverage for the 21 newer skills** in `SKILL_DOMAIN_KEYWORDS` — add triggers like "uptime", "frozen", "recycle bin", "signal", "gateway"; extend for Wave D/E skills as they land ("printer", "spooler", "bluetooth", "clock", "battery report").
4. **`repeat_penalty` passthrough** in `EmbeddedAI.query`/`stream_query` (default 1.1) — cheap guard against 3B repetition loops.
5. **Explicit non-changes:** keep n_ctx=4096 / max_tokens=320 (right envelope for 3B Q4 on CPU; catalog filtering makes bigger ctx unnecessary); history trimming already stores cleaned text and sane budgets; streaming JSON filter already covers split fenced blocks.

Verify: re-measure catalog sizes (full vs. "my pc is slow" vs. "what can you do") before/after; size assertions in `tests/test_ai_engine.py`.

## Phase 3 — Test backfill for landed-but-undertested behavior

- `tests/test_assistant_core.py`: `_resolve_allowlisted_scan_root` accepts Downloads subfolder / rejects `C:\Windows`; execution dispatch for all 21 newer kinds (`_execute_toolbox_action` → monkeypatched `toolbox.*`, assert call-through); `end_process` friendly-name resolution (single match / ambiguous).
- `tests/test_assistant_tab_skills.py`: `_follow_up_actions_for` returns cleanup follow-up only for cleanup kinds, nothing for e.g. `set_power_plan`.
- New `tests/test_chat_widgets_action_card.py` (offscreen Qt, follow existing patterns): `_confirm` leaves pending state (not "Confirmed"); `mark_cancelled` after pending; `mark_failed` shows result label.

## Phase 4 — New skills: Waves D & E ("add more tools and skills")

Each skill follows the 6-step pattern: `ASSISTANT_TOOLS` entry → `ASSISTANT_SKILLS` entry → `SKILL_DOMAINS`/`SKILL_DOMAIN_KEYWORDS` → resolve branch in `skill_request_to_action` → execute branch in `_execute_toolbox_action` (or audio/layout executor) → `skills_list.md` row + tests. Ship Wave D first (thin wrappers over existing backends), then Wave E (new fixed-command backends).

### Wave D — mostly existing backends

| Skill | Risk | Confirm | Backend |
|---|---|---|---|
| `list_installed_programs` | Read-only | No | `system_info.get_installed_programs` (exists) + thin `toolbox` ToolResult wrapper |
| `set_system_volume` | Low | Yes | New small fn in `audio_control` (mirrors `set_session_volume`, pycaw endpoint volume) |
| `mute_system_audio` | Low | Yes | Shares fn with `set_system_volume` |
| `delete_saved_layout` | Medium | Yes | `window_layouts.load_layouts`/`save_layouts` + ~10-line delete helper; resolve via existing `_resolve_layout` |
| `check_proxy_settings` | Read-only | No | New fixed-command toolbox fn: `netsh winhttp show proxy` |
| `check_bluetooth_status` | Read-only | No | New read-only toolbox fn: `Get-PnpDevice -Class Bluetooth` via existing `_run_json_powershell` |

### Wave E — new fixed-command backends (classic PC-fix value)

| Skill | Risk | Confirm | Fixed command |
|---|---|---|---|
| `check_component_store_health` | Read-only | No | `DISM /Online /Cleanup-Image /CheckHealth` |
| `run_sfc_scan` | Medium | Yes | `sfc /scannow` (long-running; honest `ToolResult(False,…)` on non-admin) |
| `restart_print_spooler` | Medium | Yes | One shared `toolbox.restart_allowlisted_service(key)` with a **frozen** map `{"spooler": "Spooler", "audiosvc": "Audiosrv"}` — never free-form service names |
| `restart_audio_service` | Medium | Yes | Shares the allowlisted-service helper |
| `resync_system_clock` | Low | Yes | `w32tm /resync` |
| `export_battery_report` | Read-only | No | `powercfg /batteryreport /output reports\…` (same dir as `export_pc_report`) |
| `run_defender_quick_scan` (stretch) | Low | Yes | `Start-MpScan -ScanType QuickScan` (fixed scan type) |
| `check_hosts_file` (stretch) | Read-only | No | Read `drivers\etc\hosts`, report non-comment entries |

**Excluded on purpose** (violates hard constraints or too risky): arbitrary service restart, Windows Update cache reset, registry-edit surfaces, drive defrag, kill-by-path.

Per-skill tests mirror `test_assistant_toolbox_skills.py`: catalog documentation, validation accept/reject, payload shape, execution dispatch (monkeypatched), plus rejection test for non-allowlisted service keys.

The only new execution surface is `restart_allowlisted_service` — keep its service map module-level frozen and covered by a rejection test.

## Phase 5 — Docs sync (inside each wave, not deferred)

- `skills_list.md`: new rows land in the same change as each wave.
- `CLAUDE.md` / `AGENTS.md`: update skill counts / line counts if referenced.
- Roadmap plan file: append Wave D/E section.

---

## Sequencing

**0 → 1 → 2.1/2.2 → 3 → 4 Wave D → 4 Wave E → 2.3/2.4 polish → 5** (docs inside each wave). Commit per phase/wave, full pytest green before each commit.

## Verification (every phase)

1. `.\venv\Scripts\python.exe -m py_compile <touched files>`
2. Focused pytest: `tests\test_assistant_core.py tests\test_assistant_toolbox_skills.py tests\test_assistant_tab_skills.py tests\test_ai_engine.py`
3. Full suite: `.\venv\Scripts\python.exe -m pytest` (baseline 124, grows each phase)
4. Manual chat smoke per wave: "my printer is stuck" → `restart_print_spooler` confirm card; "is my system clock wrong" → `resync_system_clock`; cancel any card → must never show "Confirmed".