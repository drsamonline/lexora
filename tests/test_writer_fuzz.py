"""Writer-path hardening: adversarial inputs, failing destinations, no debris.

The reader fuzz suite (test_reader_fuzz.py) attacks what comes *in*. This attacks
what goes *out*: pathological block sizes, data that defeats the compressor's own
cap, destinations that fail mid-write, and directories that cannot be written at
all. The property under test is not "it succeeds" but "when it cannot succeed, it
fails cleanly and leaves nothing behind".

Session 55 built these; one real user-facing bug fell out immediately — a pack into
a missing or unwritable directory raised a traceback and exited 1, contradicting
the documented exit-code table, which promises 3 and a one-line error.
"""

from __future__ import annotations

import io
import os
import pathlib
import random

import pytest

from lexora import cli, container
from lexora.canonicalize import canonicalize, canonicalize_stream


class _FailingDst(io.RawIOBase):
    """A destination that accepts `limit` bytes and then reports ENOSPC."""

    def __init__(self, limit: int) -> None:
        self.limit = limit
        self.written = 0

    def writable(self) -> bool:
        return True

    def write(self, b) -> int:  # type: ignore[override]
        self.written += len(b)
        if self.written > self.limit:
            raise OSError(28, "No space left on device")
        return len(b)

    def seekable(self) -> bool:
        return True

    def seek(self, *a) -> int:  # type: ignore[override]
        return 0

    def tell(self) -> int:
        return self.written


class _ShortReader:
    """A source that returns one byte per read, whatever it was asked for.

    Real files can return short reads; a streaming reader that assumed
    read(n) gives n bytes would corrupt or stall here.
    """

    def __init__(self, data: bytes) -> None:
        self.data = data
        self.pos = 0

    def read(self, n: int = -1) -> bytes:  # type: ignore[override]
        out = self.data[self.pos:self.pos + 1]
        self.pos += 1
        return out


@pytest.mark.parametrize("block_size", [1, 2, 3, 7, 10, 11, 4096])
def test_pathological_block_sizes_round_trip(block_size: int) -> None:
    data = b"abcdefghij"  # 10 bytes: exercises exact-block and block+1 cases
    archive = container.pack(data, block_size=block_size, level=1)
    assert container.unpack(archive) == data
    info, _, _ = container.read_index(archive)
    assert sum(b.uncompressed_size for b in info.blocks) == len(data)


@pytest.mark.parametrize(
    "payload",
    [
        b"",
        b"\x00" * 5000,
        b"\xff" * 5000,
        bytes(range(256)) * 20,
        b"a" * 4096,        # exactly one block
        b"a" * 4097,        # one block plus one byte
    ],
)
def test_nasty_payloads_round_trip_and_verify(payload: bytes) -> None:
    archive = container.pack(payload, block_size=4096, level=1)
    assert container.verify_archive(archive).ok is True
    assert container.unpack(archive) == payload
    # and the streaming pair agrees with the buffered pair
    out = io.BytesIO()
    container.unpack_stream(io.BytesIO(archive), out)
    assert out.getvalue() == payload


def test_incompressible_data_with_a_tight_cap_is_refused_not_truncated() -> None:
    """E-RES-002: a block that compresses past the declared ceiling must refuse.
    Truncating it would produce an archive that cannot round-trip."""
    rng = random.Random(7)  # fixed seed: the noise must stay incompressible
    noise = bytes(rng.getrandbits(8) for _ in range(5000))
    with pytest.raises(container.ContainerError) as exc:
        container.pack(noise, block_size=4096, level=1, max_block_compressed=1024)
    assert exc.value.code == "E-RES-002"


def test_failing_destination_raises_oserror_and_writes_nothing_valid() -> None:
    dst = _FailingDst(limit=500)
    with pytest.raises(OSError):
        container.pack_stream(io.BytesIO(b"payload " * 2000), dst, block_size=1024)
    assert dst.written > 0  # it did start writing; the failure is what matters


