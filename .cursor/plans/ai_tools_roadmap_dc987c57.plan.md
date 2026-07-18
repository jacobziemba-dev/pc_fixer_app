---
name: AI Assistant Roadmap
overview: A phased roadmap focused on the AI Chat assistant — better prompts/context, stricter skill handling, Chat UX, and a large expansion of assistant skills (~20 new fixed/validated skills) — without a broad toolbox/tab overhaul.
todos:
  - id: phase-1-context
    content: "Phase 1: Raise n_ctx, intent-filter skill catalog, native history budget, tighter system prompt"
    status: pending
  - id: phase-2-validate
    content: "Phase 2: Fail-closed schema validation, path allowlists, stronger target resolution, gate keyword fallback, sync assistant snapshot after tab refreshes"
    status: pending
  - id: phase-3-chat-ux
    content: "Phase 3: Single ActionCard confirm, richer cards with resolved targets + result summaries, clearer streaming/status feedback"
    status: pending
  - id: phase-4-skills
    content: "Phase 4: Ship expanded assistant skill set across cleanup, network, diagnostics, and allowlisted openers; update skills_list.md + tests"
    status: pending
  - id: phase-5-assistant-queue
    content: "Phase 5: JobQueue scopes for assistant inference and actions only"
    status: pending
isProject: false
---

# AI Assistant Improvement Roadmap

**Focus:** the AI Chat assistant only — [`app/ai_engine.py`](app/ai_engine.py), [`app/assistant_core.py`](app/assistant_core.py), [`app/assistant_tab.py`](app/assistant_tab.py), [`skills_list.md`](skills_list.md), and assistant tests.

**In scope:** A (reliability) + B (new assistant skills) + C (Chat UX).

**Out of scope for this roadmap:** Health/Network/Cleanup tab polish, shared tab confirm helpers, Reports/`tool_history` cleanup wiring, hardware/layouts JobQueue migration, Cleanup scope splits. Those stay backlog items outside this plan.

Safety invariant stays: LLM only emits validated skill JSON; Python resolves targets and confirms PC-changing actions. No arbitrary shell/PowerShell/Python execution.

```mermaid
flowchart LR
  P1[Phase1 Context] --> P2[Phase2 Validation]
  P2 --> P3[Phase3 ChatUX]
  P3 --> P4[Phase4 Skills]
  P4 --> P5[Phase5 AssistantQueue]
```

---

## Phase 1 — Make the assistant fit the context window

**Goal:** Fewer truncated/confused answers; skill requests stay grounded in the live snapshot.

Primary files: [`app/ai_engine.py`](app/ai_engine.py), [`app/assistant_core.py`](app/assistant_core.py)

1. **Raise and budget context** — Increase `EmbeddedAI.n_ctx` from `2048` to `4096` (or the highest value that still loads reliably on the 3B Q4 model), keep `max_tokens` modest (~256–384), and trim history more aggressively when the prompt is large.
2. **Intent-filtered skill catalog** — Replace always-on `render_skill_catalog()` in `compose_user_prompt` with a compact catalog: always include a short “core” set (health/process/cleanup/export), plus domain skills matched to the user question (network, display, audio, layouts, startup, storage). Keep the full catalog for explicit “what can you do?” prompts.
3. **Native multi-turn history** — Stop stuffing `User:`/`Assistant:` text into one user blob; format prior turns with Llama 3.2 chat headers (or a tight history section with a hard char budget) so continuity doesn’t burn the whole window.
4. **Tighten system prompt** — Update `DEFAULT_SYSTEM_PROMPT` to: prefer 1 skill request unless the user asked for a multi-step plan; refuse invented targets; say “I need a refresh first” when snapshot data is missing.

**Done when:** Prompt composition tests show catalog + snapshot + 4 history turns fit with generation headroom; focused `tests/test_ai_engine.py` coverage for catalog filtering and history budget.

---

## Phase 2 — Stricter skill validation and target resolution

**Goal:** Wrong or unsafe skill JSON fails closed in Python before Chat shows a card.

