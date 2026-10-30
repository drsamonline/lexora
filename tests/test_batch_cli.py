"""Tests for `lexora batch` — many files in one invocation.

The batch verb is the core the GUI's queue needs, so the properties that matter
are the ones a queue needs: deterministic ordering, per-file results instead of a
first-error abort, streaming per file (one document resident, not all of them),
preserved directory structure, and no half-written artifact left behind when a
file fails.
"""

from __future__ import annotations

import json
import pathlib

import pytest

from lexora import cli, container
from lexora.canonicalize import canonicalize


def _tree(root: pathlib.Path) -> pathlib.Path:
    (root / "sub").mkdir(parents=True)
    (root / "a.txt").write_bytes(b"alpha\r\nbeta\r\n")
    (root / "sub" / "b.txt").write_bytes(b"gamma\rdelta\n")
    return root


class TestCanonBatch:
    def test_processes_a_tree_and_preserves_structure(self, tmp_path) -> None:
        src = _tree(tmp_path / "in")
        out = tmp_path / "out"
        assert cli.main(["batch", "--in", str(src), "--out-dir", str(out)]) == cli.EXIT_OK
        assert (out / "a.txt.canon").read_bytes() == canonicalize(b"alpha\r\nbeta\r\n")
        assert (out / "sub" / "b.txt.canon").read_bytes() == canonicalize(b"gamma\rdelta\n")

    def test_a_failing_file_does_not_stop_the_batch(self, tmp_path, capsys) -> None:
        src = _tree(tmp_path / "in")
        (src / "sub" / "bad.txt").write_bytes(b"bad \xff bytes\n")
        out = tmp_path / "out"

        rc = cli.main(["batch", "--in", str(src), "--out-dir", str(out), "--json"])

        assert rc == cli.EXIT_PARTIAL  # 1: completed, but not everything worked
        report = json.loads(capsys.readouterr().out)
        by_input = {r["input"]: r for r in report["results"]}
        assert by_input["a.txt"]["ok"] is True
        assert by_input["sub/b.txt"]["ok"] is True
        assert by_input["sub/bad.txt"]["ok"] is False
        assert by_input["sub/bad.txt"]["code"] == "E-CAN"
        assert report["files_ok"] == 2 and report["files_failed"] == 1
        # a failed file leaves no artifact behind
        assert not (out / "sub" / "bad.txt.canon").exists()

    def test_stop_on_error_returns_the_files_own_code(self, tmp_path) -> None:
        src = _tree(tmp_path / "in")
        (src / "a_bad.txt").write_bytes(b"\xff")
        rc = cli.main(["batch", "--in", str(src), "--out-dir", str(tmp_path / "o"),
                       "--stop-on-error"])
        assert rc == cli.EXIT_CANON

    def test_report_file_matches_stdout_report(self, tmp_path, capsys) -> None:
        src = _tree(tmp_path / "in")
        report_path = tmp_path / "report.json"
        assert cli.main(["batch", "--in", str(src), "--out-dir", str(tmp_path / "o"),
                         "--json", "--report", str(report_path)]) == cli.EXIT_OK
        printed = json.loads(capsys.readouterr().out)
        assert json.loads(report_path.read_text()) == printed
        assert printed["files_matched"] == 2
        assert printed["input_bytes_total"] == 25  # 13 + 12 bytes of input
        assert [r["input"] for r in printed["results"]] == ["a.txt", "sub/b.txt"]  # sorted

    def test_pattern_filters_and_no_match_is_a_usage_error(self, tmp_path) -> None:
        src = _tree(tmp_path / "in")
        assert cli.main(["batch", "--in", str(src), "--out-dir", str(tmp_path / "o1"),
                         "--pattern", "*.md"]) == 2
        assert cli.main(["batch", "--in", str(src), "--out-dir", str(tmp_path / "o2"),
                         "--pattern", "*.txt"]) == cli.EXIT_OK
        assert not (tmp_path / "o2" / "a.txt.md").exists()

    def test_declared_encoding_applies_to_the_batch(self, tmp_path) -> None:
        src = tmp_path / "in"
        src.mkdir()
        (src / "cp.txt").write_bytes(b"\xcf\xf0\xe8\xe2\xe5\xf2\r\n")
        out = tmp_path / "out"
        assert cli.main(["batch", "--in", str(src), "--out-dir", str(out),
                         "--encoding", "cp1251"]) == cli.EXIT_OK
        assert (out / "cp.txt.canon").read_bytes() == canonicalize(
            b"\xcf\xf0\xe8\xe2\xe5\xf2\r\n", declared_encoding="cp1251"
        )


