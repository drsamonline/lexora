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
        if text is None or text in (w.text() or "") or text in (w.placeholderText() or ""):
            return w
    raise AssertionError(f"widget {type_.__name__} ({text!r}) not found")


def test_window_builds_with_expected_views(window):
    assert "LEXORA" in window.windowTitle()
    combo = _find(window, QComboBox)
    assert [combo.itemText(i) for i in range(combo.count())][: len(VIEWS)] == list(VIEWS)


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
    assert "packed" in log.toPlainText(), log.toPlainText()
    assert arc.exists()

    combo.setCurrentText("unpack")
    in_edit.setText(str(arc))
    out_edit.setText(str(back))
    run_btn.click()
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
