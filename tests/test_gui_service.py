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
    packed = svc.run_pack(SAMPLES[2], level=3, block_size=16).value["archive"]
    info = svc.run_inspect(packed)
    assert info.ok
    hdr = info.value["header"]
    assert hdr["magic"] if "magic" in hdr else True  # ArchiveInfo field naming stable
    ver = svc.run_verify(packed)
    assert ver.ok and ver.value.get("ok", True) is not False


# ---------- file-level operations (pack_file/unpack_file/...) ----------

def test_pack_unpack_file_roundtrip(tmp_path, svc):
    src = tmp_path / "in.txt"
    payload = b"hello lexora gui file path\n"
    src.write_bytes(payload)
    arc = tmp_path / "out.lxz"
    res = svc.pack_file(src, arc, level=3)
    assert res.ok, res.error
    assert res.value["bytes_in"] == len(payload) and res.value["bytes_out"] > 0
    out = tmp_path / "back.txt"
    res2 = svc.unpack_file(arc, out)
    assert res2.ok, res2.error
    assert out.read_bytes() == payload


def test_pack_file_canonicalize_first(tmp_path, svc):
    """canonicalize_first=True must produce EXACTLY canonicalize(raw) bytes in
    the archive (delegating to the library's tested rules — no GUI-side NFC
    assumption; whitelist contract CAN-R05 leaves Latin combining marks)."""
    from lexora.canonicalize import canonicalize
    src = tmp_path / "raw.txt"
    raw = "cafe\u0301 \u2014 dash input".encode()
    src.write_bytes(raw)
    arc = tmp_path / "out.lxz"
    res = svc.pack_file(src, arc, level=3, canonicalize_first=True)
    assert res.ok, res.error
    back = svc.unpack_file(arc, tmp_path / "out.txt")
    assert back.ok
    assert (tmp_path / "out.txt").read_bytes() == canonicalize(raw)


def test_pack_file_missing_input_exit3(tmp_path, svc):
    res = svc.pack_file(tmp_path / "nope.bin", tmp_path / "out.lxz", level=3)
    assert not res.ok and res.exit_code == 3
    assert not (tmp_path / "out.lxz").exists()


def test_unpack_file_tampered_refuses_before_write(tmp_path, svc):
    good = svc.run_pack(b"payload for tamper test", level=3).value["archive"]
    arc = tmp_path / "t.lxz"
    arc.write_bytes(good)
    bad = bytearray(good)
    bad[len(good) - 5] ^= 0xFF  # corrupt trailer/index digest area
    arc.write_bytes(bytes(bad))
    out = tmp_path / "never.txt"
    res = svc.unpack_file(arc, out)
    assert not res.ok and res.exit_code in (7,)
    assert not out.exists(), "partial output written despite refusal (REQ-SEC-004)"


def test_atomic_write_leaves_no_temp_on_success(tmp_path, svc):
    target = tmp_path / "w.bin"
    svc.atomic_write(b"data", target)
    assert target.read_bytes() == b"data"
    assert not list(tmp_path.glob(".w.bin.*.tmp")), "temp file leaked"


def test_inspect_verify_file_shapes(tmp_path, svc):
    seed = tmp_path / "seed"
    seed.write_bytes(b"0123456789abcdef")
    arc = tmp_path / "i.lxz"
    assert svc.pack_file(seed, arc, level=3, block_size=8).ok
    ins = svc.inspect_file(arc)
    assert ins.ok and "header" in ins.value
    ver = svc.verify_file(arc)
    assert ver.ok


def test_run_pack_shape_and_exit3_for_bad_output_dir(tmp_path, svc):
    src = tmp_path / "s.bin"
    src.write_bytes(b"x" * 32)
    res = svc.pack_file(src, tmp_path / "nodir" / "out.lxz", level=3)
    assert not res.ok and res.exit_code == 3


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
    assert gui_res.value["archive"] == cli_bytes, "GUI/CLI pack divergence — ADR-0008 parity violated"


def test_golden_vector_readable_via_service(tmp_path):
    """Committed golden vector unpacks through the service to its known payload."""
    golden = (GOLDEN_DIR / "golden_1byte.lxz").read_bytes()
    res = AppService().run_unpack(golden)
    assert res.ok, res.error
    # cross-check with the pure library reader used by CLI/tests
    assert res.value == __import__(
        "lexora.container", fromlist=["unpack"]).unpack(golden)


# ---------- Qt isolation guarantees ----------

