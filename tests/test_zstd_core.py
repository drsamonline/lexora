"""Tests for lexora.zstd_core (REQ-CMP-001..003, 006 intent)."""

from __future__ import annotations

import pytest

import lexora.zstd_core as zc


@pytest.mark.parametrize(
    "payload",
    [
        b"",
        b"x",
        b"the quick brown fox jumps over the lazy dog\n" * 50,
        "किताब ज़ पુસ્તક ✅".encode("utf-8"),
        bytes(range(256)),
    ],
    ids=["empty", "single", "repetitive", "unicode", "binary"],
)
def test_roundtrip_byte_exact(payload: bytes):
    # REQ-CMP-001: decode(encode(C)) == C byte-exactly; deviation = blocker.
    blob = zc.compress(payload)
    assert zc.decompress(blob) == payload
    assert zc.decompress(blob, expected_original_size=len(payload)) == payload


def test_determinism_same_settings_same_bytes():
    # REQ-CMP-003 at codec level.
    data = ("lexical compression " * 500).encode("utf-8")
    assert zc.compress(data) == zc.compress(data)


def test_rejects_str_input():
    with pytest.raises(zc.CodecError):
        zc.compress("not bytes")  # type: ignore[arg-type]


@pytest.mark.parametrize("level", [0, 1, 22, 23, -5])
def test_level_bounds_enforced(level):
    if 1 <= level <= 22:
        zc.compress(b"abc", level=level)  # in-range must work
    else:
        with pytest.raises(zc.CodecError):
            zc.compress(b"abc", level=level)


def test_corrupt_frame_refused_not_best_effort():
    # REQ-CMP-006 spirit: refusal with specific error, never partial output.
    good = zc.compress(b"hello world " * 100)
    corrupted = good[:10] + bytes(20) + good[30:]
    with pytest.raises(zc.CodecError):
        zc.decompress(corrupted, expected_original_size=1200)


def test_truncated_frame_refused():
    good = zc.compress(b"A" * 10_000)
    with pytest.raises(zc.CodecError):
        zc.decompress(good[:-5], expected_original_size=10_000)


def test_verify_roundtrip_stats():
    data = b"measure me " * 1000
    stats = zc.verify_roundtrip(data)
    assert stats["roundtrip_exact"] is True
    assert stats["input_bytes"] == len(data)
    assert stats["codec_profile"] == "zstd-raw-l19"
    assert stats["ratio"] < 0.1  # highly repetitive input
    assert stats["payload_sha256"] != stats["stored_sha256"]


def test_bounded_decode_hint_respected():
    data = b"safe sizing " * 10
    blob = zc.compress(data)
    # Hint smaller than actual -> decompress must refuse rather than overflow silently.
    with pytest.raises(Exception):
        zc.decompress(blob, expected_original_size=5)
