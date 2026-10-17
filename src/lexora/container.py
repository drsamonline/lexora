"""`.lxz` v0 container (LXZ-0.1) — normative layout per accepted ADR-0007.

Freeze record: docs/ADR/ADR-0007-container-v0-freeze.md (Accepted 2026-10-16,
Session 24, under standing owner delegation; one amendment applied at
acceptance: full 32-byte header SHA-256 => fixed 128-byte header).

Layout (all little-endian, fixed-width integers, no varints):

  Header   128 B @ 0     magic "LXZ|" | u16 major=0 | u16 minor=1 | u64 flags
                         | codec_id[16] | canonicalizer_version[16]
                         | u64 max_block_uncompressed | u64 max_block_compressed
                         | u64 max_total_uncompressed | u64 block_count
                         | generator_version[16] | sha256(header[0:96])[32]
  Blocks   variable @128  each block is exactly one complete zstd frame
  Index    N*48 B         per entry: u64 offset_in_file | u64 compressed_size
                         | u64 uncompressed_size | sha256(uncompressed)[32]
  Trailer  40 B @ EOF     u64 index_offset | u64 index_bytes | sha256(index)[32]

Semantics implemented here (REQ refs in brackets):
  * validate-before-allocate everywhere (REQ-SEC-001): header hash, limits,
    Σ declared sizes, offsets vs file size — all before any payload decode.
  * unknown must-understand flag bits / unknown codec id / major != 0 =>
    refusal with zero output (REQ-FMT-003, REQ-CMP-006).
  * per-block SHA-256 verified after decode; failing block yields zero output
    bytes, independent blocks may still decode (ADR-0007 Semantics).
  * pack verifies decode(encode)==input for 100% of blocks before reporting
    success (SPEC §8.1); failure raises and writes nothing.
  * determinism: same input + level => byte-identical archive (ADR-0007 V4),
    given a pinned zstandard library version.

Scope honesty: v0 containers hold ONE logical stream split into blocks — not
multi-document archives, no dictionaries, no encryption (see ADR Consequences).
"""

from __future__ import annotations

import hashlib
import struct
from dataclasses import dataclass

import zstandard as zstd

from lexora import CANONICALIZER_VERSION, CODEC_ID_ZSTD, __version__
from lexora.zstd_core import CodecError, compress, decompress

MAGIC = b"LXZ|"
FORMAT_MAJOR = 0
FORMAT_MINOR = 1
HEADER_SIZE = 128
CHECKSUM_REGION = 96          # header_sha256 covers [0, 96)
INDEX_ENTRY_SIZE = 56  # u64*3 (24B) + sha256 (32B); see ADR-0007 Amendment 2
TRAILER_SIZE = 40
BLOCK_START = HEADER_SIZE

# v0 defaults (ADR-0007 header table)
DEFAULT_MAX_BLOCK_UNCOMPRESSED = 8 * 1024 * 1024          # LIM-01, 8 MiB
DEFAULT_MAX_BLOCK_COMPRESSED = 16 * 1024 * 1024           # LIM-02, 16 MiB
DEFAULT_MAX_TOTAL_UNCOMPRESSED = 1 << 34                  # archive ceiling
FLAGS_MUST_UNDERSTAND_MASK = 0xFF                         # bits 0..7


class ContainerError(Exception):
    """Refusal to read/write an archive. Carries a machine-readable code."""

    def __init__(self, code: str, message: str):
        super().__init__(f"[{code}] {message}")
        self.code = code
        self.message = message


def _pad(s: str, width: int, *, truncate: bool = False) -> bytes:
    """NUL-padded fixed-width ASCII. `truncate=True` (generator_version only,
    per ADR-0007 amendment note) clips to width-1 so a terminator always
    remains; identity fields must never be clipped."""
    raw = s.encode("ascii")
    if truncate and len(raw) >= width:
        raw = raw[: width - 1]
    elif len(raw) >= width:
        raise ContainerError("E-FMT-HEAD-002", f"id {s!r} does not fit {width} bytes")
    return raw + b"\x00" * (width - len(raw))


def _unpad(b: bytes) -> str:
    return b.split(b"\x00", 1)[0].decode("ascii", errors="replace")


@dataclass
class BlockEntry:
    offset: int
    compressed_size: int
    uncompressed_size: int
    sha256: bytes  # 32 bytes, over UNCOMPRESSED block bytes

    @property
    def hexdigest(self) -> str:
        return self.sha256.hex()


