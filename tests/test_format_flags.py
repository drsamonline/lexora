"""Header flag semantics (REQ-FMT-003).

FORMAT_LXZ §compat rules say two things that have to be enforced by the *reader*,
not just documented:

- an unknown **may-ignore** flag ⇒ proceed, and say so;
- an unknown **must-understand** flag ⇒ hard refusal with a specific code and **zero
  output bytes**.

The implementation was there (`container.py` refuses when `FLAGS_MUST_UNDERSTAND_MASK`
is set) but nothing tested it, so the requirement sat at "Not started" in the matrix.
These tests close that gap.
"""

from __future__ import annotations

import hashlib
import struct

import pytest

from lexora import container
from lexora.container import (CHECKSUM_REGION, FLAGS_MUST_UNDERSTAND_MASK,
                              HEADER_SIZE, ContainerError)

PAYLOAD = (b"the quick brown fox jumps over the lazy dog. " * 40)


def _archive() -> bytes:
    return container.pack(PAYLOAD, level=3)


def _with_flags(blob: bytes, flags: int) -> bytes:
    """Return the archive with the header's u64 flags field replaced.

    The header carries its own SHA-256 over bytes 0..CHECKSUM_REGION, so the digest
    is recomputed here. Without that, the reader rejects the archive for a corrupt
    header (`E-FMT-HEAD-004`) before it ever reaches the flag check — which is
    correct behaviour, and the reason this test has to forge a *valid* header to
    reach the flag path at all.
    """
    out = bytearray(blob)
    struct.pack_into("<Q", out, 8, flags)  # flags live at offset 8, per the layout
    out[CHECKSUM_REGION:HEADER_SIZE] = hashlib.sha256(bytes(out[:CHECKSUM_REGION])).digest()
    return bytes(out)


def test_a_clean_archive_carries_no_flags() -> None:
    """v0 writes flags = 0, so any non-zero bit is by definition unknown to it."""
    blob = _archive()
    assert struct.unpack_from("<Q", blob, 8)[0] == 0
    assert container.verify_archive(blob).ok is True


def test_unknown_must_understand_flag_is_refused() -> None:
    blob = _with_flags(_archive(), FLAGS_MUST_UNDERSTAND_MASK & 0b0000_0001)
    with pytest.raises(ContainerError) as exc:
        container.unpack(blob)
    assert exc.value.code == "E-FMT-HEAD-002"
    assert "must-understand" in exc.value.message


def test_every_must_understand_bit_is_refused() -> None:
    """Not just bit 0: the whole mask has to be treated as unknown-and-fatal."""
    for bit in range(8):
        blob = _with_flags(_archive(), 1 << bit)
        with pytest.raises(ContainerError) as exc:
            container.unpack(blob)
        assert exc.value.code == "E-FMT-HEAD-002", f"bit {bit} slipped through"


def test_may_ignore_bits_are_tolerated() -> None:
    """Bits above the must-understand mask are ignorable by definition: a reader
    that understands v0 must still decode the payload exactly."""
    blob = _with_flags(_archive(), 1 << 40)
    assert container.unpack(blob) == PAYLOAD
    assert container.verify_archive(blob).ok is True


def test_verify_reports_the_flag_failure_rather_than_crashing() -> None:
    """`verify` is the audit verb: it must report a bad header, not raise."""
    blob = _with_flags(_archive(), 0b0000_0001)
    result = container.verify_archive(blob)
    assert result.ok is False
    assert "E-FMT-HEAD-002" in str(result.error)


def test_a_corrupt_header_is_caught_before_the_flags_are_read() -> None:
    """Order matters: a tampered header is a checksum failure, not a flag failure.

    This is what made the first version of these tests fail, and the behaviour is
    right — the digest is the earlier, stronger signal.
    """
    blob = bytearray(_archive())
    struct.pack_into("<Q", blob, 8, 0b0000_0001)  # flip a flag, leave the digest stale
    with pytest.raises(ContainerError) as exc:
        container.unpack(bytes(blob))
    assert exc.value.code == "E-FMT-HEAD-004"


def test_a_refused_flag_produces_no_output_file(tmp_path) -> None:
    """The compat rule is 'zero output bytes' — a half-written file would be worse
    than the refusal itself."""
    blob = _with_flags(_archive(), 0b0000_0001)
    src = tmp_path / "bad.lxz"
    dst = tmp_path / "out.bin"
    src.write_bytes(blob)
    with pytest.raises(ContainerError):
        with open(src, "rb") as fh_in, open(dst, "wb") as fh_out:
            container.unpack_stream(fh_in, fh_out)
    assert not dst.exists() or dst.stat().st_size == 0
