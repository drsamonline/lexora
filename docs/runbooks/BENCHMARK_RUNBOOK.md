# Runbook: Benchmark Execution

> **Status:** Draft (procedure frozen in *form* only; cannot be executed until Phase 1 harness + corpus exist — verified 2026-10-15)
> **Owner:** Documentation architect (delegated)
> **Related:** [../BENCHMARK_PROTOCOL.md](../BENCHMARK_PROTOCOL.md) (normative) · [../CORPUS_POLICY.md](../CORPUS_POLICY.md) · [../COST_MODEL.md](../COST_MODEL.md) · [../PERFORMANCE_BUDGET.md](../PERFORMANCE_BUDGET.md) · [../BENCHMARK_RESULTS.md](../BENCHMARK_RESULTS.md)

**Rule zero:** this runbook *executes* the protocol; it never overrides it. If reality and [BENCHMARK_PROTOCOL.md](../BENCHMARK_PROTOCOL.md) disagree, stop, fix whichever is wrong via a documented change, then rerun. No number enters [BENCHMARK_RESULTS.md](../BENCHMARK_RESULTS.md) except from a completed checklist below.

## Preconditions checklist

- [ ] Protocol version pinned (note its commit hash in the run manifest).
- [ ] Corpus assembled per [CORPUS_POLICY.md](../CORPUS_POLICY.md): rights cleared, privacy tier set (OQ-8 answered), train/validation/held-out splits frozen with recorded hashes.
- [ ] Baselines pinned: Zstandard level 19 (primary), Brotli q11, XZ, PPMd — measurement-only roles per ADR-0002/0003; exact library versions recorded.
- [ ] Candidate codec(s) under test identified by registry ID + version.
- [ ] Machine profile matches [PERFORMANCE_BUDGET.md](../PERFORMANCE_BUDGET.md) reference definition (~4 GiB RAM envelope); background load minimized; thermal state noted.
- [ ] Fresh output directory; no results reused from earlier partial runs.

## Procedure

1. **Snapshot environment.** Record OS, CPU model, RAM, interpreter version, dependency lockfile hash → run manifest ([LOGGING_AND_DIAGNOSTICS.md](../LOGGING_AND_DIAGNOSTICS.md) format).
2. **Verify corpus integrity.** Recompute manifest hashes; any mismatch ⇒ abort (this is data drift, not a benchmark result).
3. **Run baselines first**, whole-split, each repeated N times per protocol; capture total stored bytes and wall time + peak RSS per run.
4. **Run candidate(s)** with identical inputs; include every serialized byte in cost accounting (dictionary, grammar/side tables, header, index — REQ-CMP-004). A candidate that needs an artifact to decode MUST count that artifact's bytes.
5. **Round-trip gate.** For every candidate run: `decode(encode(C)) == C` on all documents. Any failure invalidates the run entirely — record as failure, not as a size.
6. **Compute deltas** vs best baseline per category and overall; apply ADR-0001 gates: Pass ≥ 10% (validation AND reproduced on held-out), Partial ≥ 3%, Fail < 3%.
7. **Ablation section** (for regressions or "worse than expected"): re-run disabling one component at a time (dictionary off, candidate codec off, block size variant) to attribute the delta. Record which knob moved which percentage.
8. **Publish honestly.** Append dated table to [BENCHMARK_RESULTS.md](../BENCHMARK_RESULTS.md): protocol hash, corpus hash, pins, per-split numbers, spread across repeats, anomalies. Mark clearly which split each number came from.

## Post-run checklist

- [ ] Run manifest + raw logs archived with hashes.
- [ ] BENCHMARK_RESULTS.md entry added; no claims stronger than the numbers.
- [ ] Deviations/anomalies logged even if unexplained ("observed but not attributed" is a valid entry).
- [ ] Session outcome recorded in [../SESSION_LOG.md](../SESSION_LOG.md).

## Common failure modes

| Symptom | First checks |
|---|---|
| Results vary > noise threshold between repeats | Thermal throttling, background jobs, unpinned allocator/threading env vars |
| Candidate wins on train, loses on held-out | Dictionary overfit — expected behavior of gate; report both numbers |
| OOM during a run | Block/dictionary sizes vs [../RESOURCE_LIMITS.md](../RESOURCE_LIMITS.md); escalate to [PERFORMANCE_TRIAGE.md](PERFORMANCE_TRIAGE.md) |
| Baseline beats itself from last month | Library version drift — repin and note protocol amendment |