@dataclass
class ArchiveInfo:
    format_major: int
    format_minor: int
    flags: int
    codec_id: str
    canonicalizer_version: str
    max_block_uncompressed: int
    max_block_compressed: int
    max_total_uncompressed: int
    generator_version: str
    blocks: list[BlockEntry]

    @property
    def total_uncompressed(self) -> int:
        return sum(b.uncompressed_size for b in self.blocks)


def pack(data: bytes, *, level: int = 19,
         block_size: int = DEFAULT_MAX_BLOCK_UNCOMPRESSED,
         max_block_compressed: int = DEFAULT_MAX_BLOCK_COMPRESSED,
         max_total_uncompressed: int = DEFAULT_MAX_TOTAL_UNCOMPRESSED,
         generator_version: str | None = None) -> bytes:
    """Serialize `data` into a `.lxz` v0 archive. Raises ContainerError on any
    limit violation; never returns a partially verified archive (SPEC §8.1)."""
    if not isinstance(data, bytes):
        raise ContainerError("E-USAGE-001", "pack() expects bytes")
    if block_size < 1:
        raise ContainerError("E-USAGE-002", "block_size must be >= 1")
    if len(data) > max_total_uncompressed:
        raise ContainerError(
            "E-RES-003",
            f"input {len(data)} exceeds max_total_uncompressed {max_total_uncompressed}",
        )

    gen = generator_version or f"lexora-{__version__}"
    chunks = [data[i:i + block_size] for i in range(0, len(data), block_size)] or [b""]

    blocks_region = bytearray()
    entries: list[BlockEntry] = []
    for chunk in chunks:
        if len(chunk) > DEFAULT_MAX_BLOCK_UNCOMPRESSED and len(chunk) > block_size:
            raise ContainerError("E-RES-001", "internal chunking error")  # unreachable
        frame = compress(chunk, level=level)
        if len(frame) > max_block_compressed:
            raise ContainerError(
                "E-RES-002",
                f"block compressed {len(frame)} > max_block_compressed {max_block_compressed}",
            )
        # verify this block decodes byte-exact BEFORE trusting it (round-trip gate)
        back = decompress(frame, expected_original_size=len(chunk))
        if back != chunk:
            raise CodecError("block round-trip mismatch (should be impossible)")
        entries.append(BlockEntry(
            offset=BLOCK_START + len(blocks_region),
            compressed_size=len(frame),
            uncompressed_size=len(chunk),
            sha256=hashlib.sha256(chunk).digest(),
        ))
        blocks_region += frame

    index = bytearray()
    for e in entries:
        index += struct.pack("<QQQ", e.offset, e.compressed_size, e.uncompressed_size)
        index += e.sha256
    assert len(index) == INDEX_ENTRY_SIZE * len(entries)

    index_offset = BLOCK_START + len(blocks_region)
    header = bytearray(BLOCK_START)
    header[0:4] = MAGIC
    struct.pack_into("<HH", header, 4, FORMAT_MAJOR, FORMAT_MINOR)
    struct.pack_into("<Q", header, 8, 0)  # flags: v0 writer emits 0
    header[16:32] = _pad(CODEC_ID_ZSTD, 16)
    header[32:48] = _pad(CANONICALIZER_VERSION, 16)
    struct.pack_into("<Q", header, 48, block_size)
    struct.pack_into("<Q", header, 56, max_block_compressed)
    struct.pack_into("<Q", header, 64, max_total_uncompressed)
    struct.pack_into("<Q", header, 72, len(entries))
    header[80:96] = _pad(gen, 16, truncate=True)
    digest = hashlib.sha256(bytes(header[:CHECKSUM_REGION])).digest()
    header[CHECKSUM_REGION:HEADER_SIZE] = digest

    trailer = struct.pack("<QQ", index_offset, len(index))
    trailer += hashlib.sha256(bytes(index)).digest()[:TRAILER_SIZE - 16]  # 24-byte prefix (see read_index note)

    archive = bytes(header) + bytes(blocks_region) + bytes(index) + trailer
    # whole-archive self-check: a reader must accept what we just wrote.
    verified, _, _ = read_index(archive)
    if len(verified.blocks) != len(entries):
        raise ContainerError("E-INT-001", "self-verify index mismatch")
    return archive


