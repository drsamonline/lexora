"""Tests for archive inspection (lexora.inspect + the `inspect` subcommand).

The value here is arithmetic honesty, not decoration: the container makes an exact
promise that header + Σ frames + index + trailer equals the file length
(REQ-CMP-004 instantiated for `.lxz` v0), and a person reading the report should
be able to see that promise hold or break. The block table and the integrity line
are secondary to that.
"""

from __future__ import annotations

import io
import json
import pathlib

import pytest

from lexora import cli, container
from lexora.inspect import format_report, summarize


def _arc(data: bytes, block_size: int = 4096) -> bytes:
    return container.pack(data, block_size=block_size)


def test_summary_reports_structure_and_closes_the_accounting() -> None:
    data = b"inspection target " * 1000  # 18 KB -> 5 blocks at 4096
    archive = _arc(data)
    s = summarize(io.BytesIO(archive))

    assert s["format"] == "LXZ-0.1"
    assert s["block_count"] == len(s["blocks"]) == 5
    assert s["archive_bytes"] == len(archive)
    assert s["total_uncompressed_bytes"] == len(data)
    assert s["accounting"]["ok"] is True
    assert s["accounting"]["accounted_bytes"] == s["accounting"]["actual_bytes"] == len(archive)
    # the identity spelled out: header + frames + index + trailer
    assert (container.HEADER_SIZE + s["total_compressed_bytes"]
            + s["overhead"]["index_bytes"] + container.TRAILER_SIZE) == len(archive)


def test_overhead_matches_the_format_constants() -> None:
    s = summarize(io.BytesIO(_arc(b"x" * 10_000, block_size=4096)))
    ov = s["overhead"]
    assert ov["header_bytes"] == container.HEADER_SIZE == 128
    assert ov["trailer_bytes"] == container.TRAILER_SIZE == 40
    assert ov["index_bytes_per_block"] == container.INDEX_ENTRY_SIZE == 56
    assert ov["index_bytes"] == s["block_count"] * 56
    assert ov["total_bytes"] == 128 + 40 + ov["index_bytes"]


def test_block_rows_are_contiguous_and_carry_a_digest() -> None:
    s = summarize(io.BytesIO(_arc(b"block rows " * 2000, block_size=8192)))
    offsets = [r["offset"] for r in s["blocks"]]
    assert offsets == sorted(offsets)
    assert all(len(r["sha256"]) == 64 for r in s["blocks"])
    assert sum(r["compressed_bytes"] for r in s["blocks"]) == s["total_compressed_bytes"]


def test_verify_flag_marks_a_healthy_archive() -> None:
    s = summarize(io.BytesIO(_arc(b"healthy " * 500)), verify=True)
    assert s["verified"] is True
    assert s["failed_blocks"] == []


def test_verify_flag_reports_the_failing_block_index() -> None:
    raw = bytearray(_arc(bytes(range(256)) * 64))  # 4 blocks
    info, _, _ = container.read_index(raw)
    raw[info.blocks[2].offset + 4] ^= 0xFF
    s = summarize(io.BytesIO(bytes(raw)), verify=True)
    assert s["verified"] is False
    assert [f["index"] for f in s["failed_blocks"]] == [2]


def test_structure_alone_does_not_claim_integrity() -> None:
    s = summarize(io.BytesIO(_arc(b"structure only " * 100)))
    assert s["verified"] is None  # "not checked", not "passed"
    assert "not checked" in format_report(s)


def test_report_elides_a_long_block_table() -> None:
    data = bytes(range(256)) * 200  # 51 KB -> 13 blocks at 4096
    s = summarize(io.BytesIO(_arc(data)))
    text = format_report(s, max_blocks=5)
    rows = [ln for ln in text.splitlines() if ln.rstrip().endswith("…")]
    assert len(rows) == 5  # exactly max_blocks rows, each ending with the elided digest
    assert "8 more block(s) not shown" in text
    assert "--blocks N" in text


def test_report_states_a_broken_accounting_identity() -> None:
    s = summarize(io.BytesIO(_arc(b"accounting " * 100)))
    s["accounting"]["ok"] = False  # simulate the mismatch the report must surface
    assert "MISMATCH" in format_report(s)


class TestCliInspect:
    def _make(self, tmp_path, data: bytes) -> pathlib.Path:
        src = tmp_path / "in.bin"
        src.write_bytes(data)
        arc = tmp_path / "a.lxz"
        assert cli.main(["pack", "--in", str(src), "--out", str(arc),
                         "--level", "1", "--block-size", "4096"]) == 0
        return arc

    def test_text_report_on_a_good_archive(self, tmp_path, capsys) -> None:
        arc = self._make(tmp_path, b"cli inspect " * 1000)
        assert cli.main(["inspect", "--in", str(arc)]) == cli.EXIT_OK
        out = capsys.readouterr().out
        assert "LXZ-0.1" in out and "accounting: OK" in out and "not checked" in out

    def test_verify_flag_and_exit_code_on_corruption(self, tmp_path, capsys) -> None:
        arc = self._make(tmp_path, bytes(range(256)) * 64)
        raw = bytearray(arc.read_bytes())
        info, _, _ = container.read_index(raw)
        raw[info.blocks[1].offset + 4] ^= 0xFF
        arc.write_bytes(bytes(raw))
        assert cli.main(["inspect", "--in", str(arc), "--verify"]) == cli.EXIT_CONTAINER
        assert "FAILED" in capsys.readouterr().out

    def test_json_matches_the_library_summary(self, tmp_path, capsys) -> None:
        arc = self._make(tmp_path, b"json parity " * 500)
        assert cli.main(["inspect", "--in", str(arc), "--json"]) == cli.EXIT_OK
        printed = json.loads(capsys.readouterr().out)
        direct = summarize(io.BytesIO(arc.read_bytes()))
        assert printed == direct

    def test_blocks_flag_hides_the_table(self, tmp_path, capsys) -> None:
        arc = self._make(tmp_path, b"hide the table " * 500)
        assert cli.main(["inspect", "--in", str(arc), "--blocks", "0"]) == cli.EXIT_OK
        out = capsys.readouterr().out
        assert "sha256" not in out  # header row of the block table

    def test_missing_file_exits_3(self, tmp_path) -> None:
        with pytest.raises(SystemExit) as exc:
            cli.main(["inspect", "--in", str(tmp_path / "nope.lxz")])
        assert exc.value.code == cli.EXIT_FILE

    def test_corrupt_header_is_a_refusal(self, tmp_path, capsys) -> None:
        arc = self._make(tmp_path, b"bad header " * 100)
        raw = bytearray(arc.read_bytes())
        raw[20] ^= 0xFF
        arc.write_bytes(bytes(raw))
        assert cli.main(["inspect", "--in", str(arc)]) == cli.EXIT_CONTAINER
        assert "refusal" in capsys.readouterr().err
