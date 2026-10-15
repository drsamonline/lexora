# Runbook: Performance Triage

> **Status:** Draft (procedure for the designed system; no measurable artifacts exist yet — verified 2026-10-15)
> **Owner:** Documentation architect (delegated)
> **Related:** [../PERFORMANCE_BUDGET.md](../PERFORMANCE_BUDGET.md) · [../RESOURCE_LIMITS.md](../RESOURCE_LIMITS.md) · [../COST_MODEL.md](../COST_MODEL.md) · [../COMPRESSION_ARCHITECTURE.md](../COMPRESSION_ARCHITECTURE.md) · [BENCHMARK_RUNBOOK.md](BENCHMARK_RUNBOOK.md)

## When to use

Any of: encode/decode exceeds wall-time or peak-RSS budget, OOM on the ~4 GiB reference profile, compression ratio unexpectedly worse than last known-good run, or throughput collapse on a specific corpus category (e.g., Devanagari-heavy documents).

## First five minutes

1. Capture the run manifest (versions, pins, corpus hash, machine profile) — without it, comparison is guesswork.
2. Identify *which stage* regressed by reading INFO-level stage timings: ingest / canonicalize / codec-selection / block-compress / verify-write.
3. Compare against the last known-good run with identical corpus + pins. If either differs, that's the answer before any tuning: **data drift or version drift**, not code slowness.

## Memory (RSS) issues

| Check | Action |
|---|---|
| Peak RSS vs [../PERFORMANCE_BUDGET.md](../PERFORMANCE_BUDGET.md) envelope | Note overshoot factor; >1.5× ⇒ treat as design bug, file with repro corpus subset |
| Block sizes near LIM-01/LIM-02 | Encoder must respect ceilings; if decoder allocates beyond declared block size ⇒ implementation bug (validate-before-allocate violated, REQ-SEC-001) |
| Dictionary load dominates | LIM-05 ceiling check; consider smaller trained dict (record cost/ratio tradeoff honestly) |
| Grammar/side-table growth (Re-Pair etc.) | LIM-06 rules; streaming parse required, not whole-file DOM |
| Candidate selection holding all candidates' outputs in RAM | Selection MUST stream/measure incrementally ([../COST_MODEL.md](../COST_MODEL.md)); flag violation |

## CPU / wall-time issues

1. **Ablate codecs**: force Core Zstd baseline only; if fast again, the candidate (dictionary search, PPM order, Re-Pair parse) is the hotspot — profile within its declared budget only.
2. **Check pathological inputs**: highly repetitive data can explode grammar construction; random/incompressible data should fall through quickly (per COMPRESSION_ARCHITECTure fallback rules). Time both micro-corpora from golden vectors.
3. **Verify per-candidate budgets** are actually enforced (TM-12): unbounded parameter sweeps masquerading as "selection" are a design violation.
4. **Thermal/background noise**: cross-check with [BENCHMARK_RUNBOOK.md](BENCHMARK_RUNBOOK.md) repeat protocol before believing a 5% delta.

## Ratio regressions

- Same corpus + same pins + different ratio ⇒ encoder nondeterminism = **integrity-adjacent bug**; stop and triage under [CORRUPTION_TRIAGE.md](CORRUPTION_TRIAGE.md) instead.
- Different corpus mix ⇒ expected; report per-category numbers, never blended-only claims.
- Dictionary staleness (trained on older split) ⇒ retrain per protocol and record both results.

## Closing

Record: symptom, stage attribution, root cause (confirmed/suspected), fix or issue link, and post-fix measurement. Update [../BENCHMARK_RESULTS.md](../BENCHMARK_RESULTS.md) only via full protocol runs — triage measurements are diagnostic, not publishable headline numbers.
