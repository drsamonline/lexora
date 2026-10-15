# LEXORA Benchmark Results

> **Status:** Active register (append-only per revision)
> **Owner:** Documentation architect (delegated)
> **Last verified:** 2026-10-15
> **Related:** [BENCHMARK_PROTOCOL.md](BENCHMARK_PROTOCOL.md) · [CORPUS_POLICY.md](CORPUS_POLICY.md) · [ADR-0001](ADR/ADR-0001-gate-scope.md)

## Purpose & scope

The single place where measured compression/cleaning/performance results are published. Only reproducible runs (committed harness + frozen manifest hash + env capture) may add numbers here. Methodology is defined in [BENCHMARK_PROTOCOL.md](BENCHMARK_PROTOCOL.md); this file contains results and their evidence pointers only.

## Current state

**No validated benchmark results yet.**

- No corpus assembled (OQ-8 open; see CORPUS_POLICY "Current status").
- No encoder/harness implemented (Phase P1/P2 not started).
- Consequently: no verdicts, no ratios, no timing or RSS figures exist. Any such number appearing anywhere in this repository before a recorded run would be fabricated and must be treated as a defect (QUALITY_PLAN S2).

## Register format (for future revisions — template, contains no data)

```text
### Revision R<n> — <date> — commit <hash>
- Manifest hash: ...
- Environment: env.json link/path, CPU/RAM/OS, Python, library versions
- Corpus: total canonical bytes, language/category mix
- Results table: system | held-out total bytes | vs best baseline % | verdict (Pass/Partial/Fail per ADR-0001)
- Per-category promotion table (validation → held-out reproduction)
- Timing & peak-RSS table vs PERFORMANCE_BUDGET
- Cleaning-quality pointer (ADR-0004 report path), if same-revision run
- Anomalies / failed runs: listed honestly
```

## Planned measurements once tooling exists

| Measurement | Phase | Blocking prerequisites |
|---|---|---|
| Core Zstd vs frozen baselines, corpus verdict | P2 | OQ-7, OQ-8, P1 exit |
| Candidate ablation tables (dictionary, Re-Pair, PPM, record coding, template+residual) | P4 | P2 harness; ADR-0001 gates |
| Peak-RSS compliance on REF-4G | P1 exit onward | P1 code; machine confirmation |
| Cleaning error rate (ADR-0004 protocol) | P3 | OCR fixtures + sample review |

## Historical entries

*None.* This section receives one dated block per completed revision; entries are never edited retroactively except via an appended correction note (master-prompt §4.6 discipline).
