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
| Core encode (level tuned for default) | ≥ 2 MB/s | **Measured — MISS at the current default:** 0.30 MiB/s (1 MiB), 0.43 MiB/s (4 MiB), 0.35 MiB/s (32 MiB) at zstd level 19 on this 2-vCPU container. Soft target, so it does not block, but the gap is ~5×. Level 19 is the reason: the budget's own wording ("level tuned for default") assumes a default chosen for speed, while the CLI still defaults to 19. **Open question for the owner:** keep 19 as the default and revise the target, or lower the default level. |
| Core decode | ≥ 20 MB/s | **Measured — PASS:** 28.5 MiB/s at a 32 MiB archive (1.4 MiB/s at 1 MiB is startup, not throughput). |

Measurement caveat for the three rows above: single runs on a noisy 2-vCPU container, derived from wall time in `benchmarks/results-rss-core.json`. Peak-RSS numbers from this box are stable; **throughput numbers are indicative only** and need the REF-4G-class machine plus BENCHMARK_PROTOCOL §6.3 repeats before anyone quotes them as a result.

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
