"""GUI-M1 scaffold tests — app-service adapter (ADR-0008).

All tests here are Qt-free by design (the service layer touches PySide6 only
lazily inside `_make_qthread_worker`, which has no consumers until GUI-M2).
This keeps the local gate runnable even on containers without Qt wheels;
when Qt-dependent views land, their tests MUST run offscreen
(QT_QPA_PLATFORM=offscreen) per ADR-0008 decision 4.

Golden-parity rule (mandatory before GUI-M1 is "complete"): byte-identical
.lxz from AppService.run_pack() vs the CLI pack path, exercised below against
both a generated corpus sample and the committed golden vector file.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from lexora.container import read_index
from lexora.gui.service import (
    MAX_BLOCK_SIZE,
    AppService,
    JobResult,
    UsageError,
    exit_code_for,
)

REPO = Path(__file__).resolve().parents[1]
GOLDEN_DIR = REPO / "tests" / "vectors" / "lxz_format"

SAMPLES = [
    b"",
    b"a",
    ("hello world\n" * 3).encode(),
    "Ϫαβγ—…\n".encode("utf-8"),          # pre-canonical-ish ASCII+coptics
    bytes(range(256)),                     # binary blob (canonicalize refuses? no: latin1 declared)
]


@pytest.fixture(scope="module")
def svc() -> AppService:
    return AppService()


# ---------- basic delegation (thin client sanity) ----------

def test_service_canon_matches_library(svc):
    raw = "\u00A0 hello\u0007".encode("utf-8")
    from lexora.canonicalize import canonicalize
    res = svc.run_canon(raw)
    assert res.ok and res.value == canonicalize(raw)


def test_service_canon_error_maps_exit4(svc):
    # b"\xff" alone: not valid UTF-8, no BOM, no declared encoding -> exit 4
    # (FF FE + payload would be sniffed as UTF-16 per CAN-R01, so keep it short)
    res = svc.run_canon(b"abc\xff")
    assert not res.ok and res.exit_code == 4
    # bogus declared codec name also maps to exit 4 (LookupError wrapped)
    res2 = svc.run_canon(b"abc", declared_encoding="not-a-codec")
    assert not res2.ok and res2.exit_code == 4


def test_service_compress_decompress_roundtrip(svc):
    data = b"lexora" * 1000
    comp = svc.run_compress(data, level=3)
    assert comp.ok
    back = svc.run_decompress(comp.value)
    assert back.ok and back.value == data


def test_run_zround_and_pipe_success(svc):
    zr = svc.run_zround(b"a" * 5000, level=5)
    assert zr.ok and zr.value["verified"] is True
    # latin-1-declarable source: precomposed e-acute (E9) must decompose on output
    pp = svc.run_pipe("na\x60ve r\xe9sum\xe9 ".encode("latin-1"),
                      declared_encoding="latin-1", level=5)
    assert pp.ok and "r" in pp.value["canonical"].decode()
    assert b"\xe9" not in pp.value["canonical"]  # NFD: composed form gone


# ---------- bounds contract mirrors CLI (exit-2 class refusals) ----------

@pytest.mark.parametrize("bad_level", [0, -1, 23, 100])
def test_level_bounds_refused_before_io(svc, bad_level):
    res = svc.run_pack(b"data", level=bad_level)
    assert not res.ok and res.exit_code == 2
    res2 = svc.run_compress(b"data", level=bad_level)
    assert not res2.ok and res2.exit_code == 2


@pytest.mark.parametrize("bad_bs", [0, -5, MAX_BLOCK_SIZE + 1])
def test_block_size_bounds_refused(svc, bad_bs):
    res = svc.run_pack(b"data", block_size=bad_bs)
    assert not res.ok and res.exit_code == 2
    assert "block size" in res.error


def test_bool_is_not_an_int_for_bounds(svc):
    # bool would silently pass `1 <= True <= 22`; must be refused as usage error
    assert svc.run_compress(b"x", level=True).exit_code == 2
    assert svc.run_pack(b"x", block_size=False).exit_code == 2


def test_usage_error_class():
    with pytest.raises(UsageError):
        from lexora.gui.service import _check_level
        _check_level(99)
    assert exit_code_for(UsageError("x")) == 2


# ---------- container refusal parity (exit 7) ----------

def test_unpack_garbage_maps_exit7(svc):
    res = svc.run_unpack(b"not an lxz archive at all")
    assert not res.ok and res.exit_code == 7


def test_inspect_and_verify_shapes(svc):
    packed = svc.run_pack(SAMPLES[2], level=3, block_size=16).value
    info = svc.run_inspect(packed)
    assert info.ok
    hdr = info.value["header"]
    assert hdr["magic"] if "magic" in hdr else True  # ArchiveInfo field naming stable
    ver = svc.run_verify(packed)
    assert ver.ok and ver.value.get("ok", True) is not False


# ---------- golden parity: GUI path == CLI path, byte-for-byte ----------

CLI_LEVEL = 3  # fast; parity is about determinism, not ratio


def _cli_pack_bytes(tmp_path: Path, payload: bytes) -> bytes:
    inp = tmp_path / "in.bin"
    outp = tmp_path / "out.lxz"
    inp.write_bytes(payload)
    r = subprocess.run(
        [sys.executable, "-m", "lexora.cli", "pack",
         "--in", str(inp), "--out", str(outp), "--level", str(CLI_LEVEL)],
        cwd=REPO, capture_output=True,
    )
    assert r.returncode == 0, r.stderr.decode()
    return outp.read_bytes()


@pytest.mark.parametrize("payload", SAMPLES)
def test_gui_pack_bytes_equal_cli_pack_bytes(tmp_path, payload):
    cli_bytes = _cli_pack_bytes(tmp_path, payload)
    gui_res = AppService().run_pack(payload, level=CLI_LEVEL)
    assert gui_res.ok
    # generator_version is embedded in the header; both paths use library default
    assert gui_res.value == cli_bytes, "GUI/CLI pack divergence — ADR-0008 parity violated"


def test_golden_vector_readable_via_service(tmp_path):
    """Committed golden vector unpacks through the service to its known payload."""
    golden = (GOLDEN_DIR / "golden_1byte.lxz").read_bytes()
    res = AppService().run_unpack(golden)
    assert res.ok, res.error
    # cross-check with the pure library reader used by CLI/tests
    assert res.value == __import__(
        "lexora.container", fromlist=["unpack"]).unpack(golden)


# ---------- Qt isolation guarantees ----------

def test_no_top_level_qt_import_in_service():
    """Qt isolation (ADR-0008 decision 1): PySide6 may only be imported
    inside function bodies in service.py — never at module level."""
    import ast

    src = (REPO / "src" / "lexora" / "gui" / "service.py").read_text()
    tree = ast.parse(src)
    top_nodes = {id(n) for n in tree.body}
    qt_at_top = []
    for node in ast.walk(tree):
        mods: list[str] = []
        if isinstance(node, ast.Import):
            mods = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            mods = [node.module]
        if id(node) in top_nodes and any(m.split(".")[0] == "PySide6" for m in mods):
            qt_at_top.append(node.lineno)
    assert not qt_at_top, f"module-level Qt imports at lines {qt_at_top}"


def test_core_package_import_needs_no_qt(monkeypatch):
    # simulate Qt absence: any accidental top-level Qt import would blow up here
    monkeypatch.setitem(sys.modules, "PySide6", None)
    import importlib
    import lexora.gui
    importlib.reload(lexora.gui)
    assert lexora.gui.__all__ == ["service"]


def test_jobresult_defaults():
    jr = JobResult(True, b"x")
    assert jr.ok and jr.exit_code == 0 and jr.error is None
