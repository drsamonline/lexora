# ADR-0007: `.lxz` v0 container — layout freeze, scope cut, and status flip

> **Status:** **Proposed** — awaiting explicit owner accept/amend/reject (OQ-11 in [../DECISIONS.md](../DECISIONS.md)). Until accepted, [FORMAT_LXZ.md](../FORMAT_LXZ.md) remains PROPOSED and implementing a container from it is forbidden by policy (SPEC §7.2).
> **Date:** 2026-10-16 (drafted Session 20 under standing documentation delegation; *acceptance requires the owner because this ADR fixes normative bytes*)
> **Deciders:** Documentation architect drafted; owner Dr. Sohil Momin must accept
> **Related:** [FORMAT_LXZ.md](../FORMAT_LXZ.md) · [SPECIFICATION.md](../SPECIFICATION.md) §7–§9 · [RESOURCE_LIMITS.md](../RESOURCE_LIMITS.md) · REQ-FMT-001…003 · REQ-CMP-005/006 · REQ-SEC-001/004 · P1-T3 / P1-T5

## Context / Problem

Phase 1's remaining high-value work (P1-T3 format freeze → P1-T5 `pack`/`unpack`) is blocked on one decision: FORMAT_LXZ.md deliberately contains **no byte layout** ("Do not implement decoders from this document"). Every attempt to "build the whole app" (owner directive 2026-10-16, English-only velocity) stalls at the container. The requirements the format must satisfy are already accepted (SPEC §7.1: magic, versions, codec/profile IDs, checksums, index, in-archive limits, feature flags, provenance, hash-verified dictionary refs); what is missing is a frozen, testable serialization of them.

Freezing the *full* intended format now (multi-block, per-document random access, embedded dictionaries, encryption hooks) would be invented complexity with zero measured need — the only codec that exists is single-frame Zstd (`zstd_core.py`).

## Options considered

- **A. Freeze a minimal `.lxz` v0 now (this ADR).** One container = one or more blocks, each block = one plain zstd frame (the existing codec output, unchanged); trailer index gives *block-level* bounded decode; all SPEC §7.1 required header elements present; exact byte layout below; golden test vectors committed with the implementation. Multi-document *packing semantics*, dictionaries, and encryption stay out of v0 scope.
- **B. Freeze the full long-term layout up front.** All fields for grammars, dictionaries, AEAD, per-document offsets sized and reserved now. Cost: many normative numbers chosen before any measurement; high regret risk; contradicts "measure first" project culture.
- **C. Keep deferring the freeze.** Zero container progress; P1-T5 impossible; app-build velocity directive unfulfilled. Rejected as status quo.

## Decision (proposed — Option A)

On acceptance, the following becomes the normative `.lxz` v0 layout. Version identifier: `LXZ-0.1`. Everything is little-endian; integers are fixed-width (no varints — hostile-input validation stays trivial).

### Header (fixed 96 bytes, offset 0)

| Off | Width | Field | Value / rule |
|---|---|---|---|
| 0 | 4 | magic | `4C 58 5A 7C` ("LXZ\|") — early rejection of wrong files |
| 4 | 2 | format_major | `0` |
| 6 | 2 | format_minor | `1` (v0 = minor-stream within major 0) |
| 8 | 8 | flags | bit0 = must-understand mask start; bits 0–7 must-understand, bits 8–63 may-ignore. v0 writer emits `0`; reader refuses any nonzero **must-understand** bit (REQ-FMT-003) |
| 16 | 16 | codec_id | NUL-padded ASCII, v0 fixed `"zstd-raw-l19"` (registry ID from `lexora.CODEC_ID_ZSTD`; unknown ⇒ hard refusal, REQ-CMP-006) |
| 32 | 16 | canonicalizer_version | NUL-padded ASCII, e.g. `"lexcan-0.1"` (REQ-CAN-004) |
| 48 | 8 | max_block_uncompressed | LIM-01 declaration; reader enforces before allocation (REQ-SEC-001). v0 default `8388608` (8 MiB) |
| 56 | 8 | max_block_compressed | LIM-02; v0 default `16777216` (16 MiB) |
| 64 | 8 | max_total_uncompressed | archive-wide ceiling; v0 default `1<<34` (generator must respect; reader pre-validates Σ declared block sizes ≤ this) |
| 72 | 8 | block_count | N ≥ 1; also bounded by LIM-03 chain (N × header-of-index ≤ file size check) |
| 80 | 8 | header_sha256_partial | SHA-256 over header bytes [0,80) stored in first 8 bytes (truncated match; full 32-byte variant rejected to keep width fixed) — detects header corruption before trusting any length field |
| 88 | 8 | generator_version | NUL-padded ASCII tool version (provenance, REQ-ING-004 spirit) |

