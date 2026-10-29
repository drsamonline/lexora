"""Tests for the streaming canonicalizer (canonicalize_stream + CLI wiring).

The contract is byte-identity with canonicalize(): the streaming reader exists to
bound memory, and it is only allowed to exist if it changes nothing about the
output. The nastiest cases are the ones that straddle a chunk boundary — a CRLF
split in two, a multi-byte UTF-8 sequence split in two, a BOM split across three
one-byte reads — so chunk_size is varied down to 1 byte.
"""

from __future__ import annotations

import io
import pathlib

import pytest

from lexora import cli
from lexora.canonicalize import (
    CanonicalizationError,
    canonicalize,
    canonicalize_stream,
    canonicalize_with_meta,
)

VECTORS = pathlib.Path(__file__).parent / "vectors" / "canonicalization"

INPUTS = {
    "empty": b"",
    "ascii": b"hello world\n",
    "crlf": b"a\r\nb\r\nc",
    "lone_cr": b"a\rb\rc",
    "trailing_cr": b"abc\r",
    "soft_hyphen": b"a\xc2\xadb",
    "cr_soft_hyphen_lf": b"a\r\xc2\xad\nb",
    "utf8_bom": b"\xef\xbb\xbfhello\r\n",
    "utf16le_bom": "\ufeffhello\r\n".encode("utf-16"),
    "utf16be_bom": "\ufeffhi\r\n".encode("utf-16-be"),
    "indic_multibyte": ("\u0915\u0916\u0917\u0918" * 200).encode(),
    "mixed": b"line1\r\nline2\rline3\xc2\xad\nline4",
    "lone_soft_hyphens": b"\xc2\xad\xc2\xad\xc2\xad",
}

CHUNKS = (1, 2, 3, 4, 5, 7, 64, 1 << 20)


def _stream(raw: bytes, chunk_size: int, **kw) -> bytes:
    out = io.BytesIO()
    canonicalize_stream(io.BytesIO(raw), out, chunk_size=chunk_size, **kw)
    return out.getvalue()


@pytest.mark.parametrize("name", sorted(INPUTS))
@pytest.mark.parametrize("chunk_size", CHUNKS)
def test_stream_matches_buffered_at_every_chunk_size(name: str, chunk_size: int) -> None:
    raw = INPUTS[name]
    assert _stream(raw, chunk_size) == canonicalize(raw)


@pytest.mark.parametrize("vector", sorted(p.name for p in VECTORS.iterdir() if p.is_dir()))
def test_stream_reproduces_every_golden_vector(vector: str) -> None:
    import json

    d = VECTORS / vector
    raw = (d / "input.bin").read_bytes()
    expected = (d / "expected_output.bin").read_bytes()
    meta = json.loads((d / "meta.json").read_text()) if (d / "meta.json").is_file() else {}
    declared = meta.get("declared_encoding")  # v005 is cp1251 by declaration
    for chunk_size in (1, 2, 3, 7, 1 << 20):
        assert _stream(raw, chunk_size, declared_encoding=declared) == expected


def test_declared_encoding_streams_identically() -> None:
    raw = b"\xcf\xf0\xe8\xe2\xe5\xf2\r\n"  # cp1251 "Привет"
    for chunk_size in (1, 2, 3, 7):
        assert _stream(raw, chunk_size, declared_encoding="cp1251") == canonicalize(
            raw, declared_encoding="cp1251"
        )


def test_meta_matches_the_buffered_audit() -> None:
    raw = INPUTS["mixed"]
    out = io.BytesIO()
    meta = canonicalize_stream(io.BytesIO(raw), out)
    buffered = canonicalize_with_meta(raw)
    assert meta["input_bytes"] == buffered["input_bytes"]
    assert meta["output_bytes"] == buffered["output_bytes"]
    assert meta["input_sha256"] == buffered["input_sha256"]
    assert meta["output_sha256"] == buffered["output_sha256"]
    assert meta["applied_rules"] == buffered["applied_rules"]
    assert "canonical" not in meta  # payload is not buffered into the audit


