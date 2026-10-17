"""LEXORA GUI application shell — G1 main window + view stack (GUI-M1/M2).

ADR-0008 compliance:
* ALL Qt imports are lazy (inside functions). Importing this module without
  PySide6 installed must succeed and must not touch Qt.
* Views contain no business logic: every operation delegates to
  `lexora.gui.service.AppService` (thin-client rule, DESIGN_GUI §2).
* Console entry point `lexora-gui` registered once the window was proven
  runnable (ADR-0008 decision 2); `python -m lexora.gui` works too.

Scope landed so far (DESIGN_GUI §5): G1 main window hosting G2 pack,
G3 unpack, G4 inspector (M1); async job runner with progress + cancellation
(M2); preview pane fed by canonicalization metadata + diagnostics log
history (M2b, this revision). The service owns all I/O; widgets only wire
signals to tested service calls. Pure rendering helpers are kept as
module-level functions (`format_inspect_text`, `format_preview_text`) so
they are testable without Qt.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - typing only, never executed at runtime
    from PySide6.QtWidgets import QMainWindow

APP_TITLE = "LEXORA"
VIEWS: tuple[str, ...] = ("pack", "unpack", "inspect", "preview", "about")

PREVIEW_MAX_BYTES = 64 * 1024   # render cap for the G5 preview pane
DIAGNOSTICS_HISTORY = 50        # G6: keep last N banner entries


def format_about_text() -> str:
    """G8 About view rendering (pure, Qt-free — thin-client posture).

    Version + the exact file paths the app reads/writes outside user jobs
    (G7 settings, crash log) so users can inspect or delete them without
    hunting through config dirs. Paths come from the same Qt-free helpers
    the widgets use, so what is shown is what is used.
    """
    from lexora import __version__
    from lexora.gui.crash import crash_log_path
    from lexora.gui.service import DEFAULT_SETTINGS, settings_path

    s = settings_path()
    c = crash_log_path()
    return "\n".join([
        f"LEXORA {__version__} — archive toolkit GUI",
        "",
        "Toolchain: PySide6 (ADR-0008); thin client over the same library",
        "code paths as the CLI — no business logic in widgets.",
        "",
        "Files this app owns:",
        f"  settings:  {s}",
        f"  crash log: {c}",
        "",
        f"Default level: {DEFAULT_SETTINGS['level']}   "
        f"Default block size: {DEFAULT_SETTINGS['block_size']} B",
        "",
        "Docs: docs/DESIGN_GUI.md · docs/FORMAT_LXZ.md · docs/CLI_REFERENCE.md",
    ])


def format_inspect_text(res) -> str:
    """G4 inspector rendering (pure, Qt-free; mirrors prior widget code)."""
    if not res.ok:
        return f"[exit {res.exit_code}] {res.error}"
    hdr = res.value["header"]
    lines = [f"header fields: {len(hdr)}",
             f"compressed:   {res.value['total_compressed']} B",
             f"uncompressed: {res.value['total_uncompressed']} B"]
    blocks = hdr.get("blocks", [])
    lines.append(f"blocks: {len(blocks)}")
    for i, b in enumerate(blocks):
        sha = b["sha256"]
        if isinstance(sha, bytes):
            sha = sha.hex()[:16]
        lines.append(f"  #{i}: offset={b['offset']} comp={b['compressed_size']}B "
                     f"raw={b['uncompressed_size']}B sha={sha}")
    for k, v in hdr.items():
        if k == "blocks":
            continue
        if isinstance(v, bytes):
            v = v.hex()
        lines.append(f"{k}: {v}")
    return "\n".join(lines)


def format_preview_text(res) -> str:
    """G5 text-preview rendering (pure, Qt-free).

    Input JobResult comes from AppService.run_canon_meta. Shows the
    canonicalized text (UTF-8, lossy-decoded for display), a line-numbered
    view capped at PREVIEW_MAX_BYTES rendered characters, and the
    canonicalization audit header (version, applied rules, byte/sha stats)
    which doubles as the declared-vs-detected encoding warning feed.
    """
    if not res.ok:
        return f"[exit {res.exit_code}] {res.error}"
    meta = res.value
    canon: bytes = meta["canonical"]
    truncated = len(canon) > PREVIEW_MAX_BYTES
    shown = canon[:PREVIEW_MAX_BYTES].decode("utf-8", errors="replace")
    lines = [
        f"canonicalizer: {meta['canonicalizer_version']}",
        f"applied rules: {', '.join(meta['applied_rules'])}",
        f"input:  {meta['input_bytes']} B  sha256={meta['input_sha256'][:16]}…",
        f"output: {meta['output_bytes']} B  sha256={meta['output_sha256'][:16]}…",
    ]
    if truncated:
        lines.append(f"(preview truncated at {PREVIEW_MAX_BYTES} rendered chars)")
    lines.append("")
    numbered = []
    for i, ln in enumerate(shown.split("\n"), start=1):
        numbered.append(f"{i:>6} | {ln}")
    lines.extend(numbered)
    return "\n".join(lines)


def _service():
    """Single AppService instance per process (stateless facade anyway)."""
    from lexora.gui.service import AppService

    return AppService()


def build_window():
    """Create the G1 main window with the G2/G3/G4 view stack. Returns a
    ready-to-show QMainWindow. Raises ImportError with guidance if Qt absent.

    GUI-M2/M2b: pack/unpack run through `JobRunner` (QThread worker) so the
    UI thread never blocks; a progress bar + Cancel button drive the job.
    G5 preview renders canonicalized text with line numbers via the pure
    `format_preview_text`; the log pane doubles as the G6 diagnostics
    banner (append-only history, newest last). The views still own no
    logic — they only wire widgets to service calls."""
    try:
        from PySide6.QtWidgets import (
            QComboBox, QHBoxLayout, QLabel, QLineEdit, QMainWindow,
            QProgressBar, QPushButton, QTextEdit, QVBoxLayout, QWidget,
        )
    except ImportError as exc:  # pragma: no cover - depends on environment
        raise ImportError(
            "The LEXORA GUI requires the [gui] extra: pip install 'lexora[gui]'"
        ) from exc

    from PySide6.QtGui import QIcon

    from lexora.gui.service import (
        JobRunner, exit_code_for, load_settings, pack_file_job,
        resolve_path, save_settings, unpack_file_job,
    )

    def icon_path():
        """App icon master (SVG shipped in-package; Qt rasterizes it)."""
        from pathlib import Path
        return Path(__file__).parent / "assets" / "lexora.svg"

    svc = _service()
    runner = JobRunner()
    win = QMainWindow()
    win.setWindowTitle(f"{APP_TITLE} — archive toolkit (M3 polish)")
    try:  # window/taskbar icon; absence must never block startup
        win.setWindowIcon(QIcon(str(icon_path())))
    except Exception:  # pragma: no cover - exotic Qt/image-plugin failures
        pass

    central = QWidget(win)
    win.setCentralWidget(central)
    root = QVBoxLayout(central)

    # --- action ribbon: view selector -------------------------------------
    bar = QHBoxLayout()
    bar.addWidget(QLabel("View:"))
    view_box = QComboBox()
    view_box.addItems(VIEWS)
    bar.addWidget(view_box)
    bar.addStretch(1)
    root.addLayout(bar)

    # --- shared form widgets ------------------------------------------------
    settings = load_settings()           # G7: persisted defaults (or shipped)
    in_edit = QLineEdit()
    in_edit.setPlaceholderText("input file (raw text or .lxz)")
    out_edit = QLineEdit()
    out_edit.setPlaceholderText("output file")
    level_edit = QLineEdit(str(settings["level"]))
    level_edit.setFixedWidth(60)
    block_edit = QLineEdit(str(settings["block_size"]))
    block_edit.setFixedWidth(120)
    canon_check = QComboBox()
    canon_check.addItems(["pack input as-is", "canonicalize first"])
    browse_in_btn = QPushButton("Browse…")     # G8 native file picker (M3a)
    browse_out_btn = QPushButton("Browse…")
    crash_btn = QPushButton("Crash log")       # M3b: crash-log viewer action
    run_btn = QPushButton("Run")
    cancel_btn = QPushButton("Cancel")
    cancel_btn.setEnabled(False)
    save_btn = QPushButton("Save as defaults")   # G7 persist action
    progress = QProgressBar()
    progress.setRange(0, 0)      # busy indicator while hidden/idle
    progress.setVisible(False)
    log = QTextEdit()
    log.setReadOnly(True)        # G6: append-only diagnostics history

    form = QHBoxLayout()
    for w in (QLabel("in:"), in_edit, browse_in_btn,
              QLabel("out:"), out_edit, browse_out_btn,
              QLabel("level:"), level_edit, QLabel("block:"), block_edit,
              canon_check, run_btn, cancel_btn, save_btn, crash_btn):
        form.addWidget(w)
    root.addLayout(form)
    root.addWidget(progress)
    root.addWidget(log, stretch=1)

    status = QLabel("ready")
    win.statusBar().addWidget(status)

    diagnostics: list[str] = []   # G6 history backing store

    def show(text: str) -> None:
        """Append one entry to the diagnostics history and render it."""
        diagnostics.append(text)
        del diagnostics[:-DIAGNOSTICS_HISTORY]
        log.setPlainText("\n\n".join(diagnostics))

    def _job_done(text: str) -> None:
        progress.setVisible(False)
        progress.setRange(0, 0)
        run_btn.setEnabled(True)
        cancel_btn.setEnabled(False)
        show(text)
        status.setText("ready")

    def on_progress(done: int, total: int) -> None:
        if total > 0:
            progress.setRange(0, total)
            progress.setValue(done)

    def on_run() -> None:
        view = view_box.currentText()
        src, dst = in_edit.text().strip(), out_edit.text().strip()
        if view == "about":  # G8-lite: static info, no file input needed
            show(format_about_text())
            return
        if not src:
            show("choose an input file first")
            return
        try:
            level = int(level_edit.text())
            block = int(block_edit.text())
        except ValueError:
            show("level and block size must be integers")
            return
        if view == "inspect":  # metadata-only read: fast, stays synchronous
            show(format_inspect_text(svc.inspect_file(src)))
            return
        if view == "preview":  # G5: read + canonicalize, render only (no writes)
            try:
                raw = svc.read_file(src)
            except Exception as exc:  # FileOpError -> exit-3 banner (parity map)
                show(f"[exit {exit_code_for(exc)}] {exc}")
                return
            show(format_preview_text(svc.run_canon_meta(raw)))
            return
        if not dst:
            show(f"{view} needs an output file")
            return
        # Heavy paths go async through the runner (GUI-M2).
        run_btn.setEnabled(False)
        cancel_btn.setEnabled(True)
        progress.setVisible(True)
        progress.setRange(0, 0)
        status.setText(f"{view} running…")
        if view == "pack":
            token = runner.start(
                pack_file_job, svc, src, dst,
                level=level, block_size=block,
                canonicalize_first=(canon_check.currentIndex() == 1),
                progress_cb=on_progress,
                on_finished=lambda res: _job_done(
                    f"packed {res.value['bytes_in']} B -> {res.value['bytes_out']} B "
                    f"(ratio {res.value['bytes_out'] / max(res.value['bytes_in'], 1):.3f}) -> {dst}"
                    if res.ok else f"[exit {res.exit_code}] {res.error}"),
                on_cancelled=lambda: _job_done("cancelled (no partial output written)"),
                on_error=lambda exc: _job_done(f"internal error: {exc!r}"),
            )
        else:  # unpack
            token = runner.start(
                unpack_file_job, svc, src, dst,
                progress_cb=on_progress,
                on_finished=lambda res: _job_done(
                    f"unpacked {res.value['bytes_in']} B -> {res.value['bytes_out']} B -> {dst}"
                    if res.ok else f"[exit {res.exit_code}] {res.error} (no output written)"),
                on_cancelled=lambda: _job_done("cancelled (no partial output written)"),
                on_error=lambda exc: _job_done(f"internal error: {exc!r}"),
            )
        win._lexora_token = token  # keep referenced for GC safety

    def on_cancel() -> None:
        runner.cancel()
        cancel_btn.setEnabled(False)
        status.setText("cancelling…")

    def on_save_defaults() -> None:
        """G7: persist current level/block values as app defaults. The
        service validates (UsageError -> exit-2 banner); nothing is written
        on refusal, same posture as every other bounds check."""
        try:
            level = int(level_edit.text())
            block = int(block_edit.text())
        except ValueError:
            show("level and block size must be integers")
            return
        try:
            path = save_settings({"level": level, "block_size": block})
        except Exception as exc:  # UsageError (exit 2) or write error (exit 3)
            show(f"[exit {exit_code_for(exc)}] {exc}")
            return
        show(f"defaults saved to {path}")

    def on_show_crash_log() -> None:
        """M3b crash-log viewer: render `CrashLog.read_records()` through the
        pure formatter into the G6 pane (newest first). Test seam:
        ``win._lexora_crash_log`` may be monkeypatched to a CrashLog bound to
        a tmp path; production uses the real config-dir sink."""
        from lexora.gui.crash import CrashLog, format_crash_records

        clog = getattr(win, "_lexora_crash_log", None) or CrashLog()
        show(format_crash_records(clog.read_records()))

    def _seed_dir(line_edit) -> str:
        """Directory to open the picker at, from the field's current text.

        Test seam: ``win._lexora_seed_dir`` may be monkeypatched (offscreen
        tests have no real dialog). Production path uses the Qt-free service
        resolver (same posture as CLI path handling); unresolvable text just
        falls back to cwd silently."""
        resolved, _err = resolve_path(line_edit.text().strip())
        return str(resolved) if resolved else ""

    def on_browse_in() -> None:
        from PySide6.QtWidgets import QFileDialog
        # seams for offscreen tests: win._lexora_seed_dir (dir seeding),
        # win._lexora_open_dialog (dialog factory; production = QFileDialog)
        seed = getattr(win, "_lexora_seed_dir", _seed_dir)(in_edit)
        make = getattr(win, "_lexora_open_dialog", None) or QFileDialog
        dlg = make(win, "Select input file", seed)
        if isinstance(dlg, tuple):  # static-method style: (path, _sel)
            path = dlg[0]
        else:                       # dialog-instance style (testable)
            dlg.exec()
            path = dlg.selectedFiles()[0] if dlg.selectedFiles() else ""
        if path:
            in_edit.setText(path)

    def on_browse_out() -> None:
        from PySide6.QtWidgets import QFileDialog
        seed = getattr(win, "_lexora_seed_dir", _seed_dir)(out_edit)
        make = getattr(win, "_lexora_save_dialog", None) or QFileDialog
        dlg = make(win, "Select output file", seed)
        if isinstance(dlg, tuple):
            path = dlg[0]
        else:
            dlg.exec()
            path = dlg.selectedFiles()[0] if dlg.selectedFiles() else ""
        if path:
            out_edit.setText(path)

    run_btn.clicked.connect(on_run)
    cancel_btn.clicked.connect(on_cancel)
    save_btn.clicked.connect(on_save_defaults)
    browse_in_btn.clicked.connect(on_browse_in)
    browse_out_btn.clicked.connect(on_browse_out)
    crash_btn.clicked.connect(on_show_crash_log)

    # Widget handles the browse tests need (kept as attributes, not globals).
    win._lexora_widgets = {
        "in_edit": in_edit, "out_edit": out_edit,
        "browse_in_btn": browse_in_btn, "browse_out_btn": browse_out_btn,
        "crash_btn": crash_btn, "view_box": view_box, "log": log,
    }

    view_box.currentTextChanged.connect(lambda v: status.setText(f"{v} view"))
    return win


_GUI_USAGE = """usage: lexora-gui [options]

