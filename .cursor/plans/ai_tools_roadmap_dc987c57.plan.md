---
name: AI Assistant Roadmap
overview: Evidence-based AI Chat roadmap. Phase 1 helpers are partially landed in working tree but not wired into InferenceWorker yet; Phases 2–5 remain. Finish Phase 1 wiring first, then validation, Chat UX, ~20 skills, and assistant JobQueue.
todos:
  - id: phase-1-context
    content: "Phase 1: Finish wiring — pass user_text into catalog + history into stream_query; add/fix tests (helpers already in ai_engine/assistant_core)"
    status: in_progress
  - id: phase-2-validate
    content: "Phase 2: Fail-closed schema, scan path allowlists, adapter/startup/process resolve, gate keyword fallback, sync snapshot after tab refreshes"
    status: pending
  - id: phase-3-chat-ux
    content: "Phase 3: Single ActionCard confirm (fix Confirmed-on-cancel bug), richer cards, clearer status, wire Stop, smarter post-action follow-up"
    status: pending
  - id: phase-4-skills
    content: "Phase 4: Ship skill waves A→B→C (~20 skills) only after Phase 1 catalog is wired; update skills_list.md + tests"
    status: pending
  - id: phase-5-assistant-queue
    content: "Phase 5: JobQueue scopes for assistant-inference and assistant-actions only"
    status: pending
isProject: false
---

# AI Assistant Improvement Roadmap

**Focus:** AI Chat only — [`app/ai_engine.py`](app/ai_engine.py), [`app/assistant_core.py`](app/assistant_core.py), [`app/assistant_tab.py`](app/assistant_tab.py), [`app/chat_widgets.py`](app/chat_widgets.py), [`skills_list.md`](skills_list.md).

**Out of scope:** Health/Network/Cleanup tab polish, Reports history wiring, hardware/layouts JobQueue migration.

Safety invariant stays: LLM emits validated skill JSON only; Python resolves targets and confirms PC-changing actions. No arbitrary shell/PowerShell/Python execution.

---

## Current state (reviewed 2026-07-18)

### Baseline (committed / already shipped)

- Local Llama 3.2 3B Q4; Chat UI redesign shipped (`chat_widgets.py`, welcome prompts, context drawer, streaming).
- **39 skills / 39 tools**, all enabled; **15** confirm-gated. Toolbox Phase 1 mirrored; [`skills_list.md`](skills_list.md) matches.
- Safety pipeline: extract → validate → resolve → ActionCard → `execute_assistant_action`. Display/audio/layout `_single_match` works.
- Allowlists for settings pages, known folders, power plans, cleanup delete paths, startup toggles, protected processes.
- ~58 assistant-related tests for parse/validate/resolve/propose and prompt helpers.

### Working-tree progress (uncommitted, incomplete)

Modified: [`app/ai_engine.py`](app/ai_engine.py), [`app/assistant_core.py`](app/assistant_core.py).

| Item | Status | Evidence |
| --- | --- | --- |
| `n_ctx` → 4096 | **Done in engine** | `DEFAULT_N_CTX = 4096` |
| `max_tokens` → 320 | **Done in engine** | `DEFAULT_MAX_TOKENS = 320` |
| Tighter system prompt | **Done** | Prefer one skill; no invented targets; ask for refresh |
| Intent catalog helpers | **Done** | `CORE_SKILL_NAMES`, `SKILL_DOMAINS`, `select_skill_names_for_prompt`, `render_skill_catalog(user_text=)` |
| Catalog size when filtered | **Works offline** | Full ~5407 chars / 39 skills; “slow PC” ~1252 / 8; “wifi” ~1935 / 14 |
| Budgeted + native history | **Done in engine** | `MAX_HISTORY_CHARS=1200`; `format_chat_prompt(..., history=)` uses Llama headers; `compose_user_prompt` no longer embeds history text |
| Wire filtered catalog into Chat | **Not done** | `InferenceWorker` still calls `build_skill_catalog()` with **no** `user_text` |
| Wire history into generation | **Not done** | `stream_query(system, prompt)` called **without** `history=` |
| Phase 1 tests | **Not done** | Existing history tests still expect old “Recent conversation” shape |
| Phases 2–5 | **Not started** | Double confirm, fail-open schema, JobQueue bypass, 39 skills only, etc. |

