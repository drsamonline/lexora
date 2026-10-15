# LEXORA Logging & Diagnostics

> **Status:** Draft (contract for future implementation; no logger exists — verified 2026-10-15)
> **Owner:** Documentation architect (delegated)
> **Last verified:** 2026-10-15
> **Related:** [ERROR_HANDLING.md](ERROR_HANDLING.md) · [PRIVACY_AND_DATA_HANDLING.md](PRIVACY_AND_DATA_HANDLING.md) · [PERFORMANCE_BUDGET.md](PERFORMANCE_BUDGET.md) · runbooks/

## Purpose & scope

Defines what LEXORA logs, at which level, in what format, and with what privacy constraints — so that a failed benchmark run or refused archive can be diagnosed *without* exposing document contents. Diagnostic quality is itself a requirement: every error code in [ERROR_HANDLING.md](ERROR_HANDLING.md) MUST have enough logged context to reproduce triage steps from a runbook.

## Log levels

| Level | Contents | Default on |
|---|---|---|
| ERROR | Fatal/error-class events with codes + object hashes | Always |
| WARN | Degradations, quarantines, limit near-misses (>90% of a LIM ceiling) | Always |
| INFO | Stage transitions: ingest-start, canonicalize-done(n docs, m quarantined), encode-block(i/N), verify-pass, publish-manifest | Console default |
| DEBUG | Per-candidate cost numbers, codec parameter probes, index walk steps | Opt-in flag |
| TRACE | Byte-offset-level parser decisions; tokenizer class assignments | Opt-in; never in shared bug reports without scrubbing |

## Privacy rules for log content (binding on implementers)

1. **Never log document text** — not bodies, not excerpts, not "first N bytes." Identifiers only: file path basename (configurable to hash-only), content hash, document ID, block index.
2. **Hashes are the join key.** Every logged artifact reference carries its digest so operators can correlate logs ↔ manifests ↔ archives.
3. **Personal-data hosts**: a `--log-sanitize` mode replaces basenames with hashes for P2/P3 corpora ([PRIVACY_AND_DATA_HANDLING.md](PRIVACY_AND_DATA_HANDLING.md) tiers). Recommended default when tier ≥ P2.
4. Bug-report bundles export level ≥ WARN plus a machine-readable run manifest; DEBUG/TRACE excluded unless user explicitly attaches them.

## Formats

- **Console**: human one-liner per event: `LEVEL ts component code? message k=v...`.
- **Structured file**: line-delimited JSON (proposed), one object per event, stable field names: `ts`, `level`, `component`, `event`, `code`, `doc_id`, `sha256`, `block`, `lim_id`, `observed`, `limit`, `msg`. Field set freezes with SPEC approval.
- **Run manifest** (per invocation): argv template with secrets redacted, versions (canonicalizer `lexcan-x.y`, codec registry version, dependency pins), corpus manifest hash, machine profile tag, wall time, peak RSS samples, exit code. This is the primary evidence artifact for benchmarks ([BENCHMARK_PROTOCOL.md](BENCHMARK_PROTOCOL.md)) and triage.

## Key diagnostic events (minimum set)

| Event id | Emitted when | Must include |
|---|---|---|
| run.start / run.finish | Invocation bracket | Run manifest fields |
| ingest.file.rejected | E-INPUT-* | Path/hash, code, reason |
| can.doc.quarantined | E-CAN-* | Doc id, rule id CAN-Rnn |
| cmp.verify.fail | Round-trip mismatch | Doc/block id, both hashes, byte offset of first difference (offset only, no bytes) |
| fmt.refuse | E-FMT-* | Offending field name + observed value |
| res.limit.hit | E-RES-* | LIM-id, observed vs allowed |
| bench.result | Benchmark harness | Codec, split, total bytes, ratio vs each frozen baseline — numbers land ONLY here and in BENCHMARK_RESULTS.md |
| dict.reference | Dictionary load | Dict id + hash + tier gate outcome |

## Retention & size

Rotating cap (proposed default 10 MiB × 5 files, configurable) sized for the ~4 GiB target machine; structured logs are compressed with the *generic* compressor already in the stack (Zstd), never with an unverified LEXORA codec — logging must not depend on the thing under diagnosis.

## Non-goals

- Remote telemetry: LEXORA sends nothing anywhere. All logs stay local by design.
- Audit-grade tamper-evident logging: out of scope for v1 (no multi-party trust model yet).

## Status note

No logger exists; formats above are proposals pending Phase 1+ implementation and spec freeze.