class TestPackBatch:
    def test_pack_batch_produces_verifiable_archives(self, tmp_path) -> None:
        src = _tree(tmp_path / "in")
        out = tmp_path / "packed"
        assert cli.main(["batch", "--in", str(src), "--out-dir", str(out),
                         "--op", "pack", "--level", "1"]) == cli.EXIT_OK
        archives = sorted(out.rglob("*.lxz"))
        assert [p.relative_to(out).as_posix() for p in archives] == [
            "a.txt.lxz", "sub/b.txt.lxz"
        ]
        for arc in archives:
            with open(arc, "rb") as fh:
                assert container.verify_stream(fh).ok is True
        # and the bytes round-trip
        with open(archives[0], "rb") as fh:
            info, written = container.unpack_stream(fh, __import__("io").BytesIO())
        assert written == len(b"alpha\r\nbeta\r\n")

    def test_custom_suffix(self, tmp_path) -> None:
        src = _tree(tmp_path / "in")
        out = tmp_path / "o"
        assert cli.main(["batch", "--in", str(src), "--out-dir", str(out),
                         "--suffix", ".bak"]) == cli.EXIT_OK
        assert (out / "a.txt.bak").is_file()

    def test_single_file_input(self, tmp_path) -> None:
        one = tmp_path / "one.txt"
        one.write_bytes(b"single\r\n")
        out = tmp_path / "o"
        assert cli.main(["batch", "--in", str(one), "--out-dir", str(out)]) == cli.EXIT_OK
        assert (out / "one.txt.canon").read_bytes() == b"single\n"


class TestBatchUsage:
    def test_missing_input_exits_3(self, tmp_path) -> None:
        assert cli.main(["batch", "--in", str(tmp_path / "nope"),
                         "--out-dir", str(tmp_path / "o")]) == cli.EXIT_FILE

    def test_bad_block_size_exits_2(self, tmp_path) -> None:
        src = _tree(tmp_path / "in")
        assert cli.main(["batch", "--in", str(src), "--out-dir", str(tmp_path / "o"),
                         "--block-size", "0"]) == 2

    def test_output_dir_is_created(self, tmp_path) -> None:
        src = _tree(tmp_path / "in")
        out = tmp_path / "deep" / "nested" / "out"
        assert cli.main(["batch", "--in", str(src), "--out-dir", str(out)]) == cli.EXIT_OK
        assert (out / "a.txt.canon").is_file()


class TestUnpackBatch:
    """The symmetric gap: batch could canon and pack but not decode. A round trip
    must return the tree it started from, byte for byte."""

    def _pipeline(self, tmp_path) -> tuple[pathlib.Path, pathlib.Path, pathlib.Path]:
        src = _tree(tmp_path / "in")
        canon = tmp_path / "canon"
        packed = tmp_path / "packed"
        assert cli.main(["batch", "--in", str(src), "--out-dir", str(canon)]) == cli.EXIT_OK
        assert cli.main(["batch", "--in", str(canon), "--out-dir", str(packed),
                         "--op", "pack", "--level", "1"]) == cli.EXIT_OK
        return src, canon, packed

    def test_round_trip_returns_the_canonical_tree(self, tmp_path) -> None:
        _src, canon, packed = self._pipeline(tmp_path)
        back = tmp_path / "back"
        assert cli.main(["batch", "--in", str(packed), "--out-dir", str(back),
                         "--op", "unpack"]) == cli.EXIT_OK
        # unpack strips ".lxz", so the names match the canonical stage exactly
        for rel in ("a.txt.canon", "sub/b.txt.canon"):
            assert (back / rel).read_bytes() == (canon / rel).read_bytes()

    def test_report_records_blocks_and_sizes(self, tmp_path, capsys) -> None:
        _src, _canon, packed = self._pipeline(tmp_path)
        assert cli.main(["batch", "--in", str(packed), "--out-dir", str(tmp_path / "b"),
                         "--op", "unpack", "--json"]) == cli.EXIT_OK
        report = json.loads(capsys.readouterr().out)
        assert report["op"] == "unpack"
        assert report["files_ok"] == 2
        assert all(r["blocks"] >= 1 for r in report["results"])
        assert report["output_bytes_total"] > 0

    def test_a_corrupt_archive_fails_alone(self, tmp_path, capsys) -> None:
        _src, _canon, packed = self._pipeline(tmp_path)
        raw = bytearray((packed / "a.txt.canon.lxz").read_bytes())
        raw[20] ^= 0xFF
        (packed / "zz-broken.lxz").write_bytes(bytes(raw))
        out = tmp_path / "back"

        rc = cli.main(["batch", "--in", str(packed), "--out-dir", str(out),
                       "--op", "unpack", "--json"])

        assert rc == cli.EXIT_PARTIAL
        report = json.loads(capsys.readouterr().out)
        assert report["files_ok"] == 2 and report["files_failed"] == 1
        broken = next(r for r in report["results"] if r["input"] == "zz-broken.lxz")
        assert broken["code"] == "E-FMT-HEAD-004"
        assert not (out / "zz-broken").exists()  # no output for a refused archive
        assert (out / "a.txt.canon").is_file()   # healthy neighbours still decoded

    def test_custom_suffix_applies_to_unpack_too(self, tmp_path) -> None:
        _src, _canon, packed = self._pipeline(tmp_path)
        out = tmp_path / "suffixed"
        assert cli.main(["batch", "--in", str(packed), "--out-dir", str(out),
                         "--op", "unpack", "--suffix", ".txt"]) == cli.EXIT_OK
        assert (out / "a.txt.canon.lxz.txt").is_file()


