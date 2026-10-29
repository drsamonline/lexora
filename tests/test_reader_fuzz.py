"""Reader hardening: malformed archives must be refused, never crash or corrupt.

These are deterministic fuzz tests — no external fuzz library, no randomness that
changes between runs — so a failure is reproducible from the test name alone. They
encode the properties the reader is *supposed* to hold, which the `.lxz` docs state
but nothing until now exercised:

  P1  every mutant either decodes to the ORIGINAL bytes or raises ContainerError.
      Anything else — a bare struct.error, an IndexError, a zstd error, a silent
      wrong answer — is a defect.
  P2  the reader enforces the ABSOLUTE limits (LIM-01 8 MiB, LIM-02 16 MiB), not
      merely the limits the header declares about itself.
  P3  a frame whose own header disagrees with the index is refused *before*
      allocation, and a huge declared size never becomes a huge allocation.
  P4  the CLI never tracebacks and never returns an undocumented exit code.
  P5  refusals are deterministic: the same mutant yields the same code twice.

Session 54 built these after a manual fuzz pass; two real gaps fell out (P2 was
unenforced, and a corrupt frame header could drive an allocation attempt).
"""

from __future__ import annotations

import hashlib
import io
import pathlib
import tracemalloc

import pytest

from lexora import cli, container
from lexora.inspect import summarize

BASES = (
    b"",
    b"x",
    b"payload integrity " * 200,
    bytes(range(256)) * 20,
)


def _archives() -> list[tuple[bytes, bytes]]:
    """(payload, archive) pairs across shapes: empty, one byte, multi-block, varied."""
    out = []
    for i, data in enumerate(BASES):
        block_size = 4096 if i % 2 == 0 else 512
        out.append((data, container.pack(data, block_size=block_size, level=1)))
    return out


