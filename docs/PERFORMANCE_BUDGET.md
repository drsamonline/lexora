# LEXORA Performance Budget

> **Status:** Draft (targets are *proposed* engineering budgets; the memory **and** throughput rows below now carry live measurements — updated 2026-10-29, Session 45)
> **Owner:** Documentation architect (delegated)
> **Related:** [RESOURCE_LIMITS.md](RESOURCE_LIMITS.md) · [BENCHMARK_PROTOCOL.md](BENCHMARK_PROTOCOL.md) · [PHASES.md](PHASES.md)

## Purpose & scope

Numeric performance/memory envelopes each phase must fit into, the reference machine definition, and how compliance is proven. Budgets bind implementation choices before code is written (design-time constraint), and are re-checked at every phase exit.

## Reference machine (to be confirmed by owner — OQ-7 related)

Proposed profile "REF-4G": x86-64 laptop-class CPU, **4 GiB RAM total**, spinning or SATA SSD, Linux or Windows, no GPU. All budget statements below assume REF-4G unless noted. If the owner designates a different reference machine, budgets get revised via DECISIONS entry.

## Memory budgets (peak RSS, whole process tree)

| Operation | Proposed budget | Rationale / status |
|---|---|---|
| Canonicalize one document (streaming) | ≤ 256 MiB | **Measured 2026-10-29 (Session 45):** the default `canon` now streams and holds a flat **35.5 MiB** at both a 16 MiB and a 64 MiB document. The pre-Session-45 buffered path held 72.1 MiB at 16 MiB and **216.2 MiB** at 64 MiB — it would have reached this budget near an ~80 MiB document. Artifact: `benchmarks/results-rss-core.json` (`canon_*` keys) |
| Encode block (Zstd level default core) | ≤ 512 MiB | **Measured 2026-10-28:** streaming CLI default plateaus at **~126 MiB** from one full block upward (32 MiB → 126.1, 64 MiB → 126.2 MiB peak RSS), so the budget holds independently of document size. The pre-streaming buffered path (`--no-stream`) grew ~4.8 MiB per MiB of input and would have breached at a ~95 MiB document. Artifact: `benchmarks/results-rss-core.json` |
| Decode single block/document | ≤ 256 MiB | **Measured 2026-10-28, re-measured 2026-10-29 (Session 41):** the default `unpack` now streams block-by-block and holds a flat **~34 MiB** (34.8 MiB at a 32 MiB archive, 34.1 MiB at 64 MiB) — independent of archive size. The pre-Session-41 buffered path (`--no-stream`) grew ~2.8 MiB peak per MiB of input (28.3 MiB at 1 MiB → 116.1 MiB at 32 MiB) and would have reached the budget near an ~85 MiB archive. Artifact: `benchmarks/results-rss-core.json` (`decode_path` marks which reader each row used) |
| Benchmark baseline runs (external tools) | tool-dependent, recorded separately | Zstd-19/Brotli q11/XZ -9 can exceed budgets ⇒ run as separate processes with own limits; failures logged honestly |
| Whole pipeline headroom | peak ≤ 3 GiB of 4 GiB host | OS + Python interpreter allowance; Not yet measured (encode path alone is ~126 MiB streaming, so headroom is not the binding constraint) |

## Throughput budgets (soft targets, informational only)

| Path | Proposed target | Status |
|---|---|---|
| Canonicalization | ≥ 5 MB/s text | **Measured — PASS by a wide margin:** 29.7 MiB/s at a 16 MiB document, 66.1 MiB/s at 64 MiB (streaming default). |
| Core encode (level tuned for default) | ≥ 2 MB/s | **Measured — PASS at the default since Session 53:** `lexora.DEFAULT_LEVEL = 9` (ADR-0012) gives **6.2 MiB/s** on real prose, ~3× the target. At the previous default (19) the same measurement was 0.30–0.71 MiB/s — a 3–7× **miss**, which is what forced the decision. Level 19 remains available explicitly for archival work and still misses the target by design. |
| Core decode | ≥ 20 MB/s | **Measured — PASS:** 28.5 MiB/s at a 32 MiB archive (1.4 MiB/s at 1 MiB is startup, not throughput). |

Measurement caveat for the three rows above: single runs on a noisy 2-vCPU container, derived from wall time in `benchmarks/results-rss-core.json`. Peak-RSS numbers from this box are stable; **throughput numbers are indicative only** and need the REF-4G-class machine plus BENCHMARK_PROTOCOL §6.3 repeats before anyone quotes them as a result.

### Encode level sweep — evidence for the default-level question (Session 46)

Measured on 8 MiB of real Project Gutenberg prose (the first 8 MiB of the tier-1 snapshot, not synthetic text), 8 MiB blocks, one run per level. Artifact: `benchmarks/results-level-sweep.json`; reproduce with `python3 benchmarks/rss_probe.py --level-sweep --sweep-input FILE --overwrite`.

| zstd level | speed | ratio (archive/input) | peak RSS |
|---|---|---|---|
| 1 | 11.7 MiB/s | 0.3863 | 46.5 MiB |
| 3 | **12.8 MiB/s** | 0.3393 | 44.5 MiB |
| 6 | 9.4 MiB/s | 0.3146 | 45.6 MiB |
| 9 | 6.2 MiB/s | 0.3043 | 51.5 MiB |
| 12 | 2.4 MiB/s | 0.2961 | 81.4 MiB |
| 15 | 1.1 MiB/s | 0.2873 | 102.9 MiB |
| 19 (current default) | **0.7 MiB/s** | **0.2678** | 120.1 MiB |

Read across the ends: going from 19 to 3 costs **26.7 % more bytes** and buys **~18× the speed** and 76 MiB less peak RSS. Level 9 sits in the middle (+13.6 % bytes versus 19, ~9× the speed). Levels 1 and 3 are within noise of each other on this box, so no meaning attaches to level 1 looking slower than level 3.

**This is not a decision.** Compression *size* merit is governed by the ADR-0001 gate, not by this table, and one sample is not a benchmark revision. It exists so the owner can pick: keep 19 and revise the soft target, default to 6–9 (meets ≥2 MB/s with a modest size cost), or expose the choice and keep 19 for archival use.

Throughput misses do not block phases unless they force violating memory budgets; compression *size* merit is governed exclusively by ADR-0001 gates, not these numbers.

## Size budgets

- Container overhead per document: proposed ≤ 1 KiB fixed + index bytes; enforced by cost-accounting audit (REQ-CMP-004). Final numbers after `.lxz` v0 freeze.

## Compliance procedure

1. Perf test layer (TEST_STRATEGY layer 8) measures peak RSS via subprocess rusage on REF-4G (or nearest available machine, deviation recorded).
2. Results table appended to BENCHMARK_RESULTS.md environment section per revision.
3. Violation = S2 defect (QUALITY_PLAN); options: shrink block sizes, stream harder, or revise budget via decision record — never silently relax.

## Known open items

- REF-4G confirmation pending owner.
- Block-size defaults undecided → RESOURCE_LIMITS holds candidate values; chosen value becomes normative at format freeze.