### Gaps that still drive the roadmap

1. **Phase 1 not effective in Chat** until `InferenceWorker` passes `user_text` + `history`.
2. **Double confirm + card lie** — `ActionCard._confirm` marks Confirmed; `_run_action` may `QMessageBox`; Cancel leaves Confirmed.
3. **Fail-open schema** — unknown types/args accepted.
4. **`scan_large_files.root` unconstrained**.
5. **Tab refreshes stale assistant snapshot**.
6. **Keyword fallback always merges**.
7. **No adapter list / resolve** for `restart_network_adapter`.
8. **Stop unwired** (`stop_action = None`).
9. **Workers bypass JobQueue**.

```mermaid
flowchart LR
  P1[Phase1 FinishWire] --> P2[Phase2 Validation]
  P2 --> P3[Phase3 ChatUX]
  P3 --> P4[Phase4 Skills]
  P4 --> P5[Phase5 Queue]
```

**Gate:** Do not ship Phase 4 skill waves until Phase 1 is **wired and tested**. Helpers alone do not shrink Chat prompts.

---

## Phase 1 — Finish context fix (in progress)

**Goal:** Filtered catalog + native history actually used on every Chat turn.

Primary files: [`app/assistant_tab.py`](app/assistant_tab.py), [`app/ai_engine.py`](app/ai_engine.py), [`app/assistant_core.py`](app/assistant_core.py), [`tests/test_ai_engine.py`](tests/test_ai_engine.py), [`tests/test_assistant_tab_skills.py`](tests/test_assistant_tab_skills.py)

### Already implemented (keep; do not reinvent)

1. `DEFAULT_N_CTX = 4096`, `DEFAULT_MAX_TOKENS = 320`
2. Intent-filtered `render_skill_catalog(user_text=...)` / `select_skill_names_for_prompt`
3. `trim_chat_history` char budget + native Llama history in `format_chat_prompt`
4. Tightened `DEFAULT_SYSTEM_PROMPT`

### Remaining to close Phase 1

1. In `InferenceWorker.run`: `build_skill_catalog(user_text=self._display_text)` (or prompt text).
2. Pass `history=self._history` into `stream_query` / `query`.
3. Stop passing history into `compose_user_prompt` as if it were still inlined (or keep for compat but unused).
4. Update tests: catalog filter sizes; history via `format_chat_prompt`; drop/adjust “Recent conversation” expectations in `compose_user_prompt`.
5. Optional: status “Collecting snapshot” vs “Thinking” once Phase 3 lands (not required to close Phase 1).

**Done when:** Chat inference uses filtered catalog + native history; focused tests pass; measured catalog for “slow PC” stays ~8 skills / ~1.2k chars.

---

## Phase 2 — Fail-closed skills and better targeting

**Goal:** Bad skill JSON never becomes a misleading ActionCard.

Primary files: [`app/assistant_core.py`](app/assistant_core.py), [`app/assistant_tab.py`](app/assistant_tab.py)

1. Fail-closed `_value_matches_schema` / `validate_skill_request` — reject unknown args and unknown schema types.
2. Allowlist `root` for `scan_large_files` / storage scan skills.
3. `_resolve_adapter`, `_resolve_startup_item`, friendly `end_process` (name → PID); adapter names in snapshot when relevant.
4. Gate keyword fallback: merge `propose_actions` only when LLM emitted zero valid skills (or high-confidence matches only).
5. After tab `refresh_displays` / `refresh_audio` / `refresh_layouts`, also refresh `_current_snapshot`.

**Done when:** Unit tests cover reject-unknown-args, path allowlist, new resolvers, fallback gating, snapshot sync.

---

## Phase 3 — Chat assistant UX fixes

**Goal:** Confirm/result UX matches the safety story.

Primary files: [`app/assistant_tab.py`](app/assistant_tab.py), [`app/chat_widgets.py`](app/chat_widgets.py)