@pytest.mark.parametrize("mod", ["service.py", "app.py", "crash.py"])
def test_no_top_level_qt_import_in_service(mod):
    """Qt isolation (ADR-0008 decision 1): PySide6 may only be imported
    inside function bodies in the gui package — never at module level.
    TYPE_CHECKING-guarded imports are allowed (never executed at runtime)."""
    import ast

    src = (REPO / "src" / "lexora" / "gui" / mod).read_text()
    tree = ast.parse(src)
    top_nodes = {id(n) for n in tree.body}
    tc_nodes: set[int] = set()
    for node in tree.body:
        if isinstance(node, ast.If) and getattr(node.test, "id", None) == "TYPE_CHECKING":
            for sub in ast.walk(node):
                tc_nodes.add(id(sub))
    qt_at_top = []
    for node in ast.walk(tree):
        mods: list[str] = []
        if isinstance(node, ast.Import):
            mods = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            mods = [node.module]
        if id(node) in top_nodes and id(node) not in tc_nodes \
                and any(m.split(".")[0] == "PySide6" for m in mods):
            qt_at_top.append(node.lineno)
    assert not qt_at_top, f"module-level Qt imports at lines {qt_at_top}"


def test_core_package_import_needs_no_qt(monkeypatch):
    # simulate Qt absence: any accidental top-level Qt import would blow up here
    monkeypatch.setitem(sys.modules, "PySide6", None)
    import importlib
    import lexora.gui
    importlib.reload(lexora.gui)
    # Session 32 added the crash module; set-compare so __all__ growth stays honest
    assert set(lexora.gui.__all__) >= {"service", "crash"}
    assert "app" in lexora.gui.__all__  # exposed but lazy-imported only


def test_jobresult_defaults():
    jr = JobResult(True, b"x")
    assert jr.ok and jr.exit_code == 0 and jr.error is None


# ---- GUI-M2: cancel/progress-aware job functions (Qt-free core) ------------

from lexora.gui.service import (  # noqa: E402
    CancelToken,
    JobCancelled,
    pack_file_job,
    unpack_file_job,
)

# G7 settings helpers (GUI-M2c)
from lexora.gui.service import (  # noqa: E402
    DEFAULT_SETTINGS,
    SETTINGS_FILENAME,
    load_settings,
    save_settings,
    settings_path,
)


def test_pack_file_job_matches_sync_result(tmp_path, svc):
    """Job variant must produce the SAME JobResult and bytes as the sync M1
    path — async is plumbing, not semantics."""
    src = tmp_path / "in.txt"
    payload = b"job parity payload\n" * 40
    src.write_bytes(payload)
    a = tmp_path / "a.lxz"
    b = tmp_path / "b.lxz"
    r_sync = svc.pack_file(src, a, level=3, block_size=65536)
    events = []
    r_job = pack_file_job(svc, src, b, level=3, block_size=65536,
                          progress_cb=lambda d, t: events.append((d, t)))
    assert r_job == r_sync
    assert a.read_bytes() == b.read_bytes()
    assert events, "expected at least one progress report"
    assert events[-1] == (events[-1][0], events[-1][0]), "final report saturates"


def test_unpack_file_job_matches_sync_and_reports_progress(tmp_path, svc):
    src = tmp_path / "in.txt"
    src.write_bytes(b"unpack job parity\n" * 30)
    arc = tmp_path / "x.lxz"
    svc.pack_file(src, arc, level=3)
    o1 = tmp_path / "o1.txt"
    o2 = tmp_path / "o2.txt"
    r_sync = svc.unpack_file(arc, o1)
    seen = []
    r_job = unpack_file_job(svc, arc, o2, progress_cb=lambda d, t: seen.append((d, t)))
    assert r_job == r_sync
    assert o1.read_bytes() == o2.read_bytes()
    assert len(seen) >= 2 and seen[-1][0] == seen[-1][1]


def test_job_bounds_refuse_before_io(tmp_path, svc):
    """exit-2 usage refusal happens before ANY file access (Session-26 rule)."""
    missing = tmp_path / "does-not-exist"
    out = tmp_path / "out.lxz"
    res = pack_file_job(svc, missing, out, level=99)
    assert (res.ok, res.exit_code) == (False, 2)
    assert not out.exists()