def _mutants(archive: bytes):
    """Truncations, single-byte flips, and end-drops — deterministic and bounded."""
    n = len(archive)
    for cut in range(0, n):
        yield ("truncate", cut, archive[:cut])
    step = max(1, n // 40)          # ~40 offsets per archive keeps this module fast
    for off in range(0, n, step):
        for xor in (0xFF, 0x80):
            m = bytearray(archive)
            m[off] ^= xor
            yield ("flip", off, bytes(m))
    for cut in (1, 2, 3, 40, 56):
        if cut < n:
            yield ("dropend", cut, archive[:-cut])


def _unpack_stream_bytes(blob: bytes) -> bytes:
    """unpack_stream returns (info, written); the property test wants the bytes."""
    out = io.BytesIO()
    container.unpack_stream(io.BytesIO(blob), out)
    return out.getvalue()


READERS = {
    "read_index": lambda b: container.read_index(b),
    "read_index_stream": lambda b: container.read_index_stream(io.BytesIO(b)),
    "unpack": lambda b: container.unpack(b),
    "unpack_stream": lambda b: _unpack_stream_bytes(b),
    "verify_archive": lambda b: container.verify_archive(b),
    "verify_stream": lambda b: container.verify_stream(io.BytesIO(b)),
    "summarize": lambda b: summarize(io.BytesIO(b)),
}


@pytest.mark.parametrize("reader_name", sorted(READERS))
def test_mutants_are_refused_cleanly_or_decode_to_the_original(reader_name: str) -> None:
    """P1: no exception type other than ContainerError may escape; a decode that
    succeeds must return the original payload (a *silent* wrong answer is the worst
    possible outcome, worse than any refusal)."""
    reader = READERS[reader_name]
    for payload, archive in _archives():
        for kind, where, blob in _mutants(archive):
            try:
                result = reader(blob)
            except container.ContainerError:
                continue  # refusal: the expected outcome for most mutants
            except Exception as exc:  # noqa: BLE001 - this is exactly what we assert against
                raise AssertionError(
                    f"{reader_name} leaked {type(exc).__name__} on {kind}@{where}: {exc}"
                ) from exc
            if reader_name in ("unpack", "unpack_stream"):
                assert result == payload, f"{reader_name} silently mis-decoded {kind}@{where}"


def test_refusals_are_deterministic() -> None:
    """P5: the same mutant must produce the same code on a second pass."""
    for _payload, archive in _archives():
        for kind, where, blob in _mutants(archive):
            codes = []
            for _ in range(2):
                try:
                    container.unpack(blob)
                    codes.append("ok")
                except container.ContainerError as exc:
                    codes.append(exc.code)
            assert codes[0] == codes[1], f"non-deterministic verdict for {kind}@{where}"


def test_header_cannot_raise_its_own_limits_above_the_ceilings() -> None:
    """P2: RESOURCE_LIMITS says the reader enforces LIM-01/LIM-02. Until Session 54
    it only enforced what the header *declared*, so a hostile header could set its
    own caps to 2^60 and defeat every downstream pre-allocation check."""
    base = container.pack(b"x" * 1000, block_size=4096, level=1)
    for field, offset in (("max_block_uncompressed", 48),
                          ("max_block_compressed", 56),
                          ("max_total_uncompressed", 64)):
        m = bytearray(base)
        m[offset:offset + 8] = (1 << 60).to_bytes(8, "little")
        m[96:128] = hashlib.sha256(bytes(m[:96])).digest()  # header checksum valid
        with pytest.raises(container.ContainerError) as exc:
            container.unpack(bytes(m))
        assert exc.value.code == "E-RES-004", f"{field} above the ceiling was accepted"


def test_stricter_declared_limits_are_still_honoured() -> None:
    """P2 the other way: a header may declare *tighter* caps than the ceiling."""
    # block_size sets the header's declared max_block_uncompressed; a caller may
    # also declare a tighter archive-wide ceiling than the format default
    archive = container.pack(b"tight limits " * 100, block_size=1024, level=1,
                             max_total_uncompressed=1 << 20)
    info, _, _ = container.read_index(archive)
    assert info.max_block_uncompressed == 1024
    assert container.unpack(archive) == b"tight limits " * 100


def test_frame_header_disagreeing_with_the_index_is_refused_before_allocation() -> None:
    """P3: a corrupted frame header can declare an enormous content size. The
    reader must refuse on the mismatch, not attempt the allocation."""
    data = b"allocation guard " * 400
    archive = bytearray(container.pack(data, block_size=512, level=1))
    info, _, _ = container.read_index(bytes(archive))
    first = info.blocks[0]
    # rewrite the frame's content-size field to something absurd
    archive[first.offset + 5:first.offset + 13] = (1 << 50).to_bytes(8, "little")

    tracemalloc.start()
    try:
        with pytest.raises(container.ContainerError):
            container.unpack(bytes(archive))
        peak = tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()
    assert peak < 32 * 1024 * 1024, f"allocated {peak / 2**20:.1f} MiB refusing a 2^50 claim"


def test_cli_never_tracebacks_and_uses_documented_exit_codes(tmp_path) -> None:
    """P4: the CLI maps refusals to codes 0/2/3/7 — a traceback here would be a
    user-facing crash on a corrupt file."""
    documented = {0, 2, 3, 7}
    for _payload, archive in _archives():
        for i, (kind, where, blob) in enumerate(_mutants(archive)):
            if i % 7:               # sample: argparse per call is the slow part
                continue
            path = tmp_path / f"m_{kind}_{where}.lxz"
            path.write_bytes(blob)
            for argv in (["verify", "--in", str(path)],
                         ["inspect", "--in", str(path)],
                         ["unpack", "--in", str(path), "--out", str(tmp_path / "o.bin")]):
                try:
                    rc = cli.main(argv)
                except SystemExit as exc:
                    rc = exc.code
                except Exception as exc:  # noqa: BLE001
                    raise AssertionError(
                        f"{argv[0]} crashed on {kind}@{where}: {type(exc).__name__}: {exc}"
                    ) from exc
                assert rc in documented, f"{argv[0]} returned {rc} on {kind}@{where}"


def test_random_blobs_are_refused_not_crashed() -> None:
    """Cheap coverage for inputs that never were archives at all."""
    import random

    rng = random.Random(20261029)  # fixed seed: reproducible failures
    for size in (0, 1, 7, 128, 168, 169, 512, 4096):
        blob = bytes(rng.getrandbits(8) for _ in range(size))
        for name, reader in READERS.items():
            try:
                reader(blob)
            except container.ContainerError:
                pass
            except Exception as exc:  # noqa: BLE001
                raise AssertionError(f"{name} leaked {type(exc).__name__} on {size} B blob") from exc


def test_a_real_archive_is_still_accepted_after_hardening() -> None:
    """The guard against over-hardening: our own writer's output must still pass."""
    data = b"regression guard " * 500
    archive = container.pack(data, block_size=8192, level=1)
    assert container.unpack(archive) == data
    assert container.verify_archive(archive).ok is True
    with open(pathlib.Path(__file__).parent / "vectors" / "lxz_format" / "golden_1byte.lxz", "rb") as fh:
        golden = fh.read()
    assert container.unpack(golden) == b"x"
