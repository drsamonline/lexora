"""Tests for lexora.cli — exit codes and real behavior (P1-T5 precursor).

Only the two subcommands that actually exist are tested; no fabricated pack/unpack.
"""

from __future__ import annotations

import pytest

from lexora import cli


def test_canon_success(tmp_path):
    raw = tmp_path / "raw.txt"
    # U+00AD as UTF-8 bytes (\xc2\xad), plus CRLF -> LF expectation.
    raw.write_bytes("a\r\nb\u00adc".encode("utf-8"))
    out = tmp_path / "canon.txt"
    rc = cli.main(["canon", "--in", str(raw), "--out", str(out)])
    assert rc == cli.EXIT_OK
    assert out.read_bytes() == b"a\nbc"  # soft hyphen removed: "b\u00adc" -> "bc"


def test_canon_bad_encoding_exit4(tmp_path):
    raw = tmp_path / "raw.bin"
    raw.write_bytes(b"\x80\x81 not utf8")
    rc = cli.main(["canon", "--in", str(raw), "--out", "-"])
    assert rc == cli.EXIT_CANON


def test_canon_missing_file_exit3(tmp_path):
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["canon", "--in", str(tmp_path / "nope"), "--out", "-"])
    assert excinfo.value.code == cli.EXIT_FILE


def test_zround_success_writes_frame(tmp_path):
    data = tmp_path / "canon.txt"
    data.write_bytes("hello ".encode() * 1000)
    blob = tmp_path / "frame.zst"
    rc = cli.main(["zround", "--in", str(data), "--out", str(blob), "--level", "3"])
    assert rc == cli.EXIT_OK
    # Frame must be a plain zstd frame: magic 0xFD2FB528 little-endian.
    assert blob.read_bytes()[:4] == b"\x28\xb5\x2f\xfd"
    back = cli.decompress(blob.read_bytes(), expected_original_size=data.stat().st_size)
    assert back == data.read_bytes()


def test_zround_empty_input_ok(tmp_path):
    data = tmp_path / "empty"
    data.write_bytes(b"")
    rc = cli.main(["zround", "--in", str(data)])
    assert rc == cli.EXIT_OK


def test_usage_error_exit2():
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["nonexistent-command"])
    assert excinfo.value.code == 2


def test_no_subcommand_exit2():
    with pytest.raises(SystemExit) as excinfo:
        cli.main([])
    assert excinfo.value.code == 2


# --- pipe: end-to-end baseline flow (canonicalize -> compress -> verify) ---


def test_pipe_success_writes_frame(tmp_path):
    raw = tmp_path / "raw.txt"
    raw.write_bytes("hello \u00adworld\r\n" .encode("utf-8") * 500)
    out = tmp_path / "frame.zst"
    rc = cli.main(["pipe", "--in", str(raw), "--out", str(out), "--level", "3"])
    assert rc == cli.EXIT_OK
    assert out.read_bytes()[:4] == b"\x28\xb5\x2f\xfd"  # plain zstd frame
    # Frame decompresses to the canonical form, not the raw bytes.
    canon = cli.canonicalize(raw.read_bytes())
    back = cli.decompress(out.read_bytes(), expected_original_size=len(canon))
    assert back == canon


def test_pipe_empty_input_ok(tmp_path):
    raw = tmp_path / "empty"
    raw.write_bytes(b"")
    rc = cli.main(["pipe", "--in", str(raw)])
    assert rc == cli.EXIT_OK


def test_pipe_bad_encoding_exit4(tmp_path):
    raw = tmp_path / "raw.bin"
    raw.write_bytes(b"\x80\x81 not utf8")
    rc = cli.main(["pipe", "--in", str(raw)])
    assert rc == cli.EXIT_CANON


def test_pipe_declared_encoding_succeeds(tmp_path):
    raw = tmp_path / "latin.txt"
    raw.write_bytes("café\r\n".encode("latin-1"))
    rc = cli.main(["pipe", "--in", str(raw), "--encoding", "latin-1"])
    assert rc == cli.EXIT_OK


def test_pipe_missing_file_exit3(tmp_path):
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["pipe", "--in", str(tmp_path / "nope")])
    assert excinfo.value.code == cli.EXIT_FILE


def test_canon_meta_audit_json(tmp_path, capsys):
    """canon --meta: JSON audit to stdout, payload to --out file, NOT stdout (Session 25)."""
    import json

    raw = tmp_path / "raw.txt"
    raw.write_bytes("a\r\nb\u00adc".encode("utf-8"))
    out = tmp_path / "canon.txt"
    rc = cli.main(["canon", "--in", str(raw), "--out", str(out), "--meta"])
    assert rc == cli.EXIT_OK
    assert out.read_bytes() == b"a\nbc"
    meta = json.loads(capsys.readouterr().out)
    assert meta["canonicalizer_version"] == "lexcan-0.1"
    assert meta["applied_rules"] == ["CAN-R01", "CAN-R02", "CAN-R05"]
    assert meta["input_bytes"] == raw.stat().st_size
    assert meta["output_bytes"] == out.stat().st_size
    import hashlib
    assert meta["input_sha256"] == hashlib.sha256(raw.read_bytes()).hexdigest()
    assert meta["output_sha256"] == hashlib.sha256(b"a\nbc").hexdigest()
    assert "canonical" not in meta  # payload never leaks into the audit JSON


def test_canon_meta_stdout_payload_suppressed(tmp_path, capsys):
    """With --meta and --out -, no payload bytes go to stdout (JSON only)."""
    import json

    raw = tmp_path / "raw.txt"
    raw.write_bytes(b"hello")
    rc = cli.main(["canon", "--in", str(raw), "--out", "-", "--meta"])
    assert rc == cli.EXIT_OK
    captured = capsys.readouterr()
    meta = json.loads(captured.out)  # stdout must be parseable JSON alone
    assert meta["output_bytes"] == 5