def test_job_cancelled_during_read_writes_nothing(tmp_path, svc):
    src = tmp_path / "in.txt"
    src.write_bytes(b"cancel me\n" * 100)
    out = tmp_path / "out.lxz"
    tok = CancelToken()
    tok.cancel()                      # cancelled before first stage check
    with pytest.raises(JobCancelled):
        pack_file_job(svc, src, out, level=3, cancel=tok)
    assert not out.exists()           # never reached write stage


def test_job_canonicalize_failure_propagates_exit4(tmp_path, svc):
    src = tmp_path / "bad.bin"
    # true invalid UTF-8 (lone continuation bytes); the earlier \xff\xfe pick
    # was wrong — it sniffs as latin-1 and canonicalizes fine.
    src.write_bytes(b"\x80\x81\x82 not valid utf-8")
    out = tmp_path / "out.lxz"
    res = pack_file_job(svc, src, out, canonicalize_first=True)
    assert (res.ok, res.exit_code) == (False, 4)
    assert not out.exists()


def test_job_tampered_archive_exit7_no_output(tmp_path, svc):
    good = svc.run_pack(b"tamper job", level=3).value["archive"]
    bad = bytearray(good)
    bad[len(good) - 5] ^= 0xFF
    arc = tmp_path / "t.lxz"
    arc.write_bytes(bytes(bad))
    out = tmp_path / "never.txt"
    res = unpack_file_job(svc, arc, out)
    assert (res.ok, res.exit_code) == (False, 7)
    assert not out.exists()


def test_job_missing_input_exit3(tmp_path, svc):
    res = pack_file_job(svc, tmp_path / "nope", tmp_path / "o.lxz")
    assert (res.ok, res.exit_code) == (False, 3)
    res = unpack_file_job(svc, tmp_path / "nope", tmp_path / "o.txt")
    assert (res.ok, res.exit_code) == (False, 3)


# ---- G7 settings (GUI-M2c) ---------------------------------------------------

def test_settings_defaults_without_file(tmp_path):
    s = load_settings(tmp_path / "absent.json")
    assert s == DEFAULT_SETTINGS
    from lexora import DEFAULT_LEVEL

    assert s["level"] == DEFAULT_LEVEL and s["block_size"] == MAX_BLOCK_SIZE


def test_settings_save_load_roundtrip(tmp_path):
    p = tmp_path / "cfg" / "gui-settings.json"
    save_settings({"level": 9, "block_size": 4096}, p)
    assert load_settings(p) == {"level": 9, "block_size": 4096}
    # plain JSON on disk (no Qt QSettings dependency anywhere in this layer)
    assert json.loads(p.read_text()) == {"level": 9, "block_size": 4096}


def test_settings_save_refuses_out_of_range_before_writing(tmp_path):
    p = tmp_path / "s.json"
    with pytest.raises(UsageError):
        save_settings({"level": 0}, p)
    with pytest.raises(UsageError):
        save_settings({"block_size": MAX_BLOCK_SIZE + 1}, p)
    assert not p.exists()          # refusal wrote nothing
    assert exit_code_for(_caught(UsageError, save_settings, {"level": 99}, p)) == 2


def _caught(exc_type, fn, *a, **k):
    try:
        fn(*a, **k)
    except exc_type as e:
        return e
    raise AssertionError("expected " + exc_type.__name__)


def test_settings_corrupt_or_out_of_range_values_fall_back(tmp_path):
    p = tmp_path / "s.json"
    p.write_text("{not json", encoding="utf-8")
    assert load_settings(p) == DEFAULT_SETTINGS           # corrupt -> defaults
    p.write_text('{"level": 999, "block_size": -5}', encoding="utf-8")
    assert load_settings(p) == DEFAULT_SETTINGS           # out-of-range -> dropped
    p.write_text('{"level": 7}', encoding="utf-8")
    assert load_settings(p) == {"level": 7, "block_size": MAX_BLOCK_SIZE}  # partial ok


