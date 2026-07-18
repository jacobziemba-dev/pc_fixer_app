---
name: AI Tools Roadmap
overview: A phased roadmap to make PC Fix’s local AI more reliable, expand high-value skills/toolbox actions, and improve Chat + tool UX — without breaking the fixed-skill safety model.
todos:
  - id: phase-1-context
    content: "Phase 1: Raise n_ctx, intent-filter skill catalog, native history budget, tighter system prompt"
    status: pending
  - id: phase-2-validate
    content: "Phase 2: Fail-closed schema validation, path allowlists, stronger target resolution, gate keyword fallback, sync tab refreshes"
    status: pending
  - id: phase-3-ux
    content: "Phase 3: Single Chat confirm, richer action cards, better result truncation, event-log success semantics, tool_history for cleanup"
    status: pending
  - id: phase-4-skills
    content: "Phase 4: Add high-value skills (recycle bin, adapters, DNS, settings) + Cleanup/Health UI affordances; update skills_list.md"
    status: pending
  - id: phase-5-jobqueue
    content: "Phase 5: JobQueue for assistant actions/hardware/layouts; split cleanup scopes"
    status: pending
isProject: false
---

# AI + Tools Improvement Roadmap

Scope: **A (AI reliability) + B (new skills/actions) + C (Chat/tool UX)** as a phased backlog. Safety invariant stays: LLM only emits validated skill JSON; Python resolves targets and confirms PC-changing actions. No arbitrary shell/PowerShell/Python execution.

```mermaid
flowchart LR
  P1[Phase1 Context] --> P2[Phase2 Validation]
  P2 --> P3[Phase3 UX]
  P3 --> P4[Phase4 NewSkills]
  P4 --> P5[Phase5 Reliability]
```

---

## Phase 1 — Make the AI actually fit the context window

**Goal:** Fewer truncated/confused answers; skill requests stay grounded in the live snapshot.

Primary files: [`app/ai_engine.py`](app/ai_engine.py), [`app/assistant_core.py`](app/assistant_core.py)

1. **Raise and budget context** — Increase `EmbeddedAI.n_ctx` from `2048` to `4096` (or the highest value that still loads reliably on this 3B Q4 model), keep `max_tokens` modest (~256–384), and trim history more aggressively when the prompt is large.
2. **Intent-filtered skill catalog** — Replace always-on `render_skill_catalog()` in `compose_user_prompt` with a compact catalog: always include a short “core” set (health/process/cleanup/export), plus domain skills matched to the user question (network, display, audio, layouts, startup, storage). Keep full catalog available for explicit “what can you do?” prompts.
3. **Native multi-turn history** — Stop stuffing `User:`/`Assistant:` text into one user blob; format prior turns with Llama 3.2 chat headers (or a tight history section with hard char budget) so continuity doesn’t burn the whole window.
4. **Tighten system prompt** — Update `DEFAULT_SYSTEM_PROMPT` to: prefer 1 skill request unless the user asked for a multi-step plan; refuse invented targets; say “I need a refresh first” when snapshot data is missing.

**Done when:** Prompt composition tests show catalog + snapshot + 4 history turns fit with generation headroom; focused `tests/test_ai_engine.py` coverage for catalog filtering and history budget.

---

## Phase 2 — Stricter skill validation and target resolution

**Goal:** Wrong or unsafe skill JSON fails closed in Python.

Primary files: [`app/assistant_core.py`](app/assistant_core.py), [`tests/test_assistant_core.py`](tests/test_assistant_core.py), [`tests/test_assistant_toolbox_skills.py`](tests/test_assistant_toolbox_skills.py)

1. **Fail-closed schema checks** — In `validate_skill_request` / `_value_matches_schema`: reject unknown args, reject unknown schema types, require required fields.
2. **Path allowlisting for scans** — For `scan_large_files` / `scan_folder_sizes` / `scan_duplicate_files`, resolve `root` to an allowlisted set (home, Downloads, Desktop, Documents, temp, or currently scanned cleanup roots) — never pass arbitrary LLM paths through.
3. **Snapshot-based resolution for weak targets** — Add `_resolve_adapter`, `_resolve_startup_item`, and friendly `end_process` resolution (name/PID from top processes) using the same `_single_match` pattern as display/audio/layout.
4. **Tone down keyword fallback** — Gate `propose_actions` so it only adds cards when the LLM emitted zero valid skills, or when matches are high-confidence; stop flooding the chat with duplicate keyword cards ([`app/assistant_tab.py`](app/assistant_tab.py) `InferenceWorker`).
5. **Sync tab refreshes into assistant state** — When `refresh_displays` / `refresh_audio` / `refresh_layouts` run via `action_requested`, also refresh the assistant snapshot (or call `execute_assistant_action`) so the next turn sees new data.

**Done when:** New unit tests cover reject-unknown-args, path allowlist, adapter/startup/process resolution, and fallback gating.

---

## Phase 3 — Chat + tool UX that matches the product story

**Goal:** Confirmation and results feel intentional; history is trustworthy.

