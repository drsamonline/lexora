"""Tests for the benchmark harness's system registry.

The harness is where numbers are made, so a silent drop there is worse than a crash:
Session 62 added an `xz9-lzma` system whose availability branch forgot `ok.append`,
and the system vanished from the run without appearing in `systems_run` OR
`systems_skipped`. These tests exist to make that impossible to repeat.
"""

from __future__ import annotations

import importlib.util
import pathlib
import shutil
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "benchmarks"))

import harness  # noqa: E402  (path insertion must come first)


def test_every_registered_system_is_reachable() -> None:
    """`SYSTEMS` is the registry the CLI validates against; nothing may be dead."""
    assert "lexora" in harness.SYSTEMS
    assert "lexora19" in harness.SYSTEMS
    assert "zstd19" in harness.SYSTEMS
    assert {"xz9", "xz9-lzma"} & set(harness.SYSTEMS), "no xz implementation registered"


@pytest.mark.parametrize("name", ["lexora", "lexora19", "zstd19", "xz9-lzma"])
def test_available_systems_never_drops_a_request_silently(name: str) -> None:
    """Every requested system must land in `ok` or `skipped` — never in neither.

    This is the regression test for the Session-62 bug: a branch that only recorded
    a skip reason on failure, so success produced nothing at all.
    """
    ok, skipped = harness._available_systems([name])
    assert name in ok or name in skipped, f"{name} vanished from both lists"
    assert not (name in ok and name in skipped), f"{name} is in both lists"


def test_unknown_system_is_reported_as_skipped_with_a_reason() -> None:
    ok, skipped = harness._available_systems(["no-such-system"])
    assert ok == []
    assert "not implemented" in skipped["no-such-system"]


def test_a_mixed_request_accounts_for_every_name() -> None:
    requested = ["lexora", "no-such-system", "zstd19"]
    ok, skipped = harness._available_systems(requested)
    assert set(ok) | set(skipped) == set(requested)
    assert not set(ok) & set(skipped)


def test_xz9_lzma_produces_a_real_xz_stream(tmp_path) -> None:
    """The fallback must be genuine xz, not a stand-in with a different format."""
    import lzma

    payload = b"the quick brown fox jumps over the lazy dog\n" * 200
    out = tmp_path / "a.xz"
    n = harness.SYSTEMS["xz9-lzma"](payload, out)
    assert n == out.stat().st_size > 0
    assert lzma.decompress(out.read_bytes()) == payload


def test_lexora_systems_write_archives_that_verify(tmp_path) -> None:
    """A measured 'system' must produce a real artifact, not just a byte count."""
    from lexora import container

    payload = b"system artifact check " * 200
    for name in ("lexora", "lexora19"):
        out = tmp_path / f"{name}.lxz"
        n = harness.SYSTEMS[name](payload, out)
        assert n == out.stat().st_size
        assert container.verify_archive(out.read_bytes()).ok is True
        assert container.unpack(out.read_bytes()) == payload


def test_lexora19_is_smaller_than_the_default_on_varied_text(tmp_path) -> None:
    """Level 19 must actually be the size-oriented row; if these ever tie, the
    'lexora19' registration has drifted and the R4 comparison is meaningless.

    The payload must be VARIED, not repetitive: on 35 KB of `b"..." * 400` both
    levels produced byte-identical output (278 B) because zstd's higher levels add
    nothing when every match is already maximal — the third time this project has
    been misled by unrealistically compressible input (Sessions 39, 57, here).
    """
    import random

    rng = random.Random(5)
    words = ("alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu nu "
             "xi omicron pi rho sigma tau").split()
    buf = bytearray()
    while len(buf) < 200_000:
        buf += (" ".join(rng.choice(words) for _ in range(9)) + ".\n").encode()
    payload = bytes(buf)
    default_n = harness.SYSTEMS["lexora"](payload, tmp_path / "a.lxz")
    level19_n = harness.SYSTEMS["lexora19"](payload, tmp_path / "b.lxz")
    assert level19_n < default_n
