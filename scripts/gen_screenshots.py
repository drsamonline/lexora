#!/usr/bin/env python3
"""Generate GUI screenshots for the docs (GUI-M2c, DESIGN_GUI §5).

Headless-safe: forces QT_QPA_PLATFORM=offscreen before any Qt import, builds
the real G1 window via lexora.gui.app.build_window(), and grabs PNGs with
QWidget.grab(). Skips cleanly (exit 0) when PySide6 is not installed.

Usage:  python3 scripts/gen_screenshots.py [outdir]     (default docs/assets)
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def main() -> int:
    outdir = Path(sys.argv[1] if len(sys.argv) > 1 else "docs/assets")
    try:
        from PySide6.QtWidgets import QApplication  # noqa: F401
    except ImportError:
        print("PySide6 not installed — skipping screenshot generation "
              "(pip install 'lexora[gui]')")
        return 0

    from lexora.gui.app import build_window, save_screenshot

    app = QApplication.instance() or QApplication([])
    del app  # keep a process-wide instance alive; not used directly

    outdir.mkdir(parents=True, exist_ok=True)
    shots = []

    win = build_window()
    win.resize(900, 600)
    ok = save_screenshot(win, outdir / "gui-main.png")
    shots.append(("gui-main.png", ok))

    # Second shot: preview view selected, so the docs show both feed panes.
    from PySide6.QtWidgets import QComboBox
    view_box = win.findChild(QComboBox)
    if view_box is not None:
        view_box.setCurrentText("preview")
        ok2 = save_screenshot(win, outdir / "gui-preview-view.png")
        shots.append(("gui-preview-view.png", ok2))

    failed = [name for name, ok in shots if not ok]
    for name, ok in shots:
        print(f"{'wrote' if ok else 'FAILED'} {outdir / name}")
    if failed:
        print("screenshot generation failed", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
