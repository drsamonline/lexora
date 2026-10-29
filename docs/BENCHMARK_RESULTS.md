# LEXORA Benchmark Results

> **Status:** Active register (append-only per revision)
> **Owner:** Documentation architect (delegated)
> **Last verified:** 2026-10-16 (Revision R2 published — manifest regeneration closing R1's correction note; corpus tier T1-gutenberg-p0 unchanged)
> **Related:** [BENCHMARK_PROTOCOL.md](BENCHMARK_PROTOCOL.md) · [CORPUS_POLICY.md](CORPUS_POLICY.md) · [ADR-0001](ADR/ADR-0001-gate-scope.md)

## Purpose & scope

The single place where measured compression/cleaning/performance results are published. Only reproducible runs (committed harness + frozen manifest hash + env capture) may add numbers here. Methodology is defined in [BENCHMARK_PROTOCOL.md](BENCHMARK_PROTOCOL.md); this file contains results and their evidence pointers only.

## R4 smoke — LEXORA measured against the baseline for the first time

**DRAFT, not published** — see [R4_SMOKE_DRAFT.md](R4_SMOKE_DRAFT.md) for the write-up and `benchmarks/results-r4-smoke.json` for the artifact. Until R4, LEXORA itself appeared in no results table: R1–R3 measured the frozen baselines against each other. At equal zstd level on 12.1 MiB of heldout corpus, LEXORA **0.3082** sits **between the two frozen baselines**: marginally better than zstd-19 (**0.3102**, −0.64 %, 16 of 17 files) and marginally worse than xz-9 (**0.3064**, +0.59 %, xz wins every file). **Indistinguishable at smoke scope and suggestive rather than established** — explicitly not an ADR-0001 verdict. The shipped default (level 9) is 0.3367, i.e. 8.5 % larger than zstd-19 at ~10× the speed. The practical reading: v0 is canonicalization + zstd, so it cannot pass xz by tuning zstd — which is what the roadmap's PPMd/Brotli/dictionary phases exist for.

## Current state

**One smoke-baseline revision published (R1, 2026-10-16).** It is explicitly **not** an ADR-0001 Pass/Partial/Fail verdict run: the corpus is a Tier-1 fallback snapshot (~7.1 MB, English books only), far below the ≥1 GiB multi-language target in [CORPUS_POLICY.md](CORPUS_POLICY.md). Every number below carries the mandatory tier label **T1-gutenberg-p0**. The pre-R1 statement stands for anything beyond this scope: no validated full-corpus benchmark results exist.

- Corpus: none supplied by owner (`data/raw/` empty) → deterministic fallback fetched public-domain (P0) Project Gutenberg texts; provenance sidecars recorded (`corpus/gutenberg-r0.*.json`).
- Harness: committed (`benchmarks/harness.py`, manifest v2 + `benchmarks/corpus.py`); round-trip verified per BENCHMARK_PROTOCOL §3 mechanics.
- Verdicts per ADR-0001: **not issued** — prerequisites (≥1 GiB corpus, hi/gu coverage, OQ-8 closure) unmet.

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

One dated block per completed revision; entries are never edited retroactively except via an appended correction note (master-prompt §4.6 discipline).

### Revision R1 — 2026-10-16 — commit `908698c` (harness v2 + tiered corpus)

**Corpus tier: T1-gutenberg-p0** (mandatory label for every number below). Smoke baseline only — **no ADR-0001 verdict issued** (scope ≪ protocol target; see Current state).

- Manifest hash: `7d65d09da38640bae9d985d5aa245f8e566200a9976a2a5852f0e47f30d0ceae` (`benchmarks/MANIFEST.json`, v2; content-hash over canonical JSON, re-verified at publication time).
- Environment (`benchmarks/env.json`): Linux x86_64, Intel Xeon @ 2.50 GHz, ~2.05 GiB RAM, Python 3.12.10, zstandard 0.25.0, xz (XZ Utils) 5.4.1; CLI `zstd`/`brotli`/`7z` absent → those baselines could not run; the recorded artifact ran the two available systems (zstd19 via bindings, xz9 via subprocess).
- Corpus: 6 files, 7,124,095 B total raw UTF-8 text (baseline-system measurements on raw bytes; full-pipeline canonicalization of the corpus is pending), English prose/books, rights P0 (public domain), split by lineage: 5 train (4,336,971 B) / 1 heldout (2,787,124 B, PG#1184). Reps = 3; stored-size figures are min-over-reps (deterministic codecs: min = median = max in all rows).
- Results table (aggregate, tier **T1-gutenberg-p0**):

| System | Input B | Stored B (min reps) | Ratio | Held-out ratio | Median encode s (largest file) |
|---|---|---|---|---|---|
| Zstd level 19 | 7,124,095 | 2,139,962 | 0.3004 | 0.2809 | 1.487 |
| XZ level 9 | 7,124,095 | 2,119,756 | 0.2975 | 0.2786 | 1.858 |

  Relative: XZ-9 stores ≈0.9% fewer bytes than Zstd-19 overall (≈0.8% on held-out) while encoding ≈25% slower on the largest file. These are baseline-vs-baseline observations; the LEXORA candidate codec does not exist yet, so no Pass/Partial/Fail row can be filled.

- Per-file detail (stored bytes, ratio; tier T1-gutenberg-p0):

| File | Split | Input B | Zstd-19 | XZ-9 |
|---|---|---|---|---|
| gutenberg-1184.txt | heldout | 2,787,124 | 782,892 (0.2809) | 776,472 (0.2786) |
| gutenberg-1342.txt | train | 772,386 | 226,028 (0.2926) | 223,512 (0.2894) |
| gutenberg-1400.txt | train | 1,058,204 | 324,526 (0.3067) | 321,664 (0.3040) |
| gutenberg-1661.txt | train | 607,606 | 191,034 (0.3144) | 188,860 (0.3108) |
| gutenberg-2701.txt | train | 1,276,315 | 422,220 (0.3308) | 418,184 (0.3276) |
| gutenberg-76.txt | train | 622,460 | 193,262 (0.3105) | 191,064 (0.3069) |

- Per-category promotion table: N/A — single category (prose/books), single language (en); validation→held-out reproduction across categories requires a compliant corpus.
- Timing & peak-RSS vs PERFORMANCE_BUDGET: RSS **not measured** in this harness revision (recorded honestly as absent); timings above are wall-clock seconds on the environment described.
- Cleaning-quality pointer (ADR-0004): N/A — no OCR fixtures yet.
- Anomalies / failed runs (recorded honestly):
  - 2 of 8 requested Gutenberg titles discarded by the fetch guard (< 0.5 MB payload after boilerplate strip): PG#84 (448,885 B), PG#74 (434,357 B). See `corpus/gutenberg-r0.sources.json`.
  - Held-out is a single lineage (1-of-6 files approximates the 20% target due to tiny corpus); statistical strength is nil — treat ratios as smoke-test values only.
  - Correction note (append-only discipline): the committed manifest's per-file `rights`/`language`/`category` fields read UNCLASSIFIED/unknown/unclassified because it was generated before the meta sidecars were applied. The authoritative classification for this snapshot is `corpus/gutenberg-r0.meta.json` (en / prose-books / P0-public-domain). Manifest will be regenerated with metadata folded in for R2.
- Evidence pointers: `benchmarks/results-r0.json` (artifact, benchmark_revision 1), `benchmarks/MANIFEST.json`, `benchmarks/env.json`, `corpus/gutenberg-r0.*.json` (provenance sidecars; raw texts gitignored).

### Revision R2 — 2026-10-16 — manifest regeneration (metadata folded in); no new measurements

**Corpus tier: T1-gutenberg-p0** (unchanged snapshot bytes — same 6 files, same per-file SHA-256s). This revision **closes the R1 correction note**; it re-publishes the identical measured numbers under a corrected manifest. No new runs were performed and **no ADR-0001 verdict is issued** (scope argument from R1 stands unchanged).

- Manifest hash: `a32240d792c06953465ef71dd9dc30a2033aea976ab23291c326b32014161a5f` (`benchmarks/MANIFEST.json`, v2; content-hash over canonical JSON; `verify` → 6 files, 0 problems; `audit-splits` → train 5 / validation 0 / heldout 1, no lineage straddles splits). Supersedes R1's `7d65d09da386…`.
- What changed vs R1: per-file `rights` = P0, `language` = en, `category` = prose/books are now folded in from the provenance sidecars at manifest-generation time (R1 shipped them as UNCLASSIFIED/unknown/unclassified because the meta sidecar lookup pointed at the wrong path). Harness fix: sidecar resolution now reads `<root>.meta.json` locally, falling back to the **committed** copy `benchmarks/provenance/gutenberg-r0/meta.json`.
- Provenance evidence chain is now committed (new subcommand `corpus-commit`; small JSON files only — raw texts remain gitignored): `benchmarks/provenance/gutenberg-r0/{lineage.json, meta.json, sources.json}`. R1's "authoritative classification" pointer (`corpus/gutenberg-r0.meta.json`) referred to gitignored state; that gap is closed.
- Measured results: **identical to R1** (codec inputs are the corpus file bytes, which are byte-for-byte unchanged; the manifest metadata fields do not enter the measurement path). Aggregate: Zstd-19 stored 2,139,962 B, ratio 0.3004; XZ-9 stored 2,119,756 B, ratio 0.2975 on 7,124,095 B input; held-out (PG#1184) ratios 0.2809 / 0.2786. Per-file table: see R1 block above (values apply verbatim).
- Anomalies carried forward honestly: 2-of-8 fetch discards (PG#84/#74 size guard); single-lineage held-out; RSS not measured; scope ≪ ≥1 GiB protocol target — smoke values only.
- Evidence pointers: `benchmarks/MANIFEST.json` (regenerated), `benchmarks/provenance/gutenberg-r0/*` (committed), `benchmarks/results-r0.json` (measurement artifact, benchmark_revision 1 — rerunning with `--revision 2` would produce an identical-numbers artifact under the new manifest hash; deferred until R3 expands the corpus so each published run carries information).