LEXORA graphical front-end (GUI-M1 shell; see docs/DESIGN_GUI.md).

options:
  -h, --help          show this message and exit (no Qt loaded)
  --version           show lexora version and exit (no Qt loaded)

environment:
  QT_QPA_PLATFORM     Qt platform plugin; auto-set to 'offscreen' when no
                      display is available (headless machines).
"""


def save_screenshot(win, path) -> bool:
    """Capture a window to a PNG. Direct `QWidget.grab()` render — works
    under the offscreen platform plugin without needing an event loop turn.

    Returns False if saving fails or Qt is absent; never raises. Used by
    scripts/gen_screenshots.py (docs screenshots, GUI-M2c)."""
    try:
        win.show()
        pixmap = win.grab()
    except Exception:  # pragma: no cover - environment-dependent Qt failure
        return False
    try:
        return bool(pixmap.save(str(path)))
    except Exception:  # pragma: no cover
        return False


def main(argv: list[str] | None = None) -> int:
    """Launch the GUI. Exit codes mirror CLI conventions (0 ok, 2 usage/env)."""
    import os
    import sys

    args = list(sys.argv[1:] if argv is None else argv)
    # Handle non-GUI flags BEFORE any Qt import/construction: on a headless
    # box QApplication() aborts (SIGABRT) if no platform plugin can start,
    # so --help/--version must never require one.
    if "-h" in args or "--help" in args:
        sys.stdout.write(_GUI_USAGE)
        return 0
    if "--version" in args:
        from lexora import __version__
        sys.stdout.write(f"lexora {__version__} (gui)\n")
        return 0
    unknown = [a for a in args if a.startswith("-")]
    if unknown:
        sys.stderr.write(f"lexora-gui: unrecognized option '{unknown[0]}'\n"
                         "Try 'lexora-gui --help'.\n")
        return 2

    try:
        from PySide6.QtWidgets import QApplication
    except ImportError:
        sys.stderr.write(
            "PySide6 not installed. GUI needs the optional extra: pip install 'lexora[gui]'\n")
        return 2

    # Headless fallback: without DISPLAY/WAYLAND_DISPLAY force the offscreen
    # plugin instead of letting xcb abort the process.
    if not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    # GUI-M3: crash evidence sink — faulthandler for hard crashes + JSONL
    # log for escaped Python exceptions (docs/DESIGN_GUI.md §3). Installed
    # before QApplication so startup failures are captured too.
    from lexora.gui.crash import install as install_crash_log
    install_crash_log()

    app = QApplication(args)
    win = build_window()
    win.resize(900, 600)
    win.show()
    return app.exec()
