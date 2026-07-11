# Repository Guidelines

## Project Structure & Module Organization

This repository contains a Windows-focused Python desktop app for PC diagnostics, cleanup, and AI-assisted PC toolbox workflows.

- `main.py` is the PySide6 application entry point and wires the main tabs together.
- `app/` contains UI modules and shared logic. Tab files follow the feature they render: `dashboard_tab.py`, `hardware_tab.py`, `startup_tab.py`, and `cleanup_tab.py`.
- `app/system_info.py` centralizes OS, process, disk, startup, and cleanup data access.
- `app/toolbox.py` contains named, conservative PC helper actions such as health checks, network checks, power-plan helpers, large-file scans, and report export. Do not add arbitrary shell execution surfaces.
- `app/job_queue.py` owns centralized background job scheduling for QThread-based work. Use it for scans/actions that should not run twice or overlap unsafely.
- `app/tool_history.py` stores recent toolbox results for reports/history views.
- `app/theme.py` contains shared Qt stylesheet definitions.
- `app/scripts/hardware_info.ps1` supports Windows hardware discovery.
- `requirements.txt` lists runtime and test dependencies (including `pytest`).
- `tests/` holds automated tests (`test_*.py`).

## Build, Test, and Development Commands

Create and populate a virtual environment before running the app:

```powershell
python -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt
```

Run locally with:

```powershell
.\venv\Scripts\python.exe main.py
```

On Windows, `run.bat` launches `main.py` using `venv\Scripts\python.exe`.

No build step is currently required. If packaging is added later, document the command here.

## Coding Style & Naming Conventions

Use Python 3 conventions with 4-space indentation. Keep classes in `PascalCase`, functions and variables in `snake_case`, and constants in `UPPER_SNAKE_CASE`. UI tab classes should remain feature-named, for example `CleanupTab` in `app/cleanup_tab.py`.

Prefer small helper functions in `system_info.py` for raw platform access and `toolbox.py` for named user-facing toolbox operations. Keep Qt widget construction inside the relevant tab module.

Avoid blocking the UI thread. Slower scans or system actions should run in `QThread` workers and be submitted through the central `JobQueue` in `app/job_queue.py`. Use a stable scope name such as `cleanup`, `display`, `network-tools`, or `reports-tools` so duplicate scans/actions are rejected before another worker starts. Do not create a second synchronization helper or per-tab job framework unless replacing `JobQueue` everywhere in the same change.

## Testing Guidelines

When adding tests, use `pytest` unless the project adopts a different framework. Place tests under `tests/` and name files `test_<module>.py`. Prioritize pure helpers such as byte formatting, cleanup target selection, parsing, registry-data normalization, toolbox result handling, assistant skill conversion, and job-queue synchronization. For UI behavior, keep tests focused on logic that can run without requiring manual window interaction.

Use a lower-effort test loop during development:

- Run focused tests for the files/behavior changed, for example `.\venv\Scripts\python.exe -m pytest tests\test_job_queue.py tests\test_toolbox.py`.
- Run a lightweight compile check for touched app files with `.\venv\Scripts\python.exe -m py_compile <files>`.
- Run the full suite before a commit, release, or risky cross-cutting change.

Full suite:

```powershell
.\venv\Scripts\python.exe -m pytest
```

## Commit & Pull Request Guidelines

Recent commits use short, imperative summaries such as `Add .gitignore to keep venv and pycache out of version control`. Continue that style: describe the change in one sentence and keep it specific.

Pull requests should include a brief description, test notes, and screenshots or recordings for visible UI changes. Mention Windows-specific behavior, elevated-permission requirements, or cleanup/deletion risk.

## Security & Configuration Tips

Treat cleanup and system-inspection code carefully. Do not expand deletion targets without clear labels, conservative defaults, and user confirmation. Keep local virtual environments, caches, reports, downloaded models, and generated files out of version control.

Every system-changing toolbox or assistant action must use a fixed, named code path, validate targets in Python, and require user confirmation. Do not add arbitrary shell commands, arbitrary PowerShell, arbitrary Python execution, registry-edit surfaces, or unrestricted file deletion.

## Assistant Skills Documentation

`skills_list.md` documents every LLM-requestable assistant skill, what action it maps to, its risk level, confirmation behavior, and accepted friendly arguments. Whenever adding, removing, renaming, disabling, or changing behavior for skills in `app/assistant_core.py` (`ASSISTANT_SKILLS`, `ASSISTANT_TOOLS`, skill validation, or skill-to-action conversion), update `skills_list.md` in the same change.

Keep this documentation conservative and safety-focused. Any system-changing skill must clearly say that it requires user confirmation, and no skill documentation should imply that the LLM can run arbitrary shell commands, arbitrary Python, registry edits, unrestricted PowerShell, or arbitrary file deletion.