def test_trailing_cr_becomes_lf_at_eof() -> None:
    assert _stream(b"abc\r", 1) == b"abc\n"
    assert _stream(b"abc\r", 1 << 20) == b"abc\n"


def test_invalid_utf8_raises_the_same_error_as_buffered() -> None:
    raw = b"abc\xffdef"
    with pytest.raises(CanonicalizationError) as streamed:
        _stream(raw, 3)
    with pytest.raises(CanonicalizationError) as buffered:
        canonicalize(raw)
    assert str(streamed.value) == str(buffered.value)


def test_truncated_utf16_raises_canonicalization_error_not_a_raw_decode_error() -> None:
    """Regression: the buffered path used to leak UnicodeDecodeError here, which
    escapes the CLI handler and crashes with a traceback instead of exit 4."""
    raw = b"\xff\xfe\x00"
    with pytest.raises(CanonicalizationError):
        canonicalize(raw)
    with pytest.raises(CanonicalizationError) as streamed:
        _stream(raw, 1)
    assert "UTF-16 BOM" in str(streamed.value)


def test_chunk_size_must_be_positive() -> None:
    with pytest.raises(CanonicalizationError):
        canonicalize_stream(io.BytesIO(b"x"), io.BytesIO(), chunk_size=0)


class TestCliCanonStreaming:
    def test_default_and_no_stream_produce_identical_files(self, tmp_path) -> None:
        raw = tmp_path / "in.txt"
        raw.write_bytes(INPUTS["mixed"])
        a, b = tmp_path / "a.txt", tmp_path / "b.txt"
        assert cli.main(["canon", "--in", str(raw), "--out", str(a)]) == cli.EXIT_OK
        assert cli.main(["canon", "--in", str(raw), "--out", str(b),
                         "--no-stream"]) == cli.EXIT_OK
        assert a.read_bytes() == b.read_bytes() == canonicalize(INPUTS["mixed"])

    def test_meta_with_stdout_out_keeps_stdout_clean(self, tmp_path, capsys) -> None:
        import json

        raw = tmp_path / "in.txt"
        raw.write_bytes(INPUTS["crlf"])
        assert cli.main(["canon", "--in", str(raw), "--out", "-", "--meta"]) == cli.EXIT_OK
        meta = json.loads(capsys.readouterr().out)  # would fail if payload leaked
        assert meta["applied_rules"] == ["CAN-R01", "CAN-R02", "CAN-R05"]

    def test_meta_writes_payload_to_a_file(self, tmp_path, capsys) -> None:
        import json

        raw = tmp_path / "in.txt"
        out = tmp_path / "out.txt"
        raw.write_bytes(INPUTS["crlf"])
        assert cli.main(["canon", "--in", str(raw), "--out", str(out), "--meta"]) == cli.EXIT_OK
        assert out.read_bytes() == canonicalize(INPUTS["crlf"])
        assert json.loads(capsys.readouterr().out)["output_bytes"] == len(out.read_bytes())

    def test_missing_input_raises_systemexit_3(self, tmp_path) -> None:
        with pytest.raises(SystemExit) as exc:
            cli.main(["canon", "--in", str(tmp_path / "nope.txt"), "--out", "-"])
        assert exc.value.code == cli.EXIT_FILE

    def test_bad_encoding_exits_4_not_a_traceback(self, tmp_path) -> None:
        raw = tmp_path / "in.txt"
        raw.write_bytes(b"abc\xffdef")
        assert cli.main(["canon", "--in", str(raw), "--out", str(tmp_path / "o.txt")]) == cli.EXIT_CANON

    def test_large_input_round_trips_through_streaming(self, tmp_path) -> None:
        payload = (b"line of text\r\n" * 20_000) + b"tail\xc2\xad"
        raw = tmp_path / "in.txt"
        out = tmp_path / "out.txt"
        raw.write_bytes(payload)
        assert cli.main(["canon", "--in", str(raw), "--out", str(out)]) == cli.EXIT_OK
        assert out.read_bytes() == canonicalize(payload)
        assert b"\r" not in out.read_bytes()
