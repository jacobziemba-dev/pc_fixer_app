# Repository Guidelines

## Project Structure & Module Organization

This repository contains a Windows-focused Python desktop app for PC diagnostics and cleanup.

- `main.py` is the PySide6 application entry point and wires the main tabs together.
- `app/` contains UI modules and shared logic. Tab files follow the feature they render: `dashboard_tab.py`, `hardware_tab.py`, `startup_tab.py`, and `cleanup_tab.py`.
- `app/system_info.py` centralizes OS, process, disk, startup, and cleanup data access.
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

Prefer small helper functions in `system_info.py` for platform access, and keep Qt widget construction inside the relevant tab module. Avoid blocking the UI thread; use `QThread` workers for slower scans or hardware queries, as shown in `HardwareWorker` and `ScanWorker`.

## Testing Guidelines

When adding tests, use `pytest` unless the project adopts a different framework. Place tests under `tests/` and name files `test_<module>.py`. Prioritize pure helpers such as byte formatting, cleanup target selection, parsing, and registry-data normalization. For UI behavior, keep tests focused on logic that can run without requiring manual window interaction.

Run tests with:

```powershell
.\venv\Scripts\python.exe -m pytest
```

## Commit & Pull Request Guidelines

Recent commits use short, imperative summaries such as `Add .gitignore to keep venv and pycache out of version control`. Continue that style: describe the change in one sentence and keep it specific.

Pull requests should include a brief description, test notes, and screenshots or recordings for visible UI changes. Mention Windows-specific behavior, elevated-permission requirements, or cleanup/deletion risk.

## Security & Configuration Tips

Treat cleanup and system-inspection code carefully. Do not expand deletion targets without clear labels, conservative defaults, and user confirmation. Keep local virtual environments, caches, and generated files out of version control.