1. Single confirm path — ActionCard only; remove second `QMessageBox`. Do not mark Confirmed until confirmed (fix cancel lie).
2. Richer cards: target, risk, “what will happen”; attach compact result on the card after run.
3. Clear status states: loading model / collecting snapshot / streaming / waiting for confirm / action running.
4. Wire Stop to `_stop_inference` (e.g. dock/header button → `self.stop_action`).
5. Smarter follow-up — stop always proposing cleanup after every success.

**Done when:** Mutating skills confirm once; cancel doesn’t mark Confirmed; Stop works; follow-up isn’t always cleanup.

---

## Phase 4 — Expand skills (~20), waves A→B→C

**Goal:** Grow Chat by wrapping existing backends. Update [`skills_list.md`](skills_list.md) in every skill change. Extend `SKILL_DOMAINS` for each new skill so Phase 1 filtering stays effective.

### Wave A — Cleanup & storage

| Skill | Confirm | Backend |
| --- | --- | --- |
| `get_recycle_bin_size` | No | `_recycle_bin_size` |
| `empty_recycle_bin` | Yes | Allowlisted Recycle Bin |
| `clean_temp_files` | Yes | Existing temp categories |
| `clean_browser_cache` | Yes | Browser-cache categories |
| `clean_thumbnail_cache` | Yes | Thumbnail category |
| `scan_downloads_large_files` | No | Downloads root |
| `scan_desktop_large_files` | No | Desktop root |

### Wave B — Network triage

| Skill | Confirm | Notes |
| --- | --- | --- |
| `list_network_adapters` | No | Feeds adapter resolve |
| `check_dns_resolve` | No | Host allowlist |
| `ping_host` | No | Host allowlist + count cap |
| `check_default_gateway` | No | No-internet triage |
| `show_wifi_status` | No | SSID/signal; never passwords |

### Wave C — System helpers & openers

| Skill | Confirm | Notes |
| --- | --- | --- |
| `check_system_uptime` | No | `boot_time` from hardware |
| `check_memory_pressure` | No | RAM/commit signals |
| `list_installed_gpus` | No | Hardware summary |
| `open_task_manager` / `open_resource_monitor` / `open_device_manager` | No | Fixed launchers |
| Expand settings/folders allowlists | No | `storage`/`power`/… and `desktop`/`documents`/`pictures` |
| `capture_layout_snapshot` | Yes | Existing layouts capture |
| `set_default_audio_device` | Yes | New fixed audio path |

**Still out of scope:** arbitrary kill-by-path, registry editors, unrestricted deletion, cloud LLM, Wi‑Fi passwords, “run this PowerShell/Python”.

---

## Phase 5 — Assistant JobQueue only

1. Scopes: `assistant-inference`, `assistant-actions` via `get_job_queue().submit`.
2. Overlap → clear Chat status (“already running”).
3. Do not migrate hardware/layouts/cleanup tabs here.

---

## Sequencing

| Phase | Focus | Status | Next action |
| --- | --- | --- | --- |
| 1 | Context + catalog + history | **~70% helpers; 0% Chat wiring** | Wire `InferenceWorker` + fix tests |
| 2 | Validation + resolution | Not started | After Phase 1 green |
| 3 | Chat UX | Not started | Can lightly parallel Phase 2 |
| 4 | Skills A→B→C | Not started | Requires Phase 1 wired |
| 5 | Assistant JobQueue | Not started | After Phase 3 preferred |

Recommended ship order: **finish 1 → 2 → 3 → 4A → 4B → 4C → 5**.

---

## Testing strategy

- Focused: `tests/test_ai_engine.py`, `tests/test_assistant_core.py`, `tests/test_assistant_toolbox_skills.py`, `tests/test_assistant_tab_skills.py`
- Phase 1 priorities now: catalog filter by intent; `format_chat_prompt` history headers; InferenceWorker uses filtered catalog
- Later: reject-unknown-args, path allowlist, ActionCard-only confirm, fallback gating, new skill waves
- `py_compile` touched modules; full `pytest` before merging a phase
- Manual smoke after Phase 1 wire: “why is my PC slow?” should not inject the full 39-skill catalog
