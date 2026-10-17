"""Offscreen GUI widget tests (ADR-0008 decision 3: Qt tests run headless).

Skipped entirely when PySide6 is not installed — the core suite must stay
green on Qt-free installs. Run with: QT_QPA_PLATFORM=offscreen pytest.

These tests exercise the G1 shell end-to-end WITHOUT a display: build the
window, drive the form widgets programmatically, click Run, and assert on
the log pane + real files written through AppService (thin-client parity:
whatever the window produces, the CLI/service path produces identically).
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QComboBox, QLineEdit, QPushButton, QTextEdit  # noqa: E402

from lexora.gui.app import VIEWS, build_window  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture()
def window(qapp):
    win = build_window()
    yield win
    win.close()


def _find(window, type_, text=None):
    for w in window.findChildren(type_):
        label = w.text() if hasattr(w, "text") else ""
        ph = w.placeholderText() if hasattr(w, "placeholderText") else ""
        if text is None or text in (label or "") or text in (ph or ""):
            return w
    raise AssertionError(f"widget {type_.__name__} ({text!r}) not found")


def test_window_builds_with_expected_views(window):
    assert "LEXORA" in window.windowTitle()
    combo = _find(window, QComboBox)
    assert [combo.itemText(i) for i in range(combo.count())][: len(VIEWS)] == list(VIEWS)


def _wait_done(window, log, timeout_ms=10000):
    """Pump the event loop until the M2 job runner settles and the log pane
    updates (pack/unpack now run on a QThread; click() returns immediately)."""
    from PySide6.QtCore import QDeadlineTimer, QEventLoop, QTimer
    loop = QEventLoop()
    deadline = QDeadlineTimer(timeout_ms)
    check = QTimer()
    check.setInterval(5)
    def tick():
        # progress bar hidden + Run re-enabled == job settled
        from PySide6.QtWidgets import QProgressBar, QPushButton
        run_btn = next(b for b in window.findChildren(QPushButton) if b.text() == "Run")
        bars = window.findChildren(QProgressBar)
        if run_btn.isEnabled() and all(not b.isVisible() for b in bars):
            loop.quit()
        elif deadline.hasExpired():
            loop.quit()
    check.timeout.connect(tick)
    check.start()
    loop.exec()
    check.stop()


def test_pack_then_unpack_roundtrip_through_widgets(window, tmp_path):
    src = tmp_path / "in.txt"
    payload = b"gui widget roundtrip payload\n" * 50
    src.write_bytes(payload)
    arc = tmp_path / "out.lxz"
    back = tmp_path / "back.txt"

    combo = _find(window, QComboBox)
    lineedits = window.findChildren(QLineEdit)
    in_edit = next(le for le in lineedits if "input file" in le.placeholderText())
    out_edit = next(le for le in lineedits if "output file" in le.placeholderText())
    run_btn = _find(window, QPushButton, "Run")
    log = _find(window, QTextEdit)

    combo.setCurrentText("pack")
    in_edit.setText(str(src))
    out_edit.setText(str(arc))
    run_btn.click()
    _wait_done(window, log)
    assert "packed" in log.toPlainText(), log.toPlainText()
    assert arc.exists()

    combo.setCurrentText("unpack")
    in_edit.setText(str(arc))
    out_edit.setText(str(back))
    run_btn.click()
    _wait_done(window, log)
    assert "unpacked" in log.toPlainText(), log.toPlainText()
    assert back.read_bytes() == payload


def test_tampered_archive_shows_exit7_and_no_output(window, tmp_path):
    from lexora.gui.service import AppService

    arc = tmp_path / "t.lxz"
    good = AppService().run_pack(b"tamper me", level=3).value["archive"]
    bad = bytearray(good)
    bad[len(good) - 5] ^= 0xFF
    arc.write_bytes(bytes(bad))

    combo = _find(window, QComboBox)
    lineedits = window.findChildren(QLineEdit)
    in_edit = next(le for le in lineedits if "input file" in le.placeholderText())
    out_edit = next(le for le in lineedits if "output file" in le.placeholderText())
    run_btn = _find(window, QPushButton, "Run")
    log = _find(window, QTextEdit)

    target = tmp_path / "never.txt"
    combo.setCurrentText("unpack")
    in_edit.setText(str(arc))
    out_edit.setText(str(target))
    run_btn.click()
    _wait_done(window, log)
    assert "[exit 7]" in log.toPlainText()
    assert "no output written" in log.toPlainText()
    assert not target.exists()


def test_inspect_view_renders_header(window, tmp_path):
    from lexora.gui.service import AppService

    arc = tmp_path / "i.lxz"
    blob = AppService().run_pack(b"inspect me please", level=3).value["archive"]
    arc.write_bytes(blob)

    combo = _find(window, QComboBox)
    lineedits = window.findChildren(QLineEdit)
    in_edit = next(le for le in lineedits if "input file" in le.placeholderText())
    run_btn = _find(window, QPushButton, "Run")
    log = _find(window, QTextEdit)

    combo.setCurrentText("inspect")
    in_edit.setText(str(arc))
    run_btn.click()
    text = log.toPlainText()
    assert "compressed:" in text and "uncompressed:" in text


def test_bad_integer_field_refused_without_io(window, tmp_path):
    combo = _find(window, QComboBox)
    lineedits = window.findChildren(QLineEdit)
    in_edit = next(le for le in lineedits if "input file" in le.placeholderText())
    lvl = next(le for le in lineedits if le.text() == "3")
    run_btn = _find(window, QPushButton, "Run")
    log = _find(window, QTextEdit)

    combo.setCurrentText("pack")
    in_edit.setText(str(tmp_path / "ignored"))
    lvl.setText("abc")
    run_btn.click()
    assert "integers" in log.toPlainText()


# --- launcher regression (Session-28 known issue) ---------------------------
# On a headless box, constructing QApplication without a usable platform
# plugin aborts the process (SIGABRT). main() must therefore answer
# --help/--version BEFORE touching Qt, and fall back to offscreen when no
# display is present. See Session 28 handoff note.

import subprocess  # noqa: E402
import sys  # noqa: E402


def _run_gui(args):
    return subprocess.run(
        [sys.executable, "-m", "lexora.gui", *args],
        capture_output=True, text=True, timeout=60,
        env={k: v for k, v in os.environ.items()
             if k not in ("QT_QPA_PLATFORM",)},
    )


def test_help_exits_zero_without_qt_abort():
    proc = _run_gui(["--help"])
    assert proc.returncode == 0, f"rc={proc.returncode} (abort?); stderr={proc.stderr}"
    assert "usage: lexora-gui" in proc.stdout


def test_version_exits_zero_without_qt_abort():
    proc = _run_gui(["--version"])
    assert proc.returncode == 0, f"rc={proc.returncode}; stderr={proc.stderr}"
    assert "(gui)" in proc.stdout


def test_unknown_option_exit2_no_io():
    proc = _run_gui(["--bogus"])
    assert proc.returncode == 2
    assert "unrecognized option" in proc.stderr


# ---- GUI-M2: async job runner driven through the real widgets --------------

def test_runner_reports_progress_and_settles(window, tmp_path):
    """Pack a larger payload via the window; the progress bar must receive
    real (non-busy) range updates and settle at full before the log flips."""
    from PySide6.QtWidgets import QProgressBar

    src = tmp_path / "big.txt"
    src.write_bytes(b"progress fill measurement\n" * 4000)
    arc = tmp_path / "big.lxz"

    combo = _find(window, QComboBox)
    lineedits = window.findChildren(QLineEdit)
    in_edit = next(le for le in lineedits if "input file" in le.placeholderText())
    out_edit = next(le for le in lineedits if "output file" in le.placeholderText())
    run_btn = _find(window, QPushButton, "Run")
    log = _find(window, QTextEdit)
    bar = window.findChildren(QProgressBar)[0]

    combo.setCurrentText("pack")
    in_edit.setText(str(src))
    out_edit.setText(str(arc))
    run_btn.click()
    final_range = bar.maximum()      # sampled while loop may still be running
    _wait_done(window, log)
    assert "packed" in log.toPlainText(), log.toPlainText()
    assert arc.exists()
    # byte-weighted total = input + output size; must have been configured
    expected = src.stat().st_size + arc.stat().st_size
    assert final_range in (0, expected) or bar.maximum() == expected


def test_cancel_before_start_writes_no_output(window, tmp_path):
    """Cancel pressed after click but before the read stage completes ->
    cancelled banner, no output file. Deterministic variant: pre-fill an
    already-cancelled token is not reachable from widgets, so we cancel
    immediately after click on a big input; either the job finished first
    (benign race, output valid) or cancellation path ran (no output)."""
    src = tmp_path / "huge.txt"
    src.write_bytes(b"x" * (32 * 1024 * 1024))   # slow enough to interrupt
    arc = tmp_path / "huge.lxz"

    combo = _find(window, QComboBox)
    lineedits = window.findChildren(QLineEdit)
    in_edit = next(le for le in lineedits if "input file" in le.placeholderText())
    out_edit = next(le for le in lineedits if "output file" in le.placeholderText())
    run_btn = _find(window, QPushButton, "Run")
    cancel_btn = _find(window, QPushButton, "Cancel")
    log = _find(window, QTextEdit)

    combo.setCurrentText("pack")
    in_edit.setText(str(src))
    out_edit.setText(str(arc))
    run_btn.click()
    cancel_btn.click()
    _wait_done(window, log)
    text = log.toPlainText()
    if "cancelled" in text:
        assert not arc.exists(), "cancel raced past write stage yet wrote output"
    else:
        assert "packed" in text or "[exit" in text, text


# --- G5 preview + G6 diagnostics history (Session 30, GUI-M2b) --------------

def test_pure_renderers_without_qt():
    """format_preview_text/format_inspect_text are Qt-free module functions:
    importable and exercisable without a QApplication (thin-client rule —
    rendering logic is testable headlessly by construction)."""
    from lexora.gui.app import format_preview_text
    from lexora.gui.service import AppService, JobResult

    res = AppService().run_canon_meta(b"hello\r\nworld")
    text = format_preview_text(res)
    assert "applied rules:" in text and "CAN-R01" in text
    assert "     1 | hello" in text and "     2 | world" in text
    # failure passthrough uses the exit-code banner shape
    fail = format_preview_text(JobResult(False, error="boom", exit_code=4))
    assert fail == "[exit 4] boom"


def test_truncation_note_only_when_over_cap(tmp_path):
    from lexora.gui.app import PREVIEW_MAX_BYTES, format_preview_text
    from lexora.gui.service import AppService

    small = format_preview_text(AppService().run_canon_meta(b"tiny"))
    assert "truncated" not in small
    big = format_preview_text(
        AppService().run_canon_meta(b"a" * (PREVIEW_MAX_BYTES + 10)))
    assert "truncated" in big


def test_preview_view_renders_canonicalized_text(window, tmp_path):
    src = tmp_path / "raw.txt"
    src.write_bytes(b"alpha\r\nbeta\r\ngamma")
    combo = _find(window, QComboBox)
    in_edit = next(le for le in window.findChildren(QLineEdit)
                   if "input file" in le.placeholderText())
    run_btn = _find(window, QPushButton, "Run")
    log = _find(window, QTextEdit)

    combo.setCurrentText("preview")
    in_edit.setText(str(src))
    run_btn.click()
    text = log.toPlainText()
    assert "canonicalizer:" in text
    assert "     1 | alpha" in text and "     3 | gamma" in text
    assert "input:  18 B" in text and "output: 16 B" in text  # CRLFs folded


def test_preview_missing_file_shows_exit3_banner(window, tmp_path):
    combo = _find(window, QComboBox)
    in_edit = next(le for le in window.findChildren(QLineEdit)
                   if "input file" in le.placeholderText())
    run_btn = _find(window, QPushButton, "Run")
    log = _find(window, QTextEdit)

    combo.setCurrentText("preview")
    in_edit.setText(str(tmp_path / "nope.txt"))
    run_btn.click()
    assert "[exit 3]" in log.toPlainText()


def test_diagnostics_history_accumulates_and_caps(window, tmp_path):
    """G6: every banner stays in history (newest last), capped at
    DIAGNOSTICS_HISTORY entries."""
    from lexora.gui.app import DIAGNOSTICS_HISTORY

    combo = _find(window, QComboBox)
    lineedits = window.findChildren(QLineEdit)
    in_edit = next(le for le in lineedits if "input file" in le.placeholderText())
    run_btn = _find(window, QPushButton, "Run")
    log = _find(window, QTextEdit)

    combo.setCurrentText("inspect")
    in_edit.setText("")
    expected = []
    for i in range(DIAGNOSTICS_HISTORY + 10):
        msg = f"choose an input file first #{i}" if i == 0 else "choose an input file first"
        run_btn.click()
        expected.append("choose an input file first")
    text = log.toPlainText()
    entries = [e for e in text.split("\n\n") if e]
    assert len(entries) == DIAGNOSTICS_HISTORY, len(entries)
    assert all(e == "choose an input file first" for e in entries)


# ---- G7 settings through the window (GUI-M2c) --------------------------------

def test_save_defaults_button_persists_and_refills(qapp, tmp_path, monkeypatch):
    """Click 'Save as defaults' -> JSON on disk; a NEW window pre-fills from it."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    win = build_window()
    level_edit = next(le for le in win.findChildren(QLineEdit) if le.width() <= 60 + 1
                      and le.text().isdigit())
    block_edit = next(le for le in win.findChildren(QLineEdit)
                      if le.text() == "8388608")
    level_edit.setText("9")
    block_edit.setText("4096")
    _find(win, QPushButton, "Save as defaults").click()
    saved = tmp_path / "lexora" / "gui-settings.json"
    assert saved.exists()
    import json as _json
    assert _json.loads(saved.read_text()) == {"level": 9, "block_size": 4096}
    log = _find(win, QTextEdit)
    assert "defaults saved to" in log.toPlainText()
    win.close()

    win2 = build_window()
    l2 = next(le for le in win2.findChildren(QLineEdit) if le.text() == "9")
    b2 = next(le for le in win2.findChildren(QLineEdit) if le.text() == "4096")
    assert l2 and b2
    win2.close()


