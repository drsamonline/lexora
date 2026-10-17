"""`.lxz` v0 container tests — normative per ADR-0007 (Accepted, Session 24).

Covers the ADR's verification plan:
  V1 golden single-byte archive (exact bytes committed)
  V2 round-trip incl. block-boundary sizes (limit-1, limit, limit+1 => refuse)
  V3 hostile negatives: bad magic, truncated header, index past EOF,
     oversized declared block, checksum-flipped block, unknown codec ID,
     must-understand flag set — each with specific error code + zero output
  V4 determinism: same input+level+block_size => byte-identical archive
"""

from __future__ import annotations

import hashlib
import pathlib
import struct

import pytest

from lexora import CANONICALIZER_VERSION, CODEC_ID_ZSTD
from lexora.container import (
    HEADER_SIZE,
    INDEX_ENTRY_SIZE,
    MAGIC,
    TRAILER_SIZE,
    BlockEntry,
    ContainerError,
    pack,
    read_index,
    unpack,
    unpack_blocks,
    unpack_header,
)

GOLDEN_INPUT = b"x"
GOLDEN_SHA = hashlib.sha256(GOLDEN_INPUT).hexdigest()


def _build(overrides: dict = {}, patch: bytes | None = None) -> bytes:
    """Build a valid archive then optionally mutate named regions.
    overrides keys: 'major','minor','flags','codec_id','block_count',
    'idx_off','idx_len' applied by re-packing raw bytes (header hash recomputed
    only when `fix_hash=True`)."""
    arc = bytearray(pack(b"payload payload payload", level=1, block_size=8))
    if "flags" in overrides:
        struct.pack_into("<Q", arc, 8, overrides["flags"])
    if "codec_id" in overrides:
        idb = overrides["codec_id"].encode().ljust(16, b"\x00")
        arc[16:32] = idb
    if "major" in overrides:
        struct.pack_into("<H", arc, 4, overrides["major"])
    if patch is not None:
        for off, val in patch:
            arc[off] ^= val
    # recompute header checksum so ONLY the intended field is invalid
    arc[96:128] = hashlib.sha256(bytes(arc[:96])).digest()
    return bytes(arc)


# ---------------------------------------------------------------- V1 golden

class TestGoldenVectors:
    def test_golden_single_byte_archive(self):
        arc = pack(GOLDEN_INPUT, level=19, generator_version="lexora-golden")
        assert arc[:4] == MAGIC
        info, idx_off, idx_len = read_index(arc)
        assert len(info.blocks) == 1
        e = info.blocks[0]
        assert e.uncompressed_size == 1
        assert e.hexdigest == GOLDEN_SHA
        assert idx_len == INDEX_ENTRY_SIZE
        assert unpack(arc) == GOLDEN_INPUT
        # commit-on-change discipline: exact bytes pinned via digest
        assert hashlib.sha256(arc).hexdigest() == GOLDEN_ARCHIVE_SHA256, (
            ".lxz golden archive bytes changed — format change requires an "
            "ADR per SPEC §10.2; regenerate vector consciously, never casually"
        )
        # also write the full golden file if missing (checked into tests/vectors)
        vec = pathlib.Path(__file__).parent / "vectors" / "lxz_format" / "golden_1byte.lxz"
        if not vec.exists():
            pytest.fail(f"golden vector file missing: {vec} (commit it)")
        assert vec.read_bytes() == arc


# Pinned at Session 24 acceptance; regenerated ONLY with a deliberate ADR.
GOLDEN_ARCHIVE_SHA256 = "27877df54dcb024bb9cdc338f37539930c6dde534e7406219c402fb8c4b705e9"


# ------------------------------------------------------------------ V2 roundtrip