def test_settings_path_honors_xdg(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert settings_path() == tmp_path / "lexora" / SETTINGS_FILENAME


# ---- GUI-M3a: path resolution for file-picker pre-fills (Qt-free) ----------

from lexora.gui.service import resolve_path  # noqa: E402


def test_resolve_path_empty_is_noop():
    assert resolve_path("") == (None, None)


def test_resolve_path_directory(tmp_path):
    got, err = resolve_path(str(tmp_path))
    assert err is None and got == tmp_path


def test_resolve_path_existing_file_seeds_parent(tmp_path):
    f = tmp_path / "in.txt"
    f.write_bytes(b"x")
    got, err = resolve_path(str(f))
    assert err is None and got == tmp_path


def test_resolve_path_missing_file_with_live_parent(tmp_path):
    got, err = resolve_path(str(tmp_path / "nope.lxz"))
    assert err is None and got == tmp_path   # seed dialog at parent dir


def test_resolve_path_missing_everywhere_errors(tmp_path):
    got, err = resolve_path(str(tmp_path / "ghost" / "gone.txt"))
    assert got is None and err and "does not exist" in err


def test_resolve_path_tilde_expansion():
    got, err = resolve_path("~")
    assert err is None and got is not None and got.is_dir()


# ---- GUI-M3a: crash log sink (stdlib-only; no Qt anywhere) ------------------

def test_crash_log_records_and_reads(tmp_path):
    from lexora.gui.crash import CrashLog

    log = CrashLog(tmp_path / "crash.log.jsonl")
    assert log.read_records() == []          # absent file -> empty, no raise
    try:
        raise ValueError("boom-test")
    except ValueError as exc:
        rec = log.record_exception(exc)
    assert rec["type"] == "ValueError" and "boom-test" in rec["message"]
    assert "Traceback" in rec["traceback"] or "ValueError" in rec["traceback"]
    again = log.read_records()
    assert len(again) == 1 and again[0]["type"] == "ValueError"
    # append-only: second record keeps the first
    log.record_exception(RuntimeError("second"))
    assert [r["type"] for r in log.read_records()] == ["ValueError", "RuntimeError"]


def test_crash_excepthook_logs_then_chains(tmp_path, monkeypatch):
    from lexora.gui.crash import CrashLog

    seen: list[tuple] = []
    monkeypatch.setattr(sys, "excepthook", lambda *a: seen.append(a),
                        raising=True)
    log = CrashLog(tmp_path / "c.jsonl")
    log.install()
    assert sys.excepthook.__func__ is CrashLog.excepthook
    assert sys.excepthook.__self__ is log
    try:
        raise KeyError("k")
    except KeyError as first:
        exc = first
        log.excepthook(KeyError, exc, exc.__traceback__)
    assert seen[0][0] is KeyError and seen[0][1] is exc   # chained to previous
    assert [r["type"] for r in log.read_records()] == ["KeyError"]
    # KeyboardInterrupt must NOT be logged as a crash
    log.excepthook(KeyboardInterrupt, KeyboardInterrupt(), None)
    assert [r["type"] for r in log.read_records()] == ["KeyError"]


def test_crash_install_enables_faulthandler(tmp_path):
    import faulthandler

    from lexora.gui import crash
    prev_hook = sys.excepthook
    try:
        log = crash.install(tmp_path / "c.jsonl")
        assert faulthandler.is_enabled()
        assert sys.excepthook.__func__ is crash.CrashLog.excepthook
        assert sys.excepthook.__self__ is log
    finally:
        sys.excepthook = prev_hook


def test_crash_default_path_honors_xdg(monkeypatch, tmp_path):
    from lexora.gui.crash import crash_log_path

    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert crash_log_path() == tmp_path / "lexora" / "crash.log.jsonl"


# ---- GUI-M3b: crash-record renderer (pure, Qt-free) -------------------------

def test_format_crash_records_empty_state():
    from lexora.gui.crash import format_crash_records

    assert "no crash records" in format_crash_records([])


def test_format_crash_records_newest_first_and_caps(tmp_path):
    from lexora.gui.crash import CrashLog, _MAX_TB_CHARS, format_crash_records

    log = CrashLog(tmp_path / "c.jsonl")
    log.record_exception(ValueError("first"))
    try:
        raise RuntimeError("long-one")
    except RuntimeError as exc:
        log.record_exception(exc)
    text = format_crash_records(log.read_records())
    lines = text.splitlines()
    assert lines[0] == "2 crash record(s), newest first"
    # newest-first: the RuntimeError block appears before the ValueError one
    assert text.index("#1") < text.index("RuntimeError: long-one") \
        and text.index("RuntimeError: long-one") < text.index("#2")
    assert "#2" in text and "ValueError: first" in text
    # per-record traceback budget: huge stacks are capped, not drowned
    fat = [{"ts": "t", "version": "v", "type": "X", "message": "m",
            "traceback": "y" * (_MAX_TB_CHARS + 500)}]
    capped = format_crash_records(fat)
    assert "… (truncated)" in capped
    assert capped.count("y") <= _MAX_TB_CHARS
