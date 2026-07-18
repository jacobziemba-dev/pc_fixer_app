# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

PC Fix is a Windows-only PySide6 desktop app for PC diagnostics, cleanup, and AI-assisted toolbox workflows. It includes an embedded local LLM (llama.cpp via `llama-cpp-python`, running a GGUF model from `models/`) that acts as an in-app assistant able to request predefined, validated "skills" — never arbitrary shell/PowerShell/Python execution.

## Build, Test, and Development Commands

Set up the virtual environment (already present as `venv/` in this checkout):

```powershell
python -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt
```

Run the app:

```powershell
.\venv\Scripts\python.exe main.py
```

Or on Windows: `run.bat` (launches `main.py` via `venv\Scripts\python.exe`).

Run tests:

```powershell
# Full suite (before a commit, release, or risky cross-cutting change)
.\venv\Scripts\python.exe -m pytest

# Focused tests during development
.\venv\Scripts\python.exe -m pytest tests\test_job_queue.py tests\test_toolbox.py

# Single test
.\venv\Scripts\python.exe -m pytest tests\test_toolbox.py::test_name -v

# Lightweight compile check for touched files (fast sanity check)
.\venv\Scripts\python.exe -m py_compile app\some_file.py
```

There is no build step for development. Packaging uses PyInstaller via `PC Fix.spec` (outputs land in `build/` and `dist/`); these directories and `venv/` should not be edited by hand.

## Architecture

### Entry point and tab loading

`main.py` defines `MainWindow`, which wires together a sidebar/top-nav and a `QStackedWidget` of tabs. Only the Dashboard tab is constructed eagerly; every other tab is a placeholder widget until first visited, at which point `_LAZY_TABS` (module name, class name, title) is used to import and swap in the real tab (`_ensure_tab_loaded` / `_load_tab`). Keep this lazy pattern when adding new tabs — don't import heavy tab modules at module load time in `main.py`.

Tabs that emit `action_requested(kind, payload)` get auto-connected to `MainWindow._on_assistant_action_requested`, which is how the AI assistant tab triggers cross-tab effects (e.g. asking the Display tab to refresh after a resolution change).

### Central modules (`app/`)

- **`app/system_info.py`** — all raw OS/process/disk/startup/cleanup data access (psutil, WMI/PowerShell calls, etc.). This is the only place that should reach into the OS for read-only data.
- **`app/toolbox.py`** — conservative, named PC helper actions (health checks, network checks, power-plan changes, cleanup scans, report export). Every action is a fixed Python function, not arbitrary command execution. **Do not add an arbitrary shell/PowerShell/Python execution surface here.**
- **`app/assistant_core.py`** (~2700 lines, the largest module) — the assistant's brain:
  - `ASSISTANT_TOOLS` / `ASSISTANT_SKILLS`: the fixed catalog of things the LLM is allowed to request.
  - Snapshot collection (`collect_assistant_snapshot`, `AssistantSnapshot`) — builds the structured PC-state context sent to the model.
  - Skill request parsing/validation (`extract_skill_requests`, `validate_skill_request`, `skill_request_to_action`) — turns model-emitted JSON into an `AssistantAction`, resolving fuzzy targets (display, audio device/session, layout) against the live snapshot.
  - `execute_assistant_action` — the single place that actually performs a skill's effect, dispatching to `toolbox`, `audio_control`, or `window_layouts`.
- **`app/ai_engine.py`** — wraps `llama-cpp-python` (`EmbeddedAI`), chat prompt formatting (Llama 3.2 Instruct template), history trimming, and prompt composition (snapshot context + skill catalog + history + question). Model file resolution defaults to `models/llama-3.2-3b-instruct-q4_k_m.gguf`.
- **`app/job_queue.py`** — a single global `JobQueue` (via `get_job_queue()`) that serializes QThread-based background workers by a string `scope`, rejecting a submission if that scope is already running/queued. This is the only mechanism for running scans/actions off the UI thread. The AI Chat tab uses scopes `assistant-inference` (model streaming) and `assistant-actions` (skill execution).
- **`app/tool_history.py`** — recent toolbox results for the Reports tab.
- **`app/theme.py`** — shared Qt stylesheet (`DARK_STYLESHEET`) applied app-wide.
- **`app/audio_control.py`** / **`app/window_layouts.py`** — audio session control (pycaw) and window layout capture/restore, called from `assistant_core.execute_assistant_action` and from their respective tabs.
- **`app/scripts/hardware_info.ps1`** — PowerShell script used for hardware discovery, invoked from `system_info.py`.

### Tab modules

Each `app/*_tab.py` (e.g. `dashboard_tab.py`, `health_tab.py`, `cleanup_tab.py`, `network_tab.py`, `display_tab.py`, `audio_tab.py`, `layouts_tab.py`, `startup_tab.py`, `hardware_tab.py`, `reports_tab.py`) is a self-contained `QWidget` for one feature area, built with widgets from `toolbox_widgets.py` / `chat_widgets.py` and styled via `theme.py`. `assistant_tab.py` is the AI Chat tab and is the main consumer of `ai_engine.py` and `assistant_core.py`.

### The skill/action safety model

This is the most important architectural invariant in the codebase:

1. The LLM only ever sees a rendered skill catalog (`render_skill_catalog`) and can only respond with fenced JSON skill requests matching known skill names.
2. Every skill request is validated against `input_schema` and resolved against the current snapshot in Python (`validate_skill_request`, `skill_request_to_action`) — the model cannot supply a raw command, path, or arbitrary target.
3. Any action with `requires_confirmation=True` must render as a confirmation card the user approves before `execute_assistant_action` runs it.
4. `skills_list.md` is the authoritative, human-readable mirror of `ASSISTANT_SKILLS` in `app/assistant_core.py` — **update it in the same change** whenever skills are added, removed, renamed, disabled, or have behavior changes.

When adding a new skill: add it to `ASSISTANT_SKILLS`/`ASSISTANT_TOOLS`, add resolution/execution logic following the existing target-resolution pattern (`_resolve_display`, `_resolve_audio_session`, etc.), wire it into `execute_assistant_action`, and update `skills_list.md`.

## Coding Conventions

- Python 3, 4-space indentation, `PascalCase` classes, `snake_case` functions/variables, `UPPER_SNAKE_CASE` constants. Tab classes stay feature-named (e.g. `CleanupTab`).
- Never block the UI thread: slower scans/actions run in `QThread` workers submitted through `JobQueue` (`app/job_queue.py`), not started directly. Use a stable scope name (`cleanup`, `display`, `network-tools`, `reports-tools`, etc.) so duplicate work is rejected. Wire UI state through the `on_started` / `on_result` / `on_finished` / `on_rejected` callbacks — don't build a second synchronization/job framework.
- System-changing operations (toolbox actions, assistant skills) must use a fixed, named code path, validate targets in Python, and require user confirmation. No arbitrary shell commands, arbitrary PowerShell, arbitrary Python execution, registry-edit surfaces, or unrestricted file deletion — this is a hard constraint, not a style preference.
- Keep local venvs, caches, `reports/`, downloaded models, and generated build/dist output out of version control; update `.gitignore` in the same change if a new feature creates local artifacts.

## Testing Guidelines

Tests live in `tests/`, named `test_<module>.py`, using `pytest`. Prioritize pure/logic-heavy code: byte formatting, cleanup target selection, parsing, registry-data normalization, toolbox result handling, assistant skill conversion, and job-queue synchronization. Keep UI-behavior tests focused on logic that doesn't require manual window interaction.
