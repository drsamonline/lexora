# LEXORA GUI packaging recipes (GUI-M2c, DESIGN_GUI §5)

Wheel building is repo-wide (`pip install build && python -m build`); the GUI
rides along as the optional `[gui]` extra (`pip install 'lexora[gui]'`,
ADR-0008 decision 1). These recipes cover app-bundle-style packaging. No CI
runs any of this (GitHub Actions paused, OQ-15) — commands are smoke notes
verified at least once manually on the listed platform before a release tag.

## Linux

- **`.desktop` entry**: `packaging/lexora.desktop` (this directory). Install:
  ```sh
  cp packaging/lexora.desktop ~/.local/share/applications/   # per-user
  # or system-wide: /usr/share/applications/ (needs root)
  update-desktop-database ~/.local/share/applications 2>/dev/null || true
  ```
  Requires the `lexora-gui` console script on PATH (i.e. `pip install
  'lexora[gui]'` inside an active environment; for a venv, wrap with a small
  launcher script or use Flatpak later — out of scope until owner picks one).
- **Icon**: none shipped yet (placeholder `Icon=lexora` resolves to the
  theme default). Track as a polish item; do NOT invent binary assets in-repo.
- Smoke note (Debian 12 container, 2026-10-17): offscreen launch verified by
  tests (`tests/test_gui_app_offscreen.py`); real-display launch untested —
  needs a desktop session.

## macOS

- Recipe candidate: `pyinstaller --windowed --name LEXORA src/lexora/gui/__main__.py`
  (PyInstaller not yet a declared dependency — add under a `packaging` extra
  when a Mac smoke run actually happens).
- Status: **NOT smoke-tested** (no macOS host available in this workspace).
  Do not claim `.app` support in user-facing docs until it is.

## Windows

- Recipe candidate: same PyInstaller approach (`--noconsole`), plus
  `windeployqt` if bundling Qt DLLs manually.
- Status: **NOT smoke-tested** (no Windows host). Same documentation ban.

## Rule

DESIGN_GUI §5 acceptance for M3 requires packaged-app smoke evidence on each
claimed platform. Until then, the only supported installation story is the
wheel + `[gui]` extra, and that is what README/docs must say.