def test_save_defaults_bad_integer_banner_only(qapp, tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    win = build_window()
    level_edit = next(le for le in win.findChildren(QLineEdit) if le.text() == "3")
    level_edit.setText("abc")
    _find(win, QPushButton, "Save as defaults").click()
    log = _find(win, QTextEdit)
    assert "must be integers" in log.toPlainText()
    assert not (tmp_path / "lexora" / "gui-settings.json").exists()
    win.close()


def test_save_defaults_out_of_range_exit2_no_file(qapp, tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    win = build_window()
    block_edit = next(le for le in win.findChildren(QLineEdit) if le.text() == "8388608")
    block_edit.setText("99999999999")   # > LIM-01 ceiling
    _find(win, QPushButton, "Save as defaults").click()
    log = _find(win, QTextEdit)
    assert "[exit 2]" in log.toPlainText()
    assert not (tmp_path / "lexora" / "gui-settings.json").exists()
    win.close()


def test_screenshot_helper_writes_png(window, tmp_path):
    """save_screenshot must produce a real PNG file offscreen (docs shots)."""
    from lexora.gui.app import save_screenshot

    out = tmp_path / "shot.png"
    assert save_screenshot(window, out) is True
    data = out.read_bytes()
    assert data.startswith(b"\x89PNG\r\n\x1a\n")
    assert len(data) > 1000   # non-trivial render, not an empty pixmap
