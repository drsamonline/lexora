"""LEXORA GUI application shell — G1 main window + view stack (GUI-M1).

ADR-0008 compliance:
* ALL Qt imports are lazy (inside functions). Importing this module without
  PySide6 installed must succeed and must not touch Qt.
* Views contain no business logic: every operation delegates to
  `lexora.gui.service.AppService` (thin-client rule, DESIGN_GUI §2).
* No console entry point is registered in pyproject yet (ADR-0008 decision 2:
  entry point lands only when the window is demonstrably runnable; until then
  launch with `python -m lexora.gui`).

M1 scope (DESIGN_GUI §5 GUI-M1): G1 main window hosting G2 pack, G3 unpack,
G4 inspector views. File dialogs own path selection; the service owns I/O.
Progress/cancellation (job runner) lands with GUI-M2 — M1 operations run
synchronously on the UI thread over the same tested service calls.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - typing only, never executed at runtime
    from PySide6.QtWidgets import QMainWindow

APP_TITLE = "LEXORA"
VIEWS: tuple[str, ...] = ("pack", "unpack", "inspect")


def _service():
    """Single AppService instance per process (stateless facade anyway)."""
    from lexora.gui.service import AppService

    return AppService()


def build_window():
    """Create the G1 main window with the G2/G3/G4 view stack. Returns a
    ready-to-show QMainWindow. Raises ImportError with guidance if Qt absent.

    GUI-M2: pack/unpack run through `JobRunner` (QThread worker) so the UI
    thread never blocks; a progress bar + Cancel button drive the job. The
    views still own no logic — they only wire widgets to service calls."""
    try:
        from PySide6.QtWidgets import (
            QComboBox, QHBoxLayout, QLabel, QLineEdit, QMainWindow,
            QProgressBar, QPushButton, QTextEdit, QVBoxLayout, QWidget,
        )
    except ImportError as exc:  # pragma: no cover - depends on environment
        raise ImportError(
            "The LEXORA GUI requires the [gui] extra: pip install 'lexora[gui]'"
        ) from exc

    from lexora.gui.service import JobRunner, pack_file_job, unpack_file_job

    svc = _service()
    runner = JobRunner()
    win = QMainWindow()
    win.setWindowTitle(f"{APP_TITLE} — archive toolkit (M2 preview)")

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
    in_edit = QLineEdit()
    in_edit.setPlaceholderText("input file (raw text or .lxz)")
    out_edit = QLineEdit()
    out_edit.setPlaceholderText("output file")
    level_edit = QLineEdit("3")
    level_edit.setFixedWidth(60)
    block_edit = QLineEdit(str(8 * 1024 * 1024))
    block_edit.setFixedWidth(120)
    canon_check = QComboBox()
    canon_check.addItems(["pack input as-is", "canonicalize first"])
    run_btn = QPushButton("Run")
    cancel_btn = QPushButton("Cancel")
    cancel_btn.setEnabled(False)
    progress = QProgressBar()
    progress.setRange(0, 0)      # busy indicator while hidden/idle
    progress.setVisible(False)
    log = QTextEdit()
    log.setReadOnly(True)

    form = QHBoxLayout()
    for w in (QLabel("in:"), in_edit, QLabel("out:"), out_edit,
              QLabel("level:"), level_edit, QLabel("block:"), block_edit,
              canon_check, run_btn, cancel_btn):
        form.addWidget(w)
    root.addLayout(form)
    root.addWidget(progress)
    root.addWidget(log, stretch=1)

    status = QLabel("ready")
    win.statusBar().addWidget(status)

    def _job_done(text: str) -> None:
        progress.setVisible(False)
        progress.setRange(0, 0)
        run_btn.setEnabled(True)
        cancel_btn.setEnabled(False)
        log.setPlainText(text)
        status.setText("ready")

    def show_inspect_result(res) -> None:
        if res.ok:
            hdr = res.value["header"]
            lines = [f"header fields: {len(hdr)}", f"compressed:   {res.value['total_compressed']} B",
                     f"uncompressed: {res.value['total_uncompressed']} B"]
            for k, v in hdr.items():
                if isinstance(v, bytes):
                    v = v.hex()
                lines.append(f"{k}: {v}")
            log.setPlainText("\n".join(lines))
        else:
            log.setPlainText(f"[exit {res.exit_code}] {res.error}")

    def on_progress(done: int, total: int) -> None:
        if total > 0:
            progress.setRange(0, total)
            progress.setValue(done)

    def on_run() -> None:
        view = view_box.currentText()
        src, dst = in_edit.text().strip(), out_edit.text().strip()
        if not src:
            log.setPlainText("choose an input file first")
            return
        try:
            level = int(level_edit.text())
            block = int(block_edit.text())
        except ValueError:
            log.setPlainText("level and block size must be integers")
            return
        if view == "inspect":  # metadata-only read: fast, stays synchronous
            res = svc.inspect_file(src)
            show_inspect_result(res)
            return
        if not dst:
            log.setPlainText(f"{view} needs an output file")
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

    run_btn.clicked.connect(on_run)
    cancel_btn.clicked.connect(on_cancel)

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

    app = QApplication(args)
    win = build_window()
    win.resize(900, 600)
    win.show()
    return app.exec()