class TestBatchJobs:
    """`--jobs N` may change the wall clock, never the answer.

    Compression releases the GIL inside zstandard, so a thread pool is real
    parallelism for a pack batch — but the report and every artifact must be
    byte-identical to a sequential run, or the flag would silently change results.
    """

    def _tree(self, tmp_path) -> pathlib.Path:
        root = tmp_path / "in"
        (root / "sub").mkdir(parents=True)
        for i in range(6):
            (root / f"f{i}.txt").write_bytes((f"document {i} " * 300).encode())
        (root / "sub" / "nested.txt").write_bytes(b"nested document " * 200)
        return root

    @pytest.mark.parametrize("op", ["canon", "pack"])
    def test_report_and_artifacts_match_a_sequential_run(self, tmp_path, op) -> None:
        root = self._tree(tmp_path)
        seq, par = tmp_path / "seq", tmp_path / "par"
        common = ["--op", op, "--level", "3", "--json"]

        assert cli.main(["batch", "--in", str(root), "--out-dir", str(seq)] + common) == 0
        assert cli.main(["batch", "--in", str(root), "--out-dir", str(par), "--jobs", "4"] + common) == 0

        # artifacts: byte-identical tree
        seq_files = sorted(p.relative_to(seq) for p in seq.rglob("*") if p.is_file())
        par_files = sorted(p.relative_to(par) for p in par.rglob("*") if p.is_file())
        assert seq_files == par_files
        for rel in seq_files:
            assert (seq / rel).read_bytes() == (par / rel).read_bytes(), rel

    def test_results_stay_in_input_order_with_many_jobs(self, tmp_path, capsys) -> None:
        root = self._tree(tmp_path)
        assert cli.main(["batch", "--in", str(root), "--out-dir", str(tmp_path / "o"),
                         "--jobs", "6", "--json"]) == 0
        report = json.loads(capsys.readouterr().out)
        inputs = [r["input"] for r in report["results"]]
        assert inputs == sorted(inputs), "parallel completion order leaked into the report"
        assert report["files_ok"] == report["files_matched"] == len(inputs)

    def test_one_bad_file_still_fails_alone_under_jobs(self, tmp_path, capsys) -> None:
        root = self._tree(tmp_path)
        (root / "zz-bad.txt").write_bytes(b"bad \xff bytes\n")  # invalid UTF-8
        rc = cli.main(["batch", "--in", str(root), "--out-dir", str(tmp_path / "o"),
                       "--jobs", "4", "--json"])
        assert rc == cli.EXIT_PARTIAL
        report = json.loads(capsys.readouterr().out)
        bad = next(r for r in report["results"] if r["input"] == "zz-bad.txt")
        assert bad["ok"] is False and bad["code"] == "E-CAN"
        assert report["files_failed"] == 1
        assert not (tmp_path / "o" / "zz-bad.txt.canon").exists()

    def test_stop_on_error_still_returns_the_failing_code(self, tmp_path) -> None:
        root = self._tree(tmp_path)
        (root / "zz-bad.txt").write_bytes(b"bad \xff bytes\n")
        rc = cli.main(["batch", "--in", str(root), "--out-dir", str(tmp_path / "o"),
                       "--jobs", "2", "--stop-on-error"])
        assert rc == cli.EXIT_CANON

    def test_default_is_still_sequential(self, tmp_path) -> None:
        parser = cli.build_parser()
        args = parser.parse_args(["batch", "--in", "x", "--out-dir", "y"])
        assert args.jobs == 1, "parallelism must be opt-in"
