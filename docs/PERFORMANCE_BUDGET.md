# LEXORA Performance Budget

> **Status:** Draft (targets are *proposed* engineering budgets; the memory rows below now carry live measurements — updated 2026-10-28, Session 39)
> **Owner:** Documentation architect (delegated)
> **Related:** [RESOURCE_LIMITS.md](RESOURCE_LIMITS.md) · [BENCHMARK_PROTOCOL.md](BENCHMARK_PROTOCOL.md) · [PHASES.md](PHASES.md)

## Purpose & scope

Numeric performance/memory envelopes each phase must fit into, the reference machine definition, and how compliance is proven. Budgets bind implementation choices before code is written (design-time constraint), and are re-checked at every phase exit.

## Reference machine (to be confirmed by owner — OQ-7 related)

Proposed profile "REF-4G": x86-64 laptop-class CPU, **4 GiB RAM total**, spinning or SATA SSD, Linux or Windows, no GPU. All budget statements below assume REF-4G unless noted. If the owner designates a different reference machine, budgets get revised via DECISIONS entry.

## Memory budgets (peak RSS, whole process tree)

| Operation | Proposed budget | Rationale / status |
|---|---|---|
| Canonicalize one document (streaming) | ≤ 256 MiB | Sized for multi-MB documents without full-load; Not yet measured (canon path still reads whole input) |
| Encode block (Zstd level default core) | ≤ 512 MiB | **Measured 2026-10-28:** streaming CLI default plateaus at **~126 MiB** from one full block upward (32 MiB → 126.1, 64 MiB → 126.2 MiB peak RSS), so the budget holds independently of document size. The pre-streaming buffered path (`--no-stream`) grew ~4.8 MiB per MiB of input and would have breached at a ~95 MiB document. Artifact: `benchmarks/results-rss-core.json` |
| Decode single block/document | ≤ 256 MiB | **Measured 2026-10-28:** PASS at every size tested (28.3 MiB at 1 MiB input → 188.6 MiB at 64 MiB input) **but the default whole-file `unpack` path is still buffered** (~2.9 MiB peak per MiB of input) and would reach the budget around an ~85 MiB document. Bounded `--block N` decode (REQ-CMP-005) is the only streaming read path today — streaming `unpack` is an open item |
| Benchmark baseline runs (external tools) | tool-dependent, recorded separately | Zstd-19/Brotli q11/XZ -9 can exceed budgets ⇒ run as separate processes with own limits; failures logged honestly |
| Whole pipeline headroom | peak ≤ 3 GiB of 4 GiB host | OS + Python interpreter allowance; Not yet measured (encode path alone is ~126 MiB streaming, so headroom is not the binding constraint) |

## Throughput budgets (soft targets, informational only)

| Path | Proposed target | Status |
|---|---|---|
| Canonicalization | ≥ 5 MB/s text | Not yet measured |
| Core encode (level tuned for default) | ≥ 2 MB/s | Not yet measured |
| Core decode | ≥ 20 MB/s | Not yet measured |

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