Primary files: [`app/assistant_core.py`](app/assistant_core.py), [`app/assistant_tab.py`](app/assistant_tab.py), [`tests/test_assistant_core.py`](tests/test_assistant_core.py), [`tests/test_assistant_toolbox_skills.py`](tests/test_assistant_toolbox_skills.py)

1. **Fail-closed schema checks** — In `validate_skill_request` / `_value_matches_schema`: reject unknown args, reject unknown schema types, require required fields.
2. **Path allowlisting for scan skills** — For `scan_large_files` / `scan_folder_sizes` / `scan_duplicate_files`, resolve `root` to an allowlisted set (home, Downloads, Desktop, Documents, temp, or currently scanned cleanup roots) — never pass arbitrary LLM paths through.
3. **Snapshot-based resolution for weak targets** — Add `_resolve_adapter`, `_resolve_startup_item`, and friendly `end_process` resolution (name/PID from top processes) using the same `_single_match` pattern as display/audio/layout.
4. **Tone down keyword fallback** — Gate `propose_actions` so it only adds cards when the LLM emitted zero valid skills, or when matches are high-confidence; stop flooding Chat with duplicate keyword cards (`InferenceWorker`).
5. **Keep assistant snapshot in sync after refreshes** — When `refresh_displays` / `refresh_audio` / `refresh_layouts` run via `action_requested`, also refresh the assistant snapshot (or call `execute_assistant_action`) so the next turn sees new data.

**Done when:** Unit tests cover reject-unknown-args, path allowlist, adapter/startup/process resolution, and fallback gating.

---

## Phase 3 — Chat assistant UX

**Goal:** Confirmation and skill results in Chat feel intentional and trustworthy.

Primary files: [`app/assistant_tab.py`](app/assistant_tab.py), [`app/chat_widgets.py`](app/chat_widgets.py)

1. **Single confirmation path** — Keep `ActionCard` as the only confirm UI for assistant skills; remove the second `QMessageBox` for the same action in `_run_action`.
2. **Richer action cards** — Show resolved target, risk, and a one-line “what will happen” before confirm; after run, attach a compact result summary on the card (success/errors), not only a status label.
3. **Clearer streaming/status feedback** — Distinct states for loading model, collecting snapshot, thinking/streaming, waiting for confirm, and action running/done — so users know whether the assistant is stuck or waiting on them.
4. **Post-action follow-up quality** — After a skill completes, briefly restate what changed using the action result (not a second full inference unless useful), and offer at most one sensible next skill card when appropriate.

**Done when:** Mutating skills confirm once via ActionCard; cards show target + outcome; Chat status states are unambiguous.

---

## Phase 4 — Expand the assistant skill catalog

**Goal:** Materially grow what Chat can request through named, validated, confirm-gated skills. Every skill gets `ASSISTANT_SKILLS` / `ASSISTANT_TOOLS`, validate/execute wiring, tests, and a [`skills_list.md`](skills_list.md) row in the same change.

Primary files: [`app/assistant_core.py`](app/assistant_core.py), [`app/toolbox.py`](app/toolbox.py) (fixed backends only), [`app/system_info.py`](app/system_info.py) when reuse is cleaner, [`skills_list.md`](skills_list.md)

Ship in three waves so Phase 1 catalog filtering can absorb them.

### Wave A — Cleanup & storage (Chat’s most common asks)

| Skill | Confirm | Notes |
| --- | --- | --- |
| `empty_recycle_bin` | Yes | Allowlisted Recycle Bin only |
| `clean_temp_files` | Yes | Uses existing temp cleanup category / scanned candidates only |
| `clean_browser_cache` | Yes | Existing browser-cache cleanup categories only |
| `clean_thumbnail_cache` | Yes | Existing thumbnail category only |
| `get_recycle_bin_size` | No | Read-only size report (reuse `_recycle_bin_size`) |
| `scan_downloads_large_files` | No | Convenience wrapper: large-file scan rooted at Downloads |
| `scan_desktop_large_files` | No | Same for Desktop |

### Wave B — Network diagnostics (better triage before mutate)

