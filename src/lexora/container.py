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

from lexora import CANONICALIZER_VERSION, CODEC_ID_ZSTD, DEFAULT_LEVEL, __version__
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


def pack(data: bytes, *, level: int = DEFAULT_LEVEL,
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
    header = _build_header(
        block_size=block_size,
        max_block_compressed=max_block_compressed,
        max_total_uncompressed=max_total_uncompressed,
        block_count=len(entries),
        gen=gen,
    )

    trailer = struct.pack("<QQ", index_offset, len(index))
    trailer += hashlib.sha256(bytes(index)).digest()[:TRAILER_SIZE - 16]  # 24-byte prefix (see read_index note)

    archive = bytes(header) + bytes(blocks_region) + bytes(index) + trailer
    # whole-archive self-check: a reader must accept what we just wrote.
    verified, _, _ = read_index(archive)
    if len(verified.blocks) != len(entries):
        raise ContainerError("E-INT-001", "self-verify index mismatch")
    return archive


def _build_header(*, block_size: int, max_block_compressed: int,
                  max_total_uncompressed: int, block_count: int, gen: str) -> bytes:
    """Serialize the fixed 128-byte header (ADR-0007 layout, flags = 0)."""
    header = bytearray(BLOCK_START)
    header[0:4] = MAGIC
    struct.pack_into("<HH", header, 4, FORMAT_MAJOR, FORMAT_MINOR)
    struct.pack_into("<Q", header, 8, 0)  # flags: v0 writer emits 0
    header[16:32] = _pad(CODEC_ID_ZSTD, 16)
    header[32:48] = _pad(CANONICALIZER_VERSION, 16)
    struct.pack_into("<Q", header, 48, block_size)
    struct.pack_into("<Q", header, 56, max_block_compressed)
    struct.pack_into("<Q", header, 64, max_total_uncompressed)
    struct.pack_into("<Q", header, 72, block_count)
    header[80:96] = _pad(gen, 16, truncate=True)
    header[CHECKSUM_REGION:HEADER_SIZE] = hashlib.sha256(bytes(header[:CHECKSUM_REGION])).digest()
    return bytes(header)


def pack_stream(src, dst, *, level: int = DEFAULT_LEVEL,
                block_size: int = DEFAULT_MAX_BLOCK_UNCOMPRESSED,
                max_block_compressed: int = DEFAULT_MAX_BLOCK_COMPRESSED,
                max_total_uncompressed: int = DEFAULT_MAX_TOTAL_UNCOMPRESSED,
                generator_version: str | None = None) -> ArchiveInfo:
    """Serialize `src` (binary readable) into `dst` (binary, seekable) with
    memory bounded by ONE block instead of the whole input.

    Why this exists: `pack()` needs the entire payload in memory, and slicing it
    into blocks copies it a second time, so peak RSS grows with input size
    (measured: ~4.6 MiB peak per MiB of input, i.e. the 512 MiB encode budget in
    docs/PERFORMANCE_BUDGET.md was breached around a ~100 MiB document — see
    benchmarks/results-rss-core.json). This path holds one block buffer plus one
    compressed frame, so peak RSS is flat in input size.

    Contract:
      * Output is BYTE-IDENTICAL to `pack(src.read(), ...)` with the same
        arguments (same block boundaries, same frames, same index) — the frozen
        LXZ-0.1 layout is not touched, only how it is produced.
      * Round-trip gate is preserved: every block is decoded and compared
        before its frame is kept (SPEC §8.1), so a codec defect never yields a
        "successful" archive.
      * On limit violation the archive is abandoned: the caller is expected to
        write through a temp file and rename (the CLI does), so no partial
        artifact survives.
      * `dst` must be seekable — the header carries the block count, which is
        only known after the last block is written, so the header is backfilled.
        Non-seekable destinations raise E-USAGE-003.
    """
    if block_size < 1:
        raise ContainerError("E-USAGE-002", "block_size must be >= 1")
    if not (hasattr(dst, "seek") and hasattr(dst, "tell")):
        raise ContainerError("E-USAGE-003", "pack_stream() needs a seekable dst")

    gen = generator_version or f"lexora-{__version__}"
    dst.write(b"\x00" * HEADER_SIZE)  # placeholder; backfilled once the count is known

    entries: list[BlockEntry] = []
    offset = BLOCK_START
    total = 0
    emitted = 0

    def emit(chunk: bytes) -> None:
        nonlocal offset, emitted
        frame = compress(chunk, level=level)
        if len(frame) > max_block_compressed:
            raise ContainerError(
                "E-RES-002",
                f"block compressed {len(frame)} > max_block_compressed {max_block_compressed}",
            )
        back = decompress(frame, expected_original_size=len(chunk))
        if back != chunk:
            raise CodecError("block round-trip mismatch (should be impossible)")
        entries.append(BlockEntry(
            offset=offset,
            compressed_size=len(frame),
            uncompressed_size=len(chunk),
            sha256=hashlib.sha256(chunk).digest(),
        ))
        dst.write(frame)
        offset += len(frame)
        emitted += 1

    while True:
        chunk = src.read(block_size)
        if not chunk:
            break
        total += len(chunk)
        if total > max_total_uncompressed:
            raise ContainerError(
                "E-RES-003",
                f"input exceeds max_total_uncompressed {max_total_uncompressed}",
            )
        emit(chunk)
    if emitted == 0:  # empty input keeps pack()'s single empty block
        emit(b"")

    index = bytearray()
    for e in entries:
        index += struct.pack("<QQQ", e.offset, e.compressed_size, e.uncompressed_size)
        index += e.sha256
    assert len(index) == INDEX_ENTRY_SIZE * len(entries)

    index_offset = BLOCK_START + (offset - BLOCK_START)
    trailer = struct.pack("<QQ", index_offset, len(index))
    trailer += hashlib.sha256(bytes(index)).digest()[:TRAILER_SIZE - 16]
    dst.write(bytes(index))
    dst.write(trailer)
    end = dst.tell()  # true EOF, captured before the header backfill moves the cursor

    header = _build_header(
        block_size=block_size,
        max_block_compressed=max_block_compressed,
        max_total_uncompressed=max_total_uncompressed,
        block_count=len(entries),
        gen=gen,
    )
    dst.seek(0)
    dst.write(header)
    dst.flush()

    # self-check on the bytes actually on disk: header, trailer and index must
    # agree before we let the caller rename the temp file into place.
    dst.seek(0)
    written_header = dst.read(HEADER_SIZE)
    if written_header != header:
        raise ContainerError("E-INT-002", "streamed header did not persist")
    dst.seek(end - TRAILER_SIZE)
    written_trailer = dst.read(TRAILER_SIZE)
    if written_trailer != trailer:
        raise ContainerError("E-INT-003", "streamed trailer did not persist")
    idx_off, idx_len = struct.unpack_from("<QQ", written_trailer, 0)
    dst.seek(idx_off)
    if dst.read(idx_len) != bytes(index):
        raise ContainerError("E-INT-004", "streamed index did not persist")
    dst.seek(end)

    return ArchiveInfo(
        format_major=FORMAT_MAJOR,
        format_minor=FORMAT_MINOR,
        flags=0,
        codec_id=CODEC_ID_ZSTD,
        canonicalizer_version=CANONICALIZER_VERSION,
        max_block_uncompressed=block_size,
        max_block_compressed=max_block_compressed,
        max_total_uncompressed=max_total_uncompressed,
        generator_version=gen[:15],
        blocks=entries,
    )


def unpack_header(archive: bytes) -> ArchiveInfo:
    """Parse+validate ONLY the header (no payload touched). All refusals are
    length-checked before allocation (REQ-SEC-001)."""
    if len(archive) < HEADER_SIZE + TRAILER_SIZE:
        raise ContainerError("E-FMT-HEAD-003",
                             f"file too short for header+trailer: {len(archive)} bytes")
    return _validate_header(archive[:HEADER_SIZE], len(archive))


def _validate_header(header: bytes, file_len: int) -> ArchiveInfo:
    """Header rules over a 128-byte slice plus the archive's true length.

    Split out of unpack_header() so the streaming reader can validate a header
    it read from a file handle without materialising the whole archive."""
    if header[0:4] != MAGIC:
        raise ContainerError("E-FMT-HEAD-001", "bad magic (not an .lxz archive)")
    stored = header[CHECKSUM_REGION:HEADER_SIZE]
    computed = hashlib.sha256(header[:CHECKSUM_REGION]).digest()
    if stored != computed:
        raise ContainerError("E-FMT-HEAD-004", "header checksum mismatch (corrupt header)")

    major, minor = struct.unpack_from("<HH", header, 4)
    flags = struct.unpack_from("<Q", header, 8)[0]
    codec_id = _unpad(header[16:32])
    canon_ver = _unpad(header[32:48])
    max_bu, max_bc, max_tu = struct.unpack_from("<QQQ", header, 48)
    block_count = struct.unpack_from("<Q", header, 72)[0]
    gen = _unpad(header[80:96])

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
    # RESOURCE_LIMITS promises the reader enforces LIM-01/LIM-02 as ceilings, but
    # until Session 54 it only enforced whatever the header DECLARED — so a hostile
    # header could raise its own limits to 2^60 and defeat every pre-allocation
    # check downstream. The declared caps may be *stricter* than the ceiling,
    # never looser.
    if max_bu > DEFAULT_MAX_BLOCK_UNCOMPRESSED:
        raise ContainerError(
            "E-RES-004",
            f"declared max_block_uncompressed {max_bu} exceeds LIM-01 ceiling "
            f"{DEFAULT_MAX_BLOCK_UNCOMPRESSED}",
        )
    if max_bc > DEFAULT_MAX_BLOCK_COMPRESSED:
        raise ContainerError(
            "E-RES-004",
            f"declared max_block_compressed {max_bc} exceeds LIM-02 ceiling "
            f"{DEFAULT_MAX_BLOCK_COMPRESSED}",
        )
    if max_tu > DEFAULT_MAX_TOTAL_UNCOMPRESSED:
        raise ContainerError(
            "E-RES-004",
            f"declared max_total_uncompressed {max_tu} exceeds the archive ceiling "
            f"{DEFAULT_MAX_TOTAL_UNCOMPRESSED}",
        )
    min_size = HEADER_SIZE + block_count * INDEX_ENTRY_SIZE + TRAILER_SIZE
    if file_len < min_size:
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
    file_len = len(archive)
    if file_len < HEADER_SIZE + TRAILER_SIZE:
        raise ContainerError("E-FMT-HEAD-003",
                             f"file too short for header+trailer: {file_len} bytes")
    return _read_index_parts(
        archive[:HEADER_SIZE],
        file_len,
        archive[file_len - TRAILER_SIZE:file_len],
        lambda off, n: archive[off:off + n],
    )


def _read_index_parts(header: bytes, file_len: int, trailer: bytes, fetch) -> tuple[ArchiveInfo, int, int]:
    """Shared index validation. `fetch(offset, length)` returns bytes from the
    archive, which lets the same rules run over an in-memory buffer or a file
    handle (see read_index_stream)."""
    info = _validate_header(header, file_len)
    t_off = file_len - TRAILER_SIZE
    idx_off, idx_len = struct.unpack_from("<QQ", trailer, 0)
    idx_hash = trailer[16:TRAILER_SIZE]  # 24-byte SHA-256 prefix
    if idx_off < HEADER_SIZE or idx_len % INDEX_ENTRY_SIZE or idx_off + idx_len > t_off:
        raise ContainerError("E-FMT-IDX-001",
                             f"index region [{idx_off},{idx_off + idx_len}) invalid")
    index_region = fetch(idx_off, idx_len)
    if len(index_region) != idx_len:
        raise ContainerError("E-FMT-IDX-001",
                             f"index region truncated ({len(index_region)} of {idx_len} bytes)")
    if hashlib.sha256(index_region).digest()[:TRAILER_SIZE - 16] != idx_hash:
        raise ContainerError("E-FMT-IDX-004", "index checksum mismatch")
    count = idx_len // INDEX_ENTRY_SIZE
    if count != struct.unpack_from("<Q", header, 72)[0]:
        raise ContainerError("E-FMT-IDX-002",
                             f"header block_count {struct.unpack_from('<Q', header, 72)[0]} != index entries {count}")
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


def read_index_stream(src) -> tuple[ArchiveInfo, int, int]:
    """read_index() over a seekable file handle: reads the 128-byte header, the
    40-byte trailer and the index region — never a block payload.

    Index size is 56 bytes per block (LIM-04 bounds a single entry at 4 KiB but
    the region itself grows with block count), so this is the only part of a
    large archive that is ever fully resident.
    """
    if not (hasattr(src, "seek") and hasattr(src, "tell")):
        raise ContainerError("E-USAGE-004", "read_index_stream() needs a seekable src")
    src.seek(0, 2)
    file_len = src.tell()
    if file_len < HEADER_SIZE + TRAILER_SIZE:
        raise ContainerError("E-FMT-HEAD-003",
                             f"file too short for header+trailer: {file_len} bytes")
    src.seek(0)
    header = src.read(HEADER_SIZE)
    src.seek(file_len - TRAILER_SIZE)
    trailer = src.read(TRAILER_SIZE)

    def fetch(off: int, n: int) -> bytes:
        src.seek(off)
        return src.read(n)

    return _read_index_parts(header, file_len, trailer, fetch)


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


def unpack_stream(src, dst, *, only_block: int | None = None) -> tuple[ArchiveInfo, int]:
    """Decode a `.lxz` archive from a seekable handle into `dst`, one block at a
    time — the mirror of pack_stream().

    Why this exists: `unpack()` needs the whole archive AND the whole output in
    memory, so decode peak RSS tracked archive size (~2.9 MiB peak per MiB of
    input; the 256 MiB decode budget in docs/PERFORMANCE_BUDGET.md was reached
    near an ~85 MiB archive). Here the resident set is the index plus ONE block
    (compressed frame + decoded bytes), so it does not grow with archive size.

    Guarantees kept from unpack():
      * index is fully validated BEFORE any block is read (REQ-SEC-001);
      * each block's sha256 is checked against the index before its bytes are
        written, so a corrupt block contributes zero output (REQ-SEC-004);
      * `only_block=N` still decodes exactly one block (REQ-CMP-005).

    `dst` is written sequentially; atomicity is the caller's concern (the CLI
    writes through a temp file and renames). Returns (info, bytes_written).
    """
    info, _, _ = read_index_stream(src)
    if only_block is not None:
        if not (0 <= only_block < len(info.blocks)):
            raise ContainerError("E-FMT-IDX-006", f"block index {only_block} out of range")
        wanted: range | list[int] = [only_block]
    else:
        wanted = range(len(info.blocks))

    written = 0
    for i in wanted:
        e = info.blocks[i]
        src.seek(e.offset)
        frame = src.read(e.compressed_size)
        if len(frame) != e.compressed_size:
            raise ContainerError("E-FMT-IDX-001",
                                 f"block {i} truncated ({len(frame)} of {e.compressed_size} bytes)")
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
        dst.write(payload)
        written += len(payload)
        del frame, payload  # keep the resident set at one block
    return info, written


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


def verify_stream(src, *, only_block: int | None = None) -> VerifyResult:
    """Structural + per-block integrity verification over a seekable handle.

    Same verdict as verify_archive(), but the archive is never resident: the
    index is validated first (reader rules — header checksum, flags, codec id,
    index/trailer consistency, limits), then each block is decoded and
    hash-checked in turn. Verification is **best-effort per block**: one corrupt
    block does not stop the report, because an audit wants to know how much of an
    archive is salvageable, not just that something is wrong (ADR-0007 per-block
    semantics).

    Why this exists alongside verify_archive(): that function called
    `unpack(archive, only_block=i)` per block, and `unpack` re-reads and
    re-validates the whole archive on every call — so verifying an N-block
    archive did N full passes over it. This reads each block exactly once.
    """
    try:
        info, _, _ = read_index_stream(src)
    except ContainerError as exc:
        # exc.__str__ already renders "[code] message"; use the fields to avoid
        # printing the code twice ("E-FMT-IDX-004: [E-FMT-IDX-004] ...").
        return VerifyResult(False, f"{exc.code}: {exc.message}", 0, ())

    if only_block is not None:
        if not (0 <= only_block < len(info.blocks)):
            return VerifyResult(False, f"E-FMT-IDX-006: block index {only_block} out of range",
                                len(info.blocks), ())
        wanted: list[int] | range = [only_block]
    else:
        wanted = range(len(info.blocks))

    results: list[tuple[int, bool, str | None]] = []
    for i in wanted:
        e = info.blocks[i]
        try:
            src.seek(e.offset)
            frame = src.read(e.compressed_size)
            if len(frame) != e.compressed_size:
                raise ContainerError("E-FMT-IDX-001",
                                     f"block {i} truncated ({len(frame)} of {e.compressed_size} bytes)")
            if frame[:4] != b"\x28\xB5\x2F\xFD":
                raise ContainerError("E-CMP-003", f"block {i} is not a zstd frame")
            payload = decompress(frame, expected_original_size=e.uncompressed_size)
            if hashlib.sha256(payload).digest() != e.sha256:
                raise ContainerError("E-INTEGRITY-001",
                                     f"block {i} sha256 mismatch — refusing block, zero output")
            results.append((i, True, None))
        except ContainerError as exc:
            results.append((i, False, exc.code))
        except CodecError as exc:
            results.append((i, False, "E-CMP-004"))
            del exc
        finally:
            frame = None
            payload = None
    ok = all(r[1] for r in results)
    return VerifyResult(ok, None, len(info.blocks), tuple(results))


def verify_archive(archive: bytes) -> VerifyResult:
    """Public structural+integrity verification WITHOUT producing payload bytes.

    Reader-rule validation runs first (header checksum, flags, codec id,
    index/trailer consistency, limit checks — REQ-SEC-001); then each block is
    decoded and hash-checked independently so callers get a per-block verdict
    (ADR-0007 per-block semantics).

    Session 47: now a thin wrapper over verify_stream(), which reads each block
    once. The previous implementation called `unpack(archive, only_block=i)` per
    block, and unpack re-reads and re-validates the entire archive on every call
    — O(blocks) full passes over the buffer. Behaviour is unchanged; the cost is
    not."""
    import io

    return verify_stream(io.BytesIO(archive))