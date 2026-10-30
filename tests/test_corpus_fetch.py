"""Tests for the fetcher's resume economics (Session 65).

The grind to the ≥1 GiB gate exposed three costs that each looked like "the network
is slow" and were none of them: re-hashing the whole corpus every pass, re-running
language detection on every reused file, and re-attempting every recorded failure.
Together they turned a pass that should fetch ~90 files into one that fetched 22.
These tests pin the behaviour so it cannot regress silently.
"""

from __future__ import annotations

import hashlib
import pathlib

import pytest

from benchmarks import corpus


@pytest.fixture()
def fake_fetch(monkeypatch):
    """Count fetches and serve deterministic payloads, so no network is touched."""
    calls: list[int] = []

    def _fake(pg_id: int, timeout: float = 60.0) -> bytes:
        calls.append(pg_id)
        if pg_id == 404:
            raise corpus.urllib.error.HTTPError("u", 404, "Not Found", None, None)
        return (f"work {pg_id} " * 200).encode()

    monkeypatch.setattr(corpus, "_fetch_one", _fake)
    return calls


def test_known_failures_are_not_retried_by_default(tmp_path, fake_fetch) -> None:
    ids = (404, 1)
    first = corpus.fetch_gutenberg_snapshot(tmp_path / "s", ids=ids, min_mb=0.0)
    assert [f["file"] for f in first["failures"]] == ["gutenberg-404.txt"]
    assert fake_fetch == [404, 1]

    fake_fetch.clear()
    corpus.fetch_gutenberg_snapshot(tmp_path / "s", ids=ids, min_mb=0.0)
    assert fake_fetch == [], "a recorded failure was re-attempted without --retry-failed"

    corpus.fetch_gutenberg_snapshot(tmp_path / "s", ids=ids, min_mb=0.0, retry_failed=True)
    assert fake_fetch == [404], "--retry-failed must re-attempt recorded failures"


def test_reuse_trusts_size_and_mtime_instead_of_rehashing(tmp_path, fake_fetch, monkeypatch) -> None:
    snap_dir = tmp_path / "s"
    corpus.fetch_gutenberg_snapshot(snap_dir, ids=(7,), min_mb=0.0)

    hashed: list[pathlib.Path] = []
    real = corpus.sha256_bytes

    def _counting_sha(data: bytes) -> str:
        hashed.append(data)
        return real(data)

    monkeypatch.setattr(corpus, "sha256_bytes", _counting_sha)
    corpus.fetch_gutenberg_snapshot(snap_dir, ids=(7,), min_mb=0.0)
    assert hashed == [], "a file whose size and mtime are unchanged was re-hashed"

    # touching the file invalidates the shortcut, and the hash must then match.
    # The mtime is set explicitly: a rewrite can land inside the filesystem's mtime
    # granularity, which made this assertion flaky when the suite ran in one process.
    import os
    import time

    p = snap_dir / "gutenberg-7.txt"
    p.write_bytes(p.read_bytes())
    bumped = time.time_ns() + 1_000_000
    os.utime(p, ns=(bumped, bumped))
    corpus.fetch_gutenberg_snapshot(snap_dir, ids=(7,), min_mb=0.0)
    assert len(hashed) == 1, "a rewritten file must be re-hashed"


def test_reuse_preserves_recorded_metadata(tmp_path, fake_fetch, monkeypatch) -> None:
    snap_dir = tmp_path / "s"
    corpus.fetch_gutenberg_snapshot(snap_dir, ids=(9,), min_mb=0.0)
    before = (snap_dir.parent / "s.meta.json").read_text()

    def _boom(data: bytes) -> str:
        raise AssertionError("detect_language must not run for a reused file")

    monkeypatch.setattr(corpus, "detect_language", _boom)
    corpus.fetch_gutenberg_snapshot(snap_dir, ids=(9,), min_mb=0.0)
    assert (snap_dir.parent / "s.meta.json").read_text() == before


def test_sidecar_records_mtime_for_the_reuse_shortcut(tmp_path, fake_fetch) -> None:
    snap = corpus.fetch_gutenberg_snapshot(tmp_path / "s", ids=(3,), min_mb=0.0)
    entry = snap["files"][0]
    assert entry["mtime_ns"] == (tmp_path / "s" / entry["file"]).stat().st_mtime_ns
    assert entry["sha256"] == hashlib.sha256((tmp_path / "s" / entry["file"]).read_bytes()).hexdigest()