Primary files: [`app/assistant_tab.py`](app/assistant_tab.py), [`app/toolbox_widgets.py`](app/toolbox_widgets.py), [`app/chat_widgets.py`](app/chat_widgets.py), tab modules using `ToolRunner`

1. **Single confirmation path in Chat** — Keep `ActionCard` as the only confirm UI for assistant skills; remove the second `QMessageBox` for the same action in `_run_action`.
2. **Richer action cards** — Show resolved target, risk, and a one-line “what will happen”; after run, attach a compact `ToolResult` summary on the card (success/errors), not only a status toast.
3. **Better tool result bodies** — Raise/paginate the 12-line truncate in `result_text`; for large/folder/duplicate scans, show top N + “N more…” and keep full details in history/export.
4. **Fix false-failure scans** — Treat `scan_event_log_errors` findings as `success=True` with a warning-style summary so Reports/history don’t mark a good scan as failed.
5. **Shared confirm helper for tabs** — Small `confirm_action(parent, title, text)` used by Health/Network/Dashboard/Startup/Cleanup to cut duplicated `QMessageBox` blocks (behavior unchanged: default No).
6. **Wire cleanup delete into `tool_history`** — Junk clean completion should appear in Reports like toolbox runs.

**Done when:** Assistant mutating skills confirm once; scan results readable; cleanup actions visible in Reports history.

---

## Phase 4 — High-value new skills and toolbox actions

**Goal:** Expand capability only through named, validated, confirm-gated paths. Update [`skills_list.md`](skills_list.md) in the same change for every skill touch.

Primary files: [`app/toolbox.py`](app/toolbox.py), [`app/assistant_core.py`](app/assistant_core.py), [`app/system_info.py`](app/system_info.py), Health/Network/Cleanup tabs

Ship these first (highest user value, still conservative):

| Skill / action | Why | Confirmation |
| --- | --- | --- |
| `empty_recycle_bin` | Common cleanup ask; allowlisted only | Yes |
| `clear_temp_files` (or category-scoped clean without full scan UI) | Bridge Chat → safe temp clean using existing cleanup categories | Yes |
| `list_network_adapters` | Feeds better `restart_network_adapter` resolution | No |
| `check_dns_resolve` (fixed host allowlist, e.g. `one.one.one.one`) | Actionable network triage beyond ping | No |
| `open_task_manager` / expand `open_windows_settings` pages | Fast handoff when AI can’t safely act | No (allowlisted) |
| `suggest_startup_disable` → still requires `set_startup_item_enabled` confirm | Better AI guidance without auto-disable | Review skill is read-only; disable stays confirmed |

UI affordances for existing APIs in the same phase:
- Cleanup large-file scan: root + min-size controls (defaults stay home / current min).
- Health `review_startup_impact`: deep-link / “Open Startup tab” affordance after results.

**Out of scope for this roadmap:** arbitrary process kill by path, registry editors, unrestricted deletion, remote/cloud LLM, or “run this PowerShell” skills.

**Done when:** Each new action has toolbox function + skill entry + tests + `skills_list.md` row + tab button where it belongs.

---

## Phase 5 — Runtime reliability (JobQueue + scopes)

**Goal:** Align AI/tools with the existing background-work contract in [`app/job_queue.py`](app/job_queue.py).

1. Route assistant action execution through JobQueue scope `assistant-actions` (inference can stay on its own scope `assistant-inference` so chat doesn’t block toolbox forever, but two assistant actions cannot overlap).
2. Migrate [`app/hardware_tab.py`](app/hardware_tab.py) and [`app/layouts_tab.py`](app/layouts_tab.py) workers to JobQueue scopes `hardware` / `layouts`.
3. Split Cleanup scopes: `cleanup-junk` vs `cleanup-storage` so storage scans don’t block junk scan/delete.
4. Keep audio on the UI thread (COM STA) — document only, no JobQueue change.

**Done when:** No new direct `.start()` for assistant actions / hardware / layouts; focused `tests/test_job_queue.py` coverage for new scopes if needed.

---

## Suggested sequencing and effort

| Phase | Focus | Rough effort |
| --- | --- | --- |
| 1 | Context + catalog + history | ~2–3 days |
| 2 | Validation + resolution | ~3–4 days |
| 3 | Chat/tool UX | ~3–4 days |
| 4 | New skills + tab affordances | ~4–5 days |
| 5 | JobQueue hardening | ~2–3 days |

Start with Phase 1+2 before adding many Phase 4 skills — new skills make a weak catalog/validator worse.

---

## Testing strategy (every phase)

- Focused: `tests/test_ai_engine.py`, `tests/test_assistant_core.py`, `tests/test_assistant_toolbox_skills.py`, `tests/test_assistant_tab_skills.py`, `tests/test_toolbox.py`, `tests/test_job_queue.py`
- Compile-check touched modules with `py_compile`
- Full `pytest` before merging a phase branch
- Manual smoke: Chat “why is my PC slow?”, confirm one mutating skill once, run a large-file scan, check Reports history
