"""Core Zstd baseline codec (REQ-CMP-002) with block-level round-trip API.

Scope honesty:
  * This is the Phase-1 *baseline* codec: frame-level Zstd via python-zstandard,
    level configurable, default 19 to match BENCHMARK_PROTOCOL's frozen
    Zstd-19 baseline settings.
  * It does NOT implement the `.lxz` container. FORMAT_LXZ.md is PROPOSED and
    explicitly says "Do not implement decoders from this document" until an
    accepted format ADR + test vectors exist. The only serialization here is
    plain zstd frames (self-describing, magic 0xFD2FB528).
  * Invariant enforced by tests (REQ-CMP-001): decode(encode(C)) == C,
    byte-exact, for arbitrary byte inputs including empty.
"""

from __future__ import annotations

import hashlib

import zstandard as zstd

from lexora import CODEC_ID_ZSTD

DEFAULT_LEVEL = 19  # matches frozen baseline; profile ID reflects it


class CodecError(Exception):
    """Codec-level failure (bad parameters or corrupt input)."""


def _profile_id(level: int) -> str:
    return f"{CODEC_ID_ZSTD}" if level == DEFAULT_LEVEL else f"zstd-raw-l{level}"


def compress(canonical: bytes, *, level: int = DEFAULT_LEVEL) -> bytes:
    """Compress canonical bytes C into a single zstd frame.

    Deterministic given (bytes, level, library version) — REQ-CMP-003 at the
    codec level (selection policy is a later phase).
    """
    if not isinstance(canonical, bytes):
        raise CodecError("input must be bytes (canonical form), not str")
    if not (1 <= level <= 22):
        raise CodecError(f"level {level} outside zstd range 1..22")
    params = zstd.ZstdCompressionParameters.from_level(level)
    return zstd.ZstdCompressor(compression_params=params).compress(canonical)


def decompress(frame: bytes, *, expected_original_size: int | None = None) -> bytes:
    """Decompress one zstd frame back to canonical bytes.

    If expected_original_size is given, uses it to pre-size output (bounded
    allocation); otherwise relies on the frame content-size field. Frames
    without a content size and without the hint are refused — length-before-
    allocation principle (REQ-SEC-001 intent, applied conservatively here).

    REQ-CMP-006 spirit: never returns partial/best-effort output. python-
    zstandard's one-shot `decompress()` silently TRUNCATES when max_output_size
    is smaller than the real payload (verified empirically with zstandard
    0.25.0), so we detect truncation by re-checking against the hint and raise
    CodecError instead of returning the prefix.
    """
    dctx = zstd.ZstdDecompressor()
    try:
        if expected_original_size is not None:
            out = dctx.decompress(
                frame, max_output_size=max(expected_original_size, 1)
            )
            if len(out) != expected_original_size:
                raise CodecError(
                    f"decoded size {len(out)} != expected {expected_original_size} "
                    "(truncation or wrong hint; refusing best-effort output)"
                )
            return out
        # Read content size from frame header; refuse unknown-length frames.
        size = zstd.frame_content_size(frame)
        if size in (None, -1, zstd.CANNOT_DETERMINE_SIZE if hasattr(zstd, "CANNOT_DETERMINE_SIZE") else -1):
            raise CodecError(
                "frame has no embedded content size; supply expected_original_size "
                "(unbounded allocation is prohibited)"
            )
        return dctx.decompress(frame, max_output_size=max(size, 1))
    except zstd.ZstdError as exc:
        raise CodecError(f"corrupt or truncated zstd frame: {exc}") from exc


def verify_roundtrip(canonical: bytes, *, level: int = DEFAULT_LEVEL) -> dict:
    """Encode->decode and assert byte equality; returns measured stats."""
    blob = compress(canonical, level=level)
    back = decompress(blob, expected_original_size=len(canonical))
    ok = back == canonical
    return {
        "codec_profile": _profile_id(level),
        "library_version": zstd.__version__,
        "input_bytes": len(canonical),
        "stored_bytes": len(blob),  # total serialized bytes (REQ-CMP-004 spirit)
        "ratio": (len(blob) / len(canonical)) if canonical else 1.0,
        "roundtrip_exact": ok,
        "payload_sha256": hashlib.sha256(canonical).hexdigest(),
        "stored_sha256": hashlib.sha256(blob).hexdigest(),
    }
