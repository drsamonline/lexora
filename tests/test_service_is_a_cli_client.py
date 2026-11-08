"""The GUI's service layer is a **client of the CLI** (ADR-0011), asserted at argv level.

The existing `test_gui_service.py` proves behaviour: the service returns the same bytes
the library would, errors map to exit codes, and so on. This file proves the *mechanism*,
because behaviour alone cannot tell the difference between "shells out to the CLI" and
"calls the library directly" — both produce identical bytes, which is precisely why the
architectural rule needs its own test.

If someone later reintroduces an in-process call, `test_gui_service.py` stays green and
this file goes red. That is the point.
"""

from __future__ import annotations

import subprocess

import pytest

from lexora.gui import service as svc_mod


class _Recorder:
    """Stands in for subprocess.run and records what the service asked for."""

    def __init__(self, stdout: bytes = b"OUT", returncode: int = 0, stderr: bytes = b""):
        self.calls: list[list[str]] = []
        self.stdin: list[bytes | None] = []
        self._stdout = stdout
        self._returncode = returncode
        self._stderr = stderr

    def __call__(self, cmd, **kwargs):
        self.calls.append(list(cmd))
        self.stdin.append(kwargs.get("input"))
        return subprocess.CompletedProcess(cmd, self._returncode, self._stdout, self._stderr)


@pytest.fixture()
def recorder(monkeypatch):
    rec = _Recorder()
    monkeypatch.setattr(svc_mod.subprocess, "run", rec)
    return rec


def test_run_pack_shells_out_with_the_payload_on_stdin(recorder) -> None:
    res = svc_mod.AppService().run_pack(b"payload", level=9, block_size=1024)
    assert res.ok
    argv = recorder.calls[0]
    assert argv[:4] == [argv[0], "-m", "lexora.cli", "pack"]
    assert "--in" in argv and argv[argv.index("--in") + 1] == "-"
    assert argv[argv.index("--out") + 1] == "-"
    assert argv[argv.index("--level") + 1] == "9"
    assert argv[argv.index("--block-size") + 1] == "1024"
    assert recorder.stdin[0] == b"payload", "the payload must travel on stdin"


def test_run_unpack_shells_out_and_passes_only_block(recorder) -> None:
    svc_mod.AppService().run_unpack(b"archive", only_block=3)
    argv = recorder.calls[0]
    assert argv[3] == "unpack"
    assert argv[argv.index("--block") + 1] == "3"
    assert recorder.stdin[0] == b"archive"


def test_run_compress_uses_zround_so_the_round_trip_is_verified(recorder) -> None:
    """A frame that cannot decode must fail here, not at the user's next open."""
    svc_mod.AppService().run_compress(b"text", level=19)
    assert recorder.calls[0][3] == "zround"
    assert "--level" in recorder.calls[0]


def test_run_decompress_uses_zdecode(recorder) -> None:
    svc_mod.AppService().run_decompress(b"frame")
    assert recorder.calls[0][3] == "zdecode"


def test_run_canon_shells_out(recorder) -> None:
    svc_mod.AppService().run_canon(b"raw", declared_encoding="cp1251")
    argv = recorder.calls[0]
    assert argv[3] == "canon"
    assert argv[argv.index("--encoding") + 1] == "cp1251"


def test_a_cli_failure_becomes_the_cli_exit_code(monkeypatch) -> None:
    """Exit codes come from the CLI, not from a re-implementation here (ADR-0018)."""
    rec = _Recorder(returncode=2, stderr=b"usage error: --level 99: out of range\n")
    monkeypatch.setattr(svc_mod.subprocess, "run", rec)
    res = svc_mod.AppService().run_pack(b"x", level=99)
    assert not res.ok
    assert res.exit_code == 2
    assert "--level" in res.error, "the CLI's own message must reach the user"


def test_a_missing_cli_does_not_raise(monkeypatch) -> None:
    def boom(*_a, **_k):
        raise FileNotFoundError("python")

    monkeypatch.setattr(svc_mod.subprocess, "run", boom)
    res = svc_mod.AppService().run_pack(b"x")
    assert not res.ok and res.exit_code == svc_mod.EXIT_FILE


def test_a_hung_cli_does_not_raise(monkeypatch) -> None:
    def slow(*_a, **_k):
        raise subprocess.TimeoutExpired(cmd="lexora", timeout=1)

    monkeypatch.setattr(svc_mod.subprocess, "run", slow)
    res = svc_mod.AppService().run_pack(b"x")
    assert not res.ok and res.exit_code == svc_mod.EXIT_FILE


def test_run_canon_meta_stays_in_process_and_that_is_deliberate() -> None:
    """The one documented exception: pure bytes→bytes+dict, nothing to isolate.

    Asserted rather than left implicit, because "one method bypasses the rule" is
    exactly the kind of thing that quietly becomes five.
    """
    res = svc_mod.AppService().run_canon_meta(b"a\r\nb\r\n")
    assert res.ok
    assert isinstance(res.value, dict) and "canonical" in res.value
    assert res.value["canonical"] == b"a\nb\n"