| Skill | Confirm | Notes |
| --- | --- | --- |
| `list_network_adapters` | No | Names/status for better `restart_network_adapter` targeting |
| `check_dns_resolve` | No | Fixed host allowlist only (`one.one.one.one`, `dns.google`, etc.) |
| `ping_host` | No | Fixed host allowlist + count cap; no arbitrary hosts |
| `check_default_gateway` | No | Read gateway/route summary for “no internet” triage |
| `show_wifi_status` | No | Connected SSID / signal if available; no password access |

### Wave C — System helpers & allowlisted openers

| Skill | Confirm | Notes |
| --- | --- | --- |
| `open_task_manager` | No | Fixed launcher only |
| `open_resource_monitor` | No | Fixed launcher only |
| `open_device_manager` | No | Fixed launcher only |
| `expand open_windows_settings` | No | Add allowlisted pages: `storage`, `power`, `privacy`, `troubleshoot`, `about` |
| `expand open_known_folder` | No | Add allowlisted: `desktop`, `documents`, `pictures` |
| `check_system_uptime` | No | Boot time / uptime for slow-PC advice |
| `check_memory_pressure` | No | Compact RAM + commit/pagefile signals beyond snapshot % |
| `list_installed_gpus` | No | From hardware summary; helps display/performance advice |
| `check_smart_status` | No | Thin wrapper/clarification around disk health if not already clear enough in Chat |
| `capture_layout_snapshot` | Yes | Save current window layout (uses existing layouts backend) |
| `set_default_audio_device` | Yes | Resolve playback device from snapshot; confirm before switch |

### Implementation rules for new skills

- Prefer wrapping existing `toolbox` / `system_info` / `audio_control` / `window_layouts` paths over new OS surfaces.
- Mutating skills always `requires_confirmation=True`.
- Hosts, folders, settings pages, and cleanup categories stay allowlisted in Python — never free-form from the model.
- Intent-filtered catalog (Phase 1) must map these into domains (`cleanup`, `network`, `system`, `audio`, `layouts`) so the 3B context doesn’t explode.
- Tab UI buttons for the same actions are optional and not required in this phase.

**Still out of scope:** arbitrary process kill by path, registry editors, unrestricted deletion, remote/cloud LLM, Wi‑Fi password reading, or “run this PowerShell/Python” skills.

**Done when:** Waves A–C are in the catalog with validate/execute paths, focused tests, and updated `skills_list.md`.

---

## Phase 5 — Assistant runtime queue only

**Goal:** Serialize assistant work without redesigning every tab’s JobQueue usage.

Primary files: [`app/assistant_tab.py`](app/assistant_tab.py), [`app/job_queue.py`](app/job_queue.py)

1. Route inference through JobQueue scope `assistant-inference`.
2. Route skill/action execution through JobQueue scope `assistant-actions`.
3. Reject overlapping submits in those scopes with clear Chat status (“already running”).
4. Do **not** migrate hardware/layouts/cleanup tabs in this roadmap.

**Done when:** Assistant inference and actions go through `get_job_queue().submit`; overlapping assistant work is rejected cleanly.

---

## Suggested sequencing and effort

| Phase | Focus | Rough effort |
| --- | --- | --- |
| 1 | Context + catalog + history | ~2–3 days |
| 2 | Validation + resolution | ~3–4 days |
| 3 | Chat UX | ~2–3 days |
| 4 | Expanded skill waves A–C (~20 skills) | ~5–7 days |
| 5 | Assistant JobQueue | ~1–2 days |

Start with Phase 1+2 before Phase 4 — new skills make a weak catalog/validator worse. Prefer shipping Wave A, then B, then C so Chat gains cleanup/network value first.

---

## Testing strategy (every phase)

- Focused: `tests/test_ai_engine.py`, `tests/test_assistant_core.py`, `tests/test_assistant_toolbox_skills.py`, `tests/test_assistant_tab_skills.py`
- Compile-check touched assistant modules with `py_compile`
- Full `pytest` before merging a phase
- Manual smoke in AI Chat: “why is my PC slow?”, confirm one mutating skill once, verify next-turn snapshot awareness, check status labels through the full turn
