"""Tests for `lexora verify` — structural + per-block audit without payload output.

Two things are being defended here beyond correctness:

  * **Best-effort per-block reporting.** An audit should tell you how much of an
    archive is salvageable, so one bad block must not hide the state of the rest.
  * **One pass, one block of memory.** verify_archive() used to call
    unpack(only_block=i) per block, and unpack re-reads the whole archive on
    every call — O(blocks) full passes. A counting reader pins the new behaviour.
"""

from __future__ import annotations

import io
import json
import pathlib

import pytest

from lexora import cli, container
from lexora.container import ContainerError, pack, verify_archive, verify_stream


def _arc(data: bytes, block_size: int = 4096) -> bytes:
    return pack(data, block_size=block_size)


class _CountingReader(io.BytesIO):
    """BytesIO that records how many bytes were pulled through read()."""

    def __init__(self, data: bytes) -> None:
        super().__init__(data)
        self.bytes_read = 0

    def read(self, n: int = -1) -> bytes:  # type: ignore[override]
        out = super().read(n)
        self.bytes_read += len(out)
        return out


def test_good_archive_verifies() -> None:
    result = verify_stream(io.BytesIO(_arc(b"verify me " * 2000)))
    assert result.ok is True
    assert result.error is None
    assert result.block_count == len(result.blocks)
    assert all(ok for _, ok, _ in result.blocks)


def test_verify_matches_verify_archive_on_the_same_bytes() -> None:
    good = _arc(b"parity check " * 1000)
    for archive in (good, good[: len(good) // 2]):
        a = verify_archive(archive)
        b = verify_stream(io.BytesIO(archive))
        assert (a.ok, a.error, a.block_count) == (b.ok, b.error, b.block_count)
        assert a.blocks == b.blocks


def test_corrupt_block_is_reported_without_hiding_the_healthy_ones() -> None:
    data = bytes(range(256)) * 64  # 16 KiB -> 4 blocks at 4096
    archive = bytearray(_arc(data))
    info, _, _ = container.read_index(archive)
    target = info.blocks[1]
    archive[target.offset + 4] ^= 0xFF  # inside block 1's frame, past the magic

    result = verify_stream(io.BytesIO(bytes(archive)))

    assert result.ok is False
    failed = {i for i, ok, _ in result.blocks if not ok}
    assert failed == {1}
    # every other block still reports OK: an audit wants the salvageable part
    assert sum(1 for _, ok, _ in result.blocks if ok) == len(info.blocks) - 1


def test_corrupt_header_is_a_refusal_not_a_block_failure() -> None:
    archive = bytearray(_arc(b"header integrity " * 100))
    archive[20] ^= 0xFF  # inside the checksummed header region
    result = verify_stream(io.BytesIO(bytes(archive)))
    assert result.ok is False
    assert result.error is not None and "E-FMT-HEAD-004" in result.error
    assert result.block_count == 0
    assert result.blocks == ()
    # the code is not printed twice
    assert result.error.count("E-FMT-HEAD-004") == 1


def test_truncated_archive_is_refused() -> None:
    archive = _arc(b"truncate " * 500)
    result = verify_stream(io.BytesIO(archive[: len(archive) // 2]))
    assert result.ok is False
    assert result.error is not None


def test_only_block_checks_just_that_block() -> None:
    data = bytes(range(256)) * 64
    archive = bytearray(_arc(data))
    info, _, _ = container.read_index(archive)
    archive[info.blocks[0].offset + 4] ^= 0xFF

    assert verify_stream(io.BytesIO(bytes(archive)), only_block=0).ok is False
    assert verify_stream(io.BytesIO(bytes(archive)), only_block=2).ok is True


def test_only_block_out_of_range_is_reported() -> None:
    result = verify_stream(io.BytesIO(_arc(b"small", block_size=1024)), only_block=9)
    assert result.ok is False
    assert "E-FMT-IDX-006" in (result.error or "")


def test_verification_reads_each_block_once() -> None:
    """Guards the O(blocks) regression: bytes pulled through read() must stay
    close to the archive size, not a multiple of it."""
    data = bytes((i * 7) % 251 for i in range(40_000))  # 10 blocks at 4096
    archive = _arc(data)
    reader = _CountingReader(archive)
    assert verify_stream(reader).ok is True
    # header + trailer + index are read twice at most (validate, then use);
    # blocks are read exactly once each.
    assert reader.bytes_read < len(archive) * 1.5


def test_non_seekable_source_is_refused() -> None:
    class _NoSeek:
        def read(self, n=-1):
            return b""

    result = verify_stream(_NoSeek())
    assert result.ok is False
    assert "E-USAGE-004" in (result.error or "")


class TestCliVerify:
    def _make(self, tmp_path, data: bytes) -> pathlib.Path:
        src = tmp_path / "in.bin"
        src.write_bytes(data)
        arc = tmp_path / "a.lxz"
        assert cli.main(["pack", "--in", str(src), "--out", str(arc),
                         "--level", "1", "--block-size", "4096"]) == 0
        return arc

    def test_good_archive_exit_zero_and_writes_nothing(self, tmp_path, capsys) -> None:
        arc = self._make(tmp_path, b"cli verify " * 1000)
        before = sorted(p.name for p in tmp_path.iterdir())
        assert cli.main(["verify", "--in", str(arc)]) == cli.EXIT_OK
        captured = capsys.readouterr()
        assert "verified=yes" in captured.err
        assert captured.out == ""  # no payload, no JSON without --json
        assert sorted(p.name for p in tmp_path.iterdir()) == before

    def test_corrupt_archive_exit_7(self, tmp_path, capsys) -> None:
        arc = self._make(tmp_path, bytes(range(256)) * 64)
        raw = bytearray(arc.read_bytes())
        info, _, _ = container.read_index(raw)
        raw[info.blocks[1].offset + 4] ^= 0xFF
        arc.write_bytes(bytes(raw))
        assert cli.main(["verify", "--in", str(arc)]) == cli.EXIT_CONTAINER
        assert "FAILED" in capsys.readouterr().err

    def test_json_report_shape(self, tmp_path, capsys) -> None:
        arc = self._make(tmp_path, bytes(range(256)) * 64)
        raw = bytearray(arc.read_bytes())
        info, _, _ = container.read_index(raw)
        raw[info.blocks[1].offset + 4] ^= 0xFF
        arc.write_bytes(bytes(raw))

        assert cli.main(["verify", "--in", str(arc), "--json"]) == cli.EXIT_CONTAINER
        report = json.loads(capsys.readouterr().out)
        assert report["ok"] is False
        assert report["failed"] == [{"index": 1, "code": report["failed"][0]["code"]}]
        assert report["block_count"] == len(info.blocks)
        assert report["checked"] == list(range(len(info.blocks)))

    def test_missing_file_exits_3(self, tmp_path) -> None:
        with pytest.raises(SystemExit) as exc:
            cli.main(["verify", "--in", str(tmp_path / "nope.lxz")])
        assert exc.value.code == cli.EXIT_FILE
