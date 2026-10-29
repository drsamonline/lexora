"""Interruption: what survives a real signal during a pack?

The atomic-write guarantee is stated everywhere ("a crash leaves either the previous
artifact or the new one, never a hybrid") but until now it was only tested with
*simulated* failures — a destination object that raises. These tests kill a real
process mid-write with real signals.

Measured behaviour (Session 57):

  SIGINT   no destination, no debris          (KeyboardInterrupt unwinds, writers clean up)
  SIGTERM  no destination, no debris          (after this session installed a handler)
  SIGKILL  no destination, one .lxz-tmp-* left (uncatchable — debris is unavoidable)

The destination is safe in all three cases, because it is only ever created by
`os.replace` after the temp file is complete. That is the property these tests exist
to defend — especially the "existing archive survives an interrupted overwrite" case,
which is what a user actually cares about.
"""

from __future__ import annotations

import os
import pathlib
import signal
import subprocess
import sys
import time

import pytest

pytestmark = pytest.mark.skipif(
    not hasattr(signal, "SIGKILL") or os.name != "posix",
    reason="POSIX signals are required for a real interruption test",
)

REPO = pathlib.Path(__file__).resolve().parent.parent
PAYLOAD = 6 * 1024 * 1024  # ~6 s at level 19, so the kill lands mid-write


@pytest.fixture(scope="module")
def big_input(tmp_path_factory) -> pathlib.Path:
    """Built once for the module: generating the text is slower than the kill."""
    return _big_input(tmp_path_factory.mktemp("payload"))


def _big_input(tmp_path: pathlib.Path) -> pathlib.Path:
    """Varied pseudo-text, not a repeating byte pattern.

    A `bytes(range(256)) * N` payload compresses in well under a second at level 19
    (long matches everywhere), which made an earlier version of this test kill a
    process that had already finished — the test then failed for the wrong reason.
    Deterministic word soup keeps the pack busy for seconds.
    """
    src = tmp_path / "big.bin"
    if not src.exists():
        import random

        rng = random.Random(11)
        words = ("alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu "
                 "nu xi omicron pi rho sigma tau upsilon phi chi psi omega").split()
        buf = bytearray()
        while len(buf) < PAYLOAD:
            buf += (" ".join(rng.choice(words) for _ in range(9)) + ".\n").encode()
        src.write_bytes(bytes(buf[:PAYLOAD]))
    return src


def _start_pack(src: pathlib.Path, dest: pathlib.Path) -> subprocess.Popen:
    env = dict(os.environ, PYTHONPATH=str(REPO / "src"))
    return subprocess.Popen(
        [sys.executable, "-m", "lexora.cli", "pack", "--in", str(src),
         "--out", str(dest), "--level", "19"],
        env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )


def _kill_once_writing(proc: subprocess.Popen, out_dir: pathlib.Path, sig: int) -> list[str]:
    """Wait until the temp file exists (the write has begun), then deliver `sig`."""
    deadline = time.time() + 30
    while time.time() < deadline:
        if list(out_dir.glob(".lxz-tmp-*")):
            break
        if proc.poll() is not None:
            break
        time.sleep(0.02)
    time.sleep(0.3)  # let some bytes actually be written
    proc.send_signal(sig)
    try:
        proc.wait(timeout=30)
    except subprocess.TimeoutExpired:  # pragma: no cover - defensive
        proc.kill()
        proc.wait()
    return sorted(p.name for p in out_dir.iterdir())


@pytest.mark.parametrize("sig,expect_debris", [
    (signal.SIGINT, False),
    (signal.SIGTERM, False),   # handler installed in Session 57
])
def test_catchable_signals_leave_no_destination_and_no_debris(
    tmp_path, big_input, sig, expect_debris
) -> None:
    src = big_input
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    dest = out_dir / "a.lxz"

    leftovers = _kill_once_writing(_start_pack(src, dest), out_dir, sig)

    assert not dest.exists(), "a partial archive reached the destination"
    assert leftovers == [], f"debris left behind: {leftovers}"
    assert expect_debris is False  # documents the intent of the parametrisation


def test_sigkill_keeps_the_destination_safe_even_though_debris_remains(tmp_path, big_input) -> None:
    """SIGKILL cannot be caught, so a temp file may survive — but the destination
    must still be untouched, which is the guarantee that matters."""
    src = big_input
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    dest = out_dir / "a.lxz"

    leftovers = _kill_once_writing(_start_pack(src, dest), out_dir, signal.SIGKILL)

    assert not dest.exists()
    assert all(name.startswith(".lxz-tmp-") for name in leftovers), leftovers


def test_an_existing_archive_survives_an_interrupted_overwrite(tmp_path, big_input) -> None:
    """The property a user actually relies on: re-packing over an existing archive
    and being killed must leave the OLD archive intact and byte-identical."""
    src = tmp_path / "small.bin"
    src.write_bytes(b"original content " * 500)
    dest = tmp_path / "a.lxz"
    env = dict(os.environ, PYTHONPATH=str(REPO / "src"))
    assert subprocess.run(
        [sys.executable, "-m", "lexora.cli", "pack", "--in", str(src),
         "--out", str(dest), "--level", "1"],
        env=env, capture_output=True,
    ).returncode == 0
    before = dest.read_bytes()
    assert before  # sanity: there is something to preserve

    # now overwrite it, slowly, and get killed in the middle
    leftovers = _kill_once_writing(_start_pack(big_input, dest), tmp_path, signal.SIGKILL)

    assert dest.read_bytes() == before, "the previous archive was damaged"
    unexpected = {n for n in leftovers} - {"a.lxz", "small.bin", "big.bin"}
    assert all(name.startswith(".lxz-tmp-") for name in unexpected), unexpected
    # and the old archive is still a valid, verifiable archive
    from lexora import container

    assert container.verify_archive(dest.read_bytes()).ok is True
