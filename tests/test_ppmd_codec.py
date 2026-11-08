"""PPMd codec (ADR-0021) — the max-ratio preset.

The tests that matter here are not "does it round-trip". They are:

  * **the order is carried in the frame**, because PPMd decoded with the wrong order
    returns *wrong bytes without raising* — verified against pyppmd directly;
  * a frame whose recorded order was tampered with is **refused**, not silently decoded
    into plausible garbage;
  * the codec is optional: absent `pyppmd` is a clear CodecError naming the extra, never
    an ImportError leaking out of a library call;
  * it works through the container like any other codec, including the per-block
    SHA-256 gate.
"""

from __future__ import annotations

import importlib.util

import pytest

from lexora import container, ppmd_core
from lexora.codec_registry import by_name
from lexora.zstd_core import CodecError

_HAS_PPPMD = importlib.util.find_spec("pyppmd") is not None
requires_ppmd = pytest.mark.skipif(not _HAS_PPPMD, reason="lexora[ppmd] (pyppmd) not installed")

SAMPLE = ("The quick brown fox jumps over the lazy dog. " * 400).encode()


# --------------------------------------------------------------------------- #
# the trap: PPMd is not self-describing
# --------------------------------------------------------------------------- #

@requires_ppmd
def test_decoding_with_the_wrong_order_silently_returns_wrong_bytes() -> None:
    """The reason the frame carries an order byte — asserted against pyppmd itself.

    If this ever starts raising, the design constraint has changed and the frame
    format could be simplified. Until then, guessing the order is not an option.
    """
    import pyppmd

    stream = pyppmd.compress(SAMPLE, max_order=16, mem_size=ppmd_core.MEM_SIZE)
    wrong = pyppmd.decompress(stream, max_order=6, mem_size=ppmd_core.MEM_SIZE)
    assert wrong != SAMPLE, "pyppmd now rejects a wrong order — revisit the frame format"


@requires_ppmd
def test_a_tampered_order_byte_is_refused_not_silently_decoded() -> None:
    frame = bytearray(ppmd_core.compress(SAMPLE, level=16))
    frame[len(ppmd_core.MAGIC)] = 6          # claim a different model order
    with pytest.raises(CodecError):
        ppmd_core.decompress(bytes(frame), expected_original_size=len(SAMPLE))


@requires_ppmd
def test_the_frame_records_the_order_it_used() -> None:
    for order in (2, 6, 16):
        frame = ppmd_core.compress(SAMPLE, level=order)
        assert frame.startswith(ppmd_core.MAGIC)
        assert frame[len(ppmd_core.MAGIC)] == order


# --------------------------------------------------------------------------- #
# round trip and refusals
# --------------------------------------------------------------------------- #

@requires_ppmd
@pytest.mark.parametrize("order", [2, 6, 16, 64])
def test_round_trip_at_every_order(order: int) -> None:
    frame = ppmd_core.compress(SAMPLE, level=order)
    assert ppmd_core.decompress(frame, expected_original_size=len(SAMPLE)) == SAMPLE


@requires_ppmd
def test_empty_input_round_trips() -> None:
    frame = ppmd_core.compress(b"")
    assert ppmd_core.decompress(frame, expected_original_size=0) == b""


def test_bad_magic_is_refused() -> None:
    with pytest.raises(CodecError, match="bad magic"):
        ppmd_core.decompress(b"NOPE\x06payload")


def test_truncated_frame_is_refused() -> None:
    with pytest.raises(CodecError):
        ppmd_core.decompress(ppmd_core.MAGIC)


@requires_ppmd
def test_size_mismatch_is_refused() -> None:
    frame = ppmd_core.compress(SAMPLE)
    with pytest.raises(CodecError, match="block index says"):
        ppmd_core.decompress(frame, expected_original_size=len(SAMPLE) + 1)


@pytest.mark.parametrize("order", [0, 1, 65, -3, True, "6"])
def test_out_of_range_order_is_a_usage_error(order) -> None:
    assert ppmd_core.validate_level(order) is not None


@requires_ppmd
def test_verify_roundtrip_reports_the_profile() -> None:
    stats = ppmd_core.verify_roundtrip(SAMPLE, level=6)
    assert stats["roundtrip_exact"] is True
    assert stats["codec_profile"] == "ppmd-order6"
    assert stats["ratio"] < 0.5


# --------------------------------------------------------------------------- #
# registry + container integration
# --------------------------------------------------------------------------- #

def test_registered_with_a_level_neutral_id() -> None:
    spec = by_name("ppmd")
    assert spec.registry_id == "ppmd-1"
    assert spec.magic == b"PPMD"
    assert spec.legacy_ids == ()


@requires_ppmd
def test_container_round_trip_and_verification() -> None:
    archive = container.pack(SAMPLE, codec="ppmd")
    info, _, _ = container.read_index(archive)
    assert info.codec_id == "ppmd-1"
    assert container.unpack(archive) == SAMPLE
    assert container.verify_archive(archive).ok is True


@requires_ppmd
def test_a_corrupted_ppmd_block_fails_the_hash_gate() -> None:
    """The container's per-block SHA-256 is what makes a magicless codec safe."""
    archive = bytearray(container.pack(SAMPLE, codec="ppmd"))
    archive[200] ^= 0xFF                      # inside the block payload
    with pytest.raises(container.ContainerError):
        container.unpack(bytes(archive))


def test_the_extra_is_named_when_pyppmd_is_missing(monkeypatch) -> None:
    """Absent pyppmd must be a CodecError naming the extra, not an ImportError."""
    import builtins

    real_import = builtins.__import__

    def blocked(name, *args, **kwargs):
        if name == "pyppmd":
            raise ImportError("no pyppmd")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", blocked)
    with pytest.raises(CodecError, match=r"lexora\[ppmd\]"):
        ppmd_core.compress(b"payload")