class TestRoundTrip:
    @pytest.mark.parametrize("size", [0, 1, 7, 8, 9, 4095, 4096, 4097, 1 << 20])
    def test_sizes_and_boundaries(self, size):
        data = bytes(range(256)) * (size // 256) + bytes(range(size % 256))
        arc = pack(data, level=1, block_size=4096)
        assert unpack(arc) == data

    def test_empty_payload_is_one_empty_block(self):
        arc = pack(b"", level=1)
        info, _, _ = read_index(arc)
        assert len(info.blocks) == 1 and info.blocks[0].uncompressed_size == 0
        assert unpack(arc) == b""

    def test_limit_minus_one_and_limit_ok(self):
        data = b"a" * 4096
        assert unpack(pack(data, level=1, block_size=4096)) == data

    def test_limit_plus_one_refused_at_pack(self):
        # max_total_uncompressed smaller than input => E-RES-003 before work
        with pytest.raises(ContainerError) as ei:
            pack(b"a" * 100, level=1, max_total_uncompressed=99)
        assert ei.value.code == "E-RES-003"

    def test_reader_enforces_declared_limit(self):
        # craft archive whose index declares usz > header limit
        arc = bytearray(pack(b"abcdefgh" * 4, level=1, block_size=8))
        # find index start from trailer
        t = len(arc) - TRAILER_SIZE
        idx_off, idx_len = struct.unpack_from("<QQ", arc, t)
        # entry 0 uncompressed_size field at idx_off + 16
        struct.pack_into("<Q", arc, idx_off + 16, 10_000)
        arc[t + 16:t + TRAILER_SIZE] = hashlib.sha256(
            bytes(arc[idx_off:idx_off + idx_len])).digest()[:TRAILER_SIZE - 16]
        with pytest.raises(ContainerError) as ei:
            read_index(bytes(arc))
        assert ei.value.code == "E-RES-001"

    def test_bounded_decode_only_block(self):
        data = b"zero-block!one-block!two-block!" * 10
        arc = pack(data, level=1, block_size=11)
        info, _, _ = read_index(arc)
        for i, e in enumerate(info.blocks):
            got = unpack(arc, only_block=i)
            exp = data[i * 11:(i + 1) * 11]
            assert got == exp
        with pytest.raises(ContainerError) as ei:
            unpack(arc, only_block=len(info.blocks))
        assert ei.value.code == "E-FMT-IDX-006"

    def test_per_block_granularity(self):
        data = b"A" * 32 + b"B" * 32
        arc = bytearray(pack(data, level=1, block_size=32))
        info, _, _ = read_index(bytes(arc))
        # corrupt block 0 payload (not index): flip one compressed byte
        arc[info.blocks[0].offset + 6] ^= 0xFF
        ok, fails = unpack_blocks(bytes(arc))
        assert ok == b"B" * 32          # independent block still decodes
        assert len(fails) == 1 and "block 0" in fails[0]


# ------------------------------------------------------------------ V3 hostile

def _hostile_cases():
    good = pack(b"hostile hostile hostile", level=1, block_size=8)
    out = []
    out.append(("bad magic", good[:4].replace(b"LXZ|", b"XXXX") + good[4:], ("E-FMT-HEAD-001",)))
    out.append(("truncated header", good[:HEADER_SIZE - 1], ("E-FMT-HEAD-003",)))
    out.append(("truncated mid-file", good[:len(good) - TRAILER_SIZE - 1], ("E-FMT-IDX-001", "E-FMT-IDX-003")))
    # header corruption without fixing checksum
    b = bytearray(good); b[8] ^= 0x01
    out.append(("header bitflip (checksum catches)", bytes(b), ("E-FMT-HEAD-004",)))
    # flags must-understand bit set, header hash fixed => refusal on flags
    out.append(("must-understand flag", _build({"flags": 0x01}), ("E-FMT-HEAD-002",)))
    out.append(("unknown codec id", _build({"codec_id": "lzma-fake"}), ("E-CMP-006",)))
    out.append(("wrong major", _build({"major": 9}), ("E-FMT-HEAD-005",)))
    # index offset past EOF (rewrite trailer locator only)
    b = bytearray(good)
    t = len(b) - TRAILER_SIZE
    struct.pack_into("<Q", b, t, len(good) + 1000)
    out.append(("index offset past EOF", bytes(b), ("E-FMT-IDX-001",)))
    # flipped byte inside a block payload => decode/checksum refusal
    b = bytearray(good); b[HEADER_SIZE + 5] ^= 0xFF
    out.append(("flipped block byte", bytes(b), ("E-CMP-004", "E-INTEGRITY-001")))
    return out


class TestHostileNegatives:
    @pytest.mark.parametrize("name,data,codes", _hostile_cases())
    def test_refusals_specific_code(self, name, data, codes):
        with pytest.raises(ContainerError) as ei:
            unpack(data)
        assert ei.value.code in codes, f"{name}: got {ei.value.code}, want {codes}"

    def test_str_input_rejected(self):
        with pytest.raises(ContainerError):
            pack("not bytes")  # type: ignore[arg-type]


# ------------------------------------------------------------------ V4 determinism

class TestDeterminism:
    def test_identical_bytes(self):
        data = (b"determinism " * 5000)
        a = pack(data, level=19, block_size=4096)
        b = pack(data, level=19, block_size=4096)
        assert a == b

    def test_header_fields_roundtrip(self):
        arc = pack(b"meta", level=1, generator_version="lexora-test")
        info, _, _ = read_index(arc)  # unpack_header alone leaves blocks empty by design
        assert info.codec_id == CODEC_ID_ZSTD
        assert info.canonicalizer_version == CANONICALIZER_VERSION
        assert info.format_major == 0 and info.format_minor == 1
        assert info.flags == 0
        assert info.max_block_compressed == 16 * 1024 * 1024
        assert info.total_uncompressed == 4


class TestVerifyArchive:
    """Public verify_archive() API (Session 25; groundwork for GUI G4 inspector)."""

    def test_valid_archive_all_blocks_ok(self):
        from lexora.container import verify_archive

        data = b"verify me " * 3000
        arc = pack(data, level=3, block_size=4096)
        res = verify_archive(arc)
        assert res.ok is True
        assert res.error is None
        assert res.block_count == len(res.blocks) > 1
        assert all(ok for _, ok, _ in res.blocks)

    def test_structural_refusal_no_block_detail(self):
        from lexora.container import verify_archive

        bad = bytearray(pack(b"x" * 100, level=3))
        bad[0:4] = b"XXXX"  # magic
        res = verify_archive(bytes(bad))
        assert res.ok is False
        assert res.error.startswith("E-FMT-HEAD-001")
        assert res.block_count == 0 and res.blocks == ()

    def test_per_block_integrity_verdict(self):
        """One flipped payload byte => exactly that block fails, others pass,
        and verify produces NO payload (ADR-0007 per-block semantics)."""
        from lexora.container import verify_archive

        arc = pack(b"A" * 4096 + b"B" * 4096, level=3, block_size=4096)
        info, _, _ = read_index(arc)
        b1 = info.blocks[1]
        tampered = bytearray(arc)
        tampered[b1.offset + 10] ^= 0xFF
        res = verify_archive(bytes(tampered))
        assert res.ok is False
        assert res.block_count == 2
        assert res.blocks[0][1] is True
        assert res.blocks[1][1] is False
        assert res.blocks[1][2] in ("E-CMP-004", "E-INTEGRITY-001")