### Block region (variable, starts at offset 96)

Blocks concatenated in order, no padding. Each block MUST be exactly one complete zstd frame (magic `28 B5 2F FD` prefix check before decode). Frame content-size field MUST equal the block's uncompressed size recorded in the index; mismatch ⇒ refuse (length-before-allocation).

### Index (immediately after last block)

`block_count` entries × 48 bytes: `{ u64 offset_in_file; u64 compressed_size; u64 uncompressed_size; 32-byte sha256 of *uncompressed* block bytes }`. Offsets relative to file start. Reader validates every entry against file size and header limits **before** reading any payload (REQ-SEC-001). Index-at-trailer trade-off accepted for v0 (random access > streaming write; streaming writer can be added as may-ignore flag later).

### Trailer (fixed 40 bytes, file end)

`{ u64 index_offset; u64 index_bytes; 32-byte sha256 over index region }`. Locator-first read; index hash verified before index parse.

### Semantics

- **Checksums:** per-block SHA-256 over uncompressed bytes, verified after decode; mismatch ⇒ that block refused with specific error, zero output for it (REQ-SEC-004). Other independent blocks MAY decode (per-block granularity chosen here; supersedes FORMAT_LXZ "pending" note).
- **Bounded decode (REQ-CMP-005):** v0 supports decode-by-block-index without loading other blocks (whole-file residency NOT required; mmap/stream acceptable). Per-document indexing is out of v0 scope — see Consequences.
- **Round-trip contract (SPEC §8.1):** `pack` verifies decode(encode)==input for 100% of blocks before reporting success; failure ⇒ non-zero exit, no archive written.
- **Provenance:** source filename/encoding recorded per *archive* in an optional may-ignore metadata section is deferred; v0 stores only header versions + generator. Honest limitation, listed in FORMAT_LXZ update.

## Consequences and trade-offs

- (+) Unblocks P1-T3/P1-T5 immediately after acceptance; golden vectors become writable because bytes are defined.
- (+) Codec path is *already implemented and tested* (`zstd_core.py`) — v0 adds framing/index/checksum logic only, minimal new risk surface.
- (−) v0 containers hold one logical stream split into blocks, **not** multi-document archives; the eventual document layer will extend via format_minor bump + may-ignore flags, or supersede via new ADR. Documents that cite ".lxz = archive of documents" must be re-read as future intent until then.
- (−) Fixed 8-MiB block ceiling may be suboptimal; revisited when RSS data exists (P1-T6).
- (−) Truncated-SHA256 header checksum (8 bytes) is collision-*resistant enough for corruption detection but not adversarial forgery; documented, THREAT_MODEL TM row to note it.
- If rejected: record owner's amendment; nothing else changes this session beyond OQ-11 closure.

## Security / performance / compatibility impact

Reader enforces limits before allocation everywhere (REQ-SEC-001); unknown must-understand flags / codec IDs / major≠0 ⇒ refusal with zero output (REQ-CMP-006). No decompression-bomb exposure beyond validated ceilings. Major-version rule per COMPATIBILITY_POLICY: v0 readers refuse major≠0; minors are additive-only.

## Verification plan (test vectors shipped with implementation)

1. Golden empty-ish archive (1 block, 1 byte payload) — exact bytes committed at `tests/vectors/lxz_format/`.
2. Round-trip property tests incl. block-boundary sizes (limit−1, limit, limit+1 ⇒ refuse).
3. Hostile negatives: bad magic, truncated header, index offset past EOF, block size > declared limit, checksum-flipped block, unknown codec ID, must-understand flag set — each asserts specific error code + zero output bytes.
4. Determinism: same input+level ⇒ byte-identical archive (library version pinned in env capture).

## What acceptance changes in the repo

- FORMAT_LXZ.md status flips PROPOSED → **Accepted v0 (frozen above; still experimental)** with the layout section replaced by this ADR's tables (pointer, not duplication).
- SPEC §7.2 note updated to reference ADR-0007.
- DECISIONS.md: OQ-11 row resolved; P1-T3 marked complete-on-implementation.
- Implementation lands in `src/lexora/container.py` + CLI `pack`/`unpack` + `docs/CLI_REFERENCE.md` (P1-T5), only **after** owner acceptance.