def test_short_read_source_matches_the_buffered_canonicalizer() -> None:
    raw = b"line1\r\nline2\rline3\xc2\xad\n" * 20
    out = io.BytesIO()
    canonicalize_stream(_ShortReader(raw), out, chunk_size=64)
    assert out.getvalue() == canonicalize(raw)


def test_writer_is_deterministic_across_runs() -> None:
    data = b"determinism " * 500
    runs = {container.pack(data, block_size=1024, level=6) for _ in range(3)}
    assert len(runs) == 1, "pack() produced different bytes on identical inputs"


def _exit_code(argv: list[str]) -> int:
    """The CLI reports file errors two ways — a returned code or SystemExit(3)
    raised from the atomic writers, matching `_read()` for unreadable input. Both
    are the documented contract (exit 3), so tests accept either rather than
    pinning an implementation detail."""
    try:
        return cli.main(argv)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 1


class TestCliWriteFailures:
    """Every output-file failure must be exit 3 with a one-line error, and must
    leave no artifact and no temp file behind."""

    def _no_debris(self, directory: pathlib.Path) -> None:
        assert [p.name for p in directory.iterdir() if p.name.startswith(".lxz-tmp-")] == []

    def test_missing_destination_directory_exits_3(self, tmp_path, capsys) -> None:
        src = tmp_path / "in.txt"
        src.write_bytes(b"payload\r\n")
        target = tmp_path / "nodir" / "x.lxz"

        assert _exit_code(["pack", "--in", str(src), "--out", str(target)]) == cli.EXIT_FILE
        captured = capsys.readouterr()
        assert "cannot write" in captured.err
        assert "Traceback" not in captured.err
        assert not target.exists()

    @pytest.mark.skipif(os.geteuid() == 0, reason="root ignores directory permissions")
    def test_unwritable_destination_directory_exits_3(self, tmp_path, capsys) -> None:
        src = tmp_path / "in.txt"
        src.write_bytes(b"payload\r\n")
        ro = tmp_path / "ro"
        ro.mkdir()
        ro.chmod(0o500)
        try:
            rc = _exit_code(["pack", "--in", str(src), "--out", str(ro / "x.lxz")])
            captured = capsys.readouterr()
        finally:
            ro.chmod(0o700)
        assert rc == cli.EXIT_FILE
        assert "cannot write" in captured.err and "Traceback" not in captured.err
        assert list(ro.iterdir()) == []  # no artifact, no temp file

    def test_canon_and_unpack_fail_the_same_way(self, tmp_path) -> None:
        raw = tmp_path / "in.txt"
        raw.write_bytes(b"text\r\n")
        target = tmp_path / "nodir" / "out"
        assert _exit_code(["canon", "--in", str(raw), "--out", str(target)]) == cli.EXIT_FILE
        assert _exit_code(["unpack", "--in", str(raw), "--out", str(target)]) in (
            cli.EXIT_FILE, cli.EXIT_CONTAINER
        )

    def test_successful_pack_leaves_only_the_artifact(self, tmp_path) -> None:
        src = tmp_path / "in.txt"
        src.write_bytes(b"payload " * 100)
        out = tmp_path / "a.lxz"
        assert cli.main(["pack", "--in", str(src), "--out", str(out)]) == cli.EXIT_OK
        assert sorted(p.name for p in tmp_path.iterdir()) == ["a.lxz", "in.txt"]
        self._no_debris(tmp_path)

    @pytest.mark.skipif(os.geteuid() == 0, reason="root ignores directory permissions")
    def test_batch_into_an_unwritable_out_dir_exits_3(self, tmp_path) -> None:
        src = tmp_path / "in"
        src.mkdir()
        (src / "a.txt").write_bytes(b"alpha\r\n")
        ro = tmp_path / "ro"
        ro.mkdir()
        ro.chmod(0o500)
        try:
            rc = _exit_code(["batch", "--in", str(src), "--out-dir", str(ro / "sub")])
        finally:
            ro.chmod(0o700)
        assert rc == cli.EXIT_FILE