def unpack_header(archive: bytes) -> ArchiveInfo:
    """Parse+validate ONLY the header (no payload touched). All refusals are
    length-checked before allocation (REQ-SEC-001)."""
    if len(archive) < HEADER_SIZE + TRAILER_SIZE:
        raise ContainerError("E-FMT-HEAD-003",
                             f"file too short for header+trailer: {len(archive)} bytes")
    if archive[0:4] != MAGIC:
        raise ContainerError("E-FMT-HEAD-001", "bad magic (not an .lxz archive)")
    stored = archive[CHECKSUM_REGION:HEADER_SIZE]
    computed = hashlib.sha256(archive[:CHECKSUM_REGION]).digest()
    if stored != computed:
        raise ContainerError("E-FMT-HEAD-004", "header checksum mismatch (corrupt header)")

    major, minor = struct.unpack_from("<HH", archive, 4)
    flags = struct.unpack_from("<Q", archive, 8)[0]
    codec_id = _unpad(archive[16:32])
    canon_ver = _unpad(archive[32:48])
    max_bu, max_bc, max_tu = struct.unpack_from("<QQQ", archive, 48)
    block_count = struct.unpack_from("<Q", archive, 72)[0]
    gen = _unpad(archive[80:96])

    if major != FORMAT_MAJOR:
        raise ContainerError("E-FMT-HEAD-005", f"unsupported format major {major}")
    if flags & FLAGS_MUST_UNDERSTAND_MASK:
        raise ContainerError(
            "E-FMT-HEAD-002",
            f"unknown must-understand flag bits set: 0x{flags & 0xFF:02x}",
        )
    if codec_id != CODEC_ID_ZSTD:
        raise ContainerError("E-CMP-006", f"unknown codec id {codec_id!r}")
    if block_count < 1:
        raise ContainerError("E-FMT-IDX-002", "block_count must be >= 1")
    min_size = HEADER_SIZE + block_count * INDEX_ENTRY_SIZE + TRAILER_SIZE
    if len(archive) < min_size:
        raise ContainerError(
            "E-FMT-IDX-003",
            f"file shorter than header+index+trailer minimum ({min_size} needed)",
        )
    return ArchiveInfo(FORMAT_MAJOR, minor, flags, codec_id, canon_ver,
                       max_bu, max_bc, max_tu, gen, [])


def read_index(archive: bytes) -> tuple[ArchiveInfo, int, int]:
    """Validate trailer+index fully (before decoding any block) and return
    (info with block entries populated, index_offset, index_bytes).

    Trailer per ADR-0007 as accepted: 40 bytes = u64 index_offset + u64
    index_bytes + 24-byte *prefix* of SHA-256(index region) (the draft's own
    arithmetic: "fixed 40 bytes" with two u64 leaves 24 for the digest;
    recorded as Amendment 3 in the ADR). Header checksum remains full 32 B."""
    info = unpack_header(archive)
    file_len = len(archive)
    t_off = file_len - TRAILER_SIZE
    idx_off, idx_len = struct.unpack_from("<QQ", archive, t_off)
    idx_hash = archive[t_off + 16:t_off + TRAILER_SIZE]  # 24-byte SHA-256 prefix
    if idx_off < HEADER_SIZE or idx_len % INDEX_ENTRY_SIZE or idx_off + idx_len > t_off:
        raise ContainerError("E-FMT-IDX-001",
                             f"index region [{idx_off},{idx_off + idx_len}) invalid")
    index_region = archive[idx_off:idx_off + idx_len]
    if hashlib.sha256(index_region).digest()[:TRAILER_SIZE - 16] != idx_hash:
        raise ContainerError("E-FMT-IDX-004", "index checksum mismatch")
    count = idx_len // INDEX_ENTRY_SIZE
    if count != struct.unpack_from("<Q", archive, 72)[0]:
        raise ContainerError("E-FMT-IDX-002",
                             f"header block_count {struct.unpack_from('<Q', archive, 72)[0]} != index entries {count}")
    entries: list[BlockEntry] = []
    cursor = HEADER_SIZE
    total_unc = 0
    for i in range(count):
        off, csz, usz, digest = struct.unpack_from("<QQQ32s", index_region, i * INDEX_ENTRY_SIZE)
        if off != cursor:
            raise ContainerError("E-FMT-IDX-005",
                                 f"block {i} offset {off} not contiguous (expected {cursor})")
        if csz < 4 or off + csz > idx_off:
            raise ContainerError("E-FMT-IDX-001", f"block {i} range past index start")
        if usz > info.max_block_uncompressed:
            raise ContainerError(
                "E-RES-001",
                f"block {i} declared uncompressed {usz} > limit {info.max_block_uncompressed}",
            )
        if csz > info.max_block_compressed:
            raise ContainerError(
                "E-RES-002",
                f"block {i} declared compressed {csz} > limit {info.max_block_compressed}",
            )
        total_unc += usz
        if total_unc > info.max_total_uncompressed:
            raise ContainerError("E-RES-003", "Σ block sizes exceed archive ceiling")
        entries.append(BlockEntry(off, csz, usz, digest))
        cursor += csz
    if cursor != idx_off:
        raise ContainerError("E-FMT-IDX-003",
                             f"blocks end at {cursor}, index starts at {idx_off}")
    info.blocks = entries
    return info, idx_off, idx_len


