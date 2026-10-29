"""Tests for snapshot provenance repair and checkpoint semantics.

Two invariants are load-bearing here, and both were learned from a real failure
in Session 43: a killed fetch rewrote the record with only its own partial
progress, so a 587-file directory was recorded as 232 files while every text
stayed on disk. Checkpoints must therefore be supersets, and there must be a way
back from a record that has already been truncated.
"""

from __future__ import annotations

import json
import pathlib

import pytest

from benchmarks import corpus


def _snapshot(tmp_path: pathlib.Path, *, requested, files=(), failures=()) -> pathlib.Path:
    dest = tmp_path / "snap"
    dest.mkdir()
    (tmp_path / "snap.sources.json").write_text(
        json.dumps({"requested_ids": requested, "files": list(files), "failures": list(failures)})
    )
    return dest


class TestReconcile:
    def test_recovers_records_for_texts_on_disk(self, tmp_path) -> None:
        dest = _snapshot(tmp_path, requested=[101, 202])
        (dest / "gutenberg-101.txt").write_bytes(b"first book " * 100)
        (dest / "gutenberg-202.txt").write_bytes(b"second book " * 100)

        summary = corpus.reconcile_snapshot(dest)

        assert summary["recovered"] == 2
        assert summary["already_recorded"] == 0
        assert summary["orphaned"] == 0
        snap = json.loads((tmp_path / "snap.sources.json").read_text())
        assert [f["file"] for f in snap["files"]] == ["gutenberg-101.txt", "gutenberg-202.txt"]
        assert all(f["reconciled"] is True for f in snap["files"])
        # sha256 comes from the bytes on disk, not from anything remembered
        assert snap["files"][0]["sha256"] == corpus.sha256_bytes(b"first book " * 100)
        lineage = json.loads((tmp_path / "snap.lineage.json").read_text())
        assert lineage["gutenberg-101.txt"] == "gutenberg:101"

    def test_is_idempotent(self, tmp_path) -> None:
        dest = _snapshot(tmp_path, requested=[101])
        (dest / "gutenberg-101.txt").write_bytes(b"book " * 50)
        first = corpus.reconcile_snapshot(dest)
        second = corpus.reconcile_snapshot(dest)
        assert first["recovered"] == 1
        assert second["recovered"] == 0
        assert second["already_recorded"] == 1

    def test_orphans_are_counted_but_not_claimed(self, tmp_path) -> None:
        """A text whose id is outside the requested set must not become corpus."""
        dest = _snapshot(tmp_path, requested=[101])
        (dest / "gutenberg-101.txt").write_bytes(b"wanted " * 50)
        (dest / "gutenberg-999.txt").write_bytes(b"not requested " * 50)

        summary = corpus.reconcile_snapshot(dest)

        assert summary["orphaned"] == 1
        assert summary["files"] == 1
        snap = json.loads((tmp_path / "snap.sources.json").read_text())
        assert [f["file"] for f in snap["files"]] == ["gutenberg-101.txt"]

    def test_records_are_sorted_for_byte_stability(self, tmp_path) -> None:
        dest = _snapshot(tmp_path, requested=[303, 101, 202])
        for pg_id in (303, 101, 202):
            (dest / f"gutenberg-{pg_id}.txt").write_bytes(b"x" * 100)
        corpus.reconcile_snapshot(dest)
        first = (tmp_path / "snap.sources.json").read_text()
        corpus.reconcile_snapshot(dest)
        assert (tmp_path / "snap.sources.json").read_text() == first


class TestCheckpointSuperset:
    """A checkpoint may add to the record; it must never shrink it."""

    def test_prior_records_survive_a_shorter_run(self, tmp_path, monkeypatch) -> None:
        dest = tmp_path / "snap"
        monkeypatch.setattr(corpus, "_fetch_one", lambda pg_id, timeout=60.0: b"text " * 200)

        first = corpus.fetch_gutenberg_snapshot(dest, ids=(11, 12), min_mb=0.0)
        assert len(first["files"]) == 2

        # Second invocation covers only id 11. Id 12's text is still on disk and
        # still recorded: the record is a superset, not a snapshot of this run.
        second = corpus.fetch_gutenberg_snapshot(dest, ids=(11,), min_mb=0.0)
        assert [f["file"] for f in second["files"]] == ["gutenberg-11.txt", "gutenberg-12.txt"]
        assert (dest / "gutenberg-12.txt").is_file()

    def test_a_failure_removes_the_stale_record_for_that_file(self, tmp_path, monkeypatch) -> None:
        dest = tmp_path / "snap"
        monkeypatch.setattr(corpus, "_fetch_one", lambda pg_id, timeout=60.0: b"text " * 200)
        corpus.fetch_gutenberg_snapshot(dest, ids=(21,), min_mb=0.0)

        # The file is gone from disk and the network now errors: the record must
        # stop claiming it, otherwise the manifest would cite a file that is not
        # there.
        (dest / "gutenberg-21.txt").unlink()

        def _boom(pg_id, timeout=60.0):
            raise OSError("connection reset")

        monkeypatch.setattr(corpus, "_fetch_one", _boom)
        snap = corpus.fetch_gutenberg_snapshot(dest, ids=(21,), min_mb=0.0)
        assert snap["files"] == []
        assert [f["file"] for f in snap["failures"]] == ["gutenberg-21.txt"]


def test_sidecar_writer_is_the_single_source_of_truth(tmp_path) -> None:
    dest = tmp_path / "snap"
    dest.mkdir()
    snap = corpus._write_snapshot_sidecars(
        dest, [1], {"gutenberg-1.txt": {"file": "gutenberg-1.txt", "sha256": "0" * 64,
                                       "size_bytes": 3, "source_url": "u"}},
        {}, {"gutenberg-1.txt": "gutenberg:1"}, {"gutenberg-1.txt": {"rights": "P0"}},
        {"method": "test"},
    )
    assert snap["complete"] is True
    assert snap["selection"] == {"method": "test"}
    assert json.loads((tmp_path / "snap.sources.json").read_text())["files"][0]["size_bytes"] == 3
