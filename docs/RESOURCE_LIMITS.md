# LEXORA Resource Limits

> **Status:** Draft (candidate values proposed; become normative only at `.lxz` v0 format freeze via ADR — verified 2026-10-15)
> **Owner:** Documentation architect (delegated)
> **Related:** [PERFORMANCE_BUDGET.md](PERFORMANCE_BUDGET.md) · [FORMAT_LXZ.md](FORMAT_LXZ.md) · [SPECIFICATION.md](SPECIFICATION.md) §4 · [THREAT_MODEL.md](THREAT_MODEL.md)

## Purpose & scope

Hard ceilings the encoder may emit and the decoder must enforce, so hostile or oversized archives cannot exhaust a ~4 GiB machine. Every limit is declared in-archive where applicable (REQ-FMT-002) and checked *before* allocation.

## Limit table (candidates)

| ID | Resource | Proposed max | Enforced by | Status |
|---|---|---|---|---|
| LIM-01 | Block uncompressed size | 8 MiB | reader pre-allocation check | Candidate |
| LIM-02 | Compressed block size | 16 MiB (never > input cap + margin rule) | reader | Candidate |
| LIM-03 | Document count per `.lxz` | 1,000,000 | index parse bound | Candidate |
| LIM-04 | Index bytes per document | 4 KiB | reader | Candidate |
| LIM-05 | Embedded dictionary size | 100 MiB | header check before read | Candidate |
| LIM-06 | Grammar/side-table size (Re-Pair etc.) | 64 MiB | codec profile rules | Candidate |
| LIM-07 | Metadata (provenance strings) total | 1 MiB/document | reader | Candidate |
| LIM-08 | Filename/path length stored | 1024 UTF-8 bytes | reader | Candidate |
| LIM-09 | Total archive size sanity | ≤ declared-cap multiplier of disk target | CLI guard (warn) | Advisory |
| LIM-10 | Canonicalizer working set | per PERFORMANCE_BUDGET streaming budgets | canon engine | Candidate |

Values above are engineering candidates chosen to fit REF-4G; none are measured yet. Format-freeze ADR will pick final numbers and wire them into FORMAT_LXZ field widths.

## Decoder enforcement rules (normative intent for SPEC §4.5)

1. Validate magic/version/limits **before** trusting any length field.
2. Reject when: declared limit exceeded, length inconsistent with file size, checksum mismatch, unknown must-understand feature, unknown codec ID → specific error code, zero output bytes written (REQ-CMP-006).
3. Never grow memory proportional to an unvalidated field (allocation after validation only; REQ-SEC-001).
4. Streaming decode path must not require whole-archive residency (REQ-CMP-005); random access via index only.

## Encoder rules

- Encoder refuses inputs exceeding limits at pack time with actionable message (e.g., split document, raise block size if allowed by profile).
- Encoder writes actual effective limits into header so decoders need no out-of-band config.

## Hostile-input posture

Truncated files, absurd declared sizes, repeated headers, unicode-normalization bombs in metadata strings: all covered by negative tests T-FMT-102 / fuzz layer (TEST_STRATEGY layers 5–6). Fuzzing starts as soon as a decoder exists (P1 exit → P6 campaign).

## Open items

- Final numeric values pending first RSS measurements (P1-T6).
- Whether LIM-05/06 apply to external dictionaries charged differently → COST_MODEL/BENCHMARK_PROTOCOL §4 already defines accounting; limits remain per-archive.