def unpack(archive: bytes, *, only_block: int | None = None) -> bytes:
    """Decode a `.lxz` v0 archive to its original bytes.

    `only_block=N` performs bounded decode of block N alone (REQ-CMP-005)
    without touching other blocks' payloads.
    """
    info, _, _ = read_index(archive)
    if only_block is not None:
        if not (0 <= only_block < len(info.blocks)):
            raise ContainerError("E-FMT-IDX-006", f"block index {only_block} out of range")
        want = [info.blocks[only_block]]
    else:
        want = info.blocks

    out = bytearray()
    for i, e in enumerate(want if only_block is None else [e for e in want]):
        frame = archive[e.offset:e.offset + e.compressed_size]
        if frame[:4] != b"\x28\xB5\x2F\xFD":
            raise ContainerError("E-CMP-003", f"block {i} is not a zstd frame")
        try:
            payload = decompress(frame, expected_original_size=e.uncompressed_size)
        except CodecError as exc:
            raise ContainerError("E-CMP-004", f"block {i} decode failed: {exc}") from exc
        if hashlib.sha256(payload).digest() != e.sha256:
            # per-block granularity: zero output for THIS block (REQ-SEC-004)
            raise ContainerError("E-INTEGRITY-001",
                                 f"block {i} sha256 mismatch — refusing block, zero output")
        out += payload
    return bytes(out)


def unpack_blocks(archive: bytes) -> tuple[bytes, list[str]]:
    """Best-effort multi-block read at per-block granularity (ADR-0007
    Semantics): returns concatenated bytes of all blocks that verified, plus a
    list of refusal codes for blocks that did not. Integrity failure of one
    block never yields partial output FOR THAT BLOCK, but independent blocks
    still decode."""
    info, _, _ = read_index(archive)
    ok = bytearray()
    failures: list[str] = []
    for i, e in enumerate(info.blocks):
        try:
            ok += unpack(archive, only_block=i)
        except ContainerError as exc:
            failures.append(f"block {i}: {exc.code}")
    return bytes(ok), failures


@dataclass(frozen=True)
class VerifyResult:
    """Outcome of verify_archive(): structural verdict + per-block detail.

    `ok` is True only when header+index validated AND every block decoded and
    matched its index SHA-256. A container-level refusal during structural
    validation is recorded in `error` (code/message); per-block integrity
    failures appear in `blocks` with ok=False."""
    ok: bool
    error: str | None
    block_count: int
    blocks: tuple[tuple[int, bool, str | None], ...]  # (index, ok, code|None)


def verify_archive(archive: bytes) -> VerifyResult:
    """Public structural+integrity verification WITHOUT producing payload
    bytes. Reader-rule validation runs first (header checksum, flags, codec
    id, index/trailer consistency, limit checks — REQ-SEC-001); then each
    block is decoded and hash-checked independently so callers get a
    per-block verdict (ADR-0007 per-block semantics).

    Added Session 25: needed by the future GUI archive inspector (G4,
    docs/DESIGN_GUI.md) and any audit tooling; library-only for now — no CLI
    surface until a flag is actually requested (scope honesty)."""
    try:
        info, _, _ = read_index(archive)
    except ContainerError as exc:
        return VerifyResult(False, f"{exc.code}: {exc}", 0, ())
    results: list[tuple[int, bool, str | None]] = []
    for i, e in enumerate(info.blocks):
        try:
            unpack(archive, only_block=i)
            results.append((i, True, None))
        except ContainerError as exc:
            results.append((i, False, exc.code))
    ok = all(r[1] for r in results)
    return VerifyResult(ok, None, len(info.blocks), tuple(results))
