"""PPMd codec — the max-ratio preset, via pyppmd.

Why this exists (ADR-0021)
--------------------------
Measured on the project's own corpus class, per file, 2026-11-08:

    codec                  ratio    throughput
    PPMd (order 6, 16 MiB)  0.2283   3.34 MiB/s
    CHCE -9                 0.2286   0.48 MiB/s
    CHCE -9 --max-ratio     0.2192   0.05 MiB/s

PPMd **ties CHCE's default preset at seven times the speed**, and needs no external
binary — `pip install pyppmd`. CHCE keeps a real 4 % edge only in `--max-ratio`, which
runs at 0.05 MiB/s: a 4 MB document takes 80 seconds. So PPMd becomes the max-ratio
preset and CHCE is demoted to an explicitly-slow archival option (ADR-0021).

The trap this module is built around
-----------------------------------
PPMd is **not self-describing**. `pyppmd.decompress(data, max_order=N)` with the wrong
order does not raise — it returns **wrong bytes** silently (verified: decoding an
order-16 stream with the default order 6 returns data that does not match, with no
exception). A codec that guessed the order would corrupt archives and report success.

So the frame carries its own order byte, the decoder always uses the recorded value, and
`mem_size` is **fixed at 16 MiB** for this codec id. Changing the memory budget is a new
codec id, not a parameter — because an archive that cannot be decoded without out-of-band
knowledge is not an archive.
"""

from __future__ import annotations

import os

from lexora.zstd_core import CodecError

MAGIC = b"PPMD"
#: Fixed, not configurable: the decoder must know it, so it is part of the format.
MEM_SIZE = 16 * 1024 * 1024
#: PPMd order range, per pyppmd's own documentation (2..64).
MIN_ORDER, MAX_ORDER = 2, 64
DEFAULT_ORDER = 6


def available() -> bool:
    try:
        import pyppmd  # noqa: F401
    except ImportError:
        return False
    return True


def _require():
    try:
        import pyppmd
    except ImportError as exc:  # pragma: no cover - optional extra
        raise CodecError(
            "the ppmd codec needs pyppmd (pip install 'lexora[ppmd]'); it is an "
            "optional extra, not a base dependency"
        ) from exc
    return pyppmd


def validate_level(level: int) -> str | None:
    """PPMd's 'level' is its model order, 2..64. Outside that is a usage error."""
    if isinstance(level, bool) or not isinstance(level, int):
        return f"order must be an integer, got {type(level).__name__}"
    if not (MIN_ORDER <= level <= MAX_ORDER):
        return (f"order {level} is outside the PPMd range {MIN_ORDER}..{MAX_ORDER} "
                f"(default {DEFAULT_ORDER})")
    return None


def compress(data: bytes, *, level: int = DEFAULT_ORDER) -> bytes:
    """Compress to `MAGIC || order-byte || stream`."""
    problem = validate_level(level)
    if problem:
        raise CodecError(problem)
    pyppmd = _require()
    body = pyppmd.compress(data, max_order=level, mem_size=MEM_SIZE)
    return MAGIC + bytes([level]) + body


def decompress(frame: bytes, *, expected_original_size: int | None = None) -> bytes:
    """Decode a frame written by `compress`. Refuses anything malformed."""
    if len(frame) < len(MAGIC) + 1 or not frame.startswith(MAGIC):
        raise CodecError("not a ppmd frame (bad magic)")
    order = frame[len(MAGIC)]
    if not (MIN_ORDER <= order <= MAX_ORDER):
        raise CodecError(f"ppmd frame records an impossible order {order}")
    pyppmd = _require()
    try:
        out = pyppmd.decompress(frame[len(MAGIC) + 1:], max_order=order, mem_size=MEM_SIZE)
    except Exception as exc:  # noqa: BLE001 - pyppmd raises several types
        raise CodecError(f"ppmd decode failed: {exc}") from exc
    if not isinstance(out, (bytes, bytearray)):
        raise CodecError("ppmd decode returned non-bytes")
    out = bytes(out)
    if expected_original_size is not None and len(out) != expected_original_size:
        # The block index says how long this must be. A mismatch means the frame or
        # its parameters are wrong — refuse rather than hand back plausible bytes,
        # which is exactly the failure PPMd invites.
        raise CodecError(
            f"ppmd decoded {len(out)} bytes, block index says {expected_original_size}"
        )
    return out


def verify_roundtrip(data: bytes, *, level: int = DEFAULT_ORDER) -> dict:
    """Compress, decode, compare. The project's standard before-use gate."""
    blob = compress(data, level=level)
    back = decompress(blob, expected_original_size=len(data))
    if back != data:
        raise CodecError("ppmd round-trip mismatch")
    return {
        "codec_profile": f"ppmd-order{level}",
        "input_bytes": len(data),
        "stored_bytes": len(blob),
        "ratio": (len(blob) / len(data)) if data else 1.0,
        "roundtrip_exact": True,
    }
