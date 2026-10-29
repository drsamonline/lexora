# R4 smoke revision — LEXORA against the frozen baseline (DRAFT, not published)

> **Status:** DRAFT for owner review (Session 60, 2026-10-29). **Smoke scope, not protocol scope.** Nothing here may be published into [BENCHMARK_RESULTS.md](BENCHMARK_RESULTS.md) without owner sign-off per QUALITY_PLAN, and **no ADR-0001 verdict is implied** — the corpus is 593 MB against a ≥1 GiB requirement and the run used a 12.1 MiB subset with 2 reps.
> **Artifact:** `benchmarks/results-r4-smoke.json` (regenerate with the command at the end).
> **Related:** [BENCHMARK_PROTOCOL.md](BENCHMARK_PROTOCOL.md) · [BENCHMARK_RESULTS.md](BENCHMARK_RESULTS.md) · [COST_MODEL.md](COST_MODEL.md) · [ADR-0001](ADR/ADR-0001-gate-scope.md) · [ADR-0012](ADR/ADR-0012-default-encode-level.md) · [CORPUS_POLICY.md](CORPUS_POLICY.md)

## Why this exists

Until this revision, **LEXORA had never been measured against anything.** R1–R3 measured the *frozen baselines* against each other (zstd-19 vs xz-9) on a smoke corpus; the project's own pipeline appeared in no table. Every claim about the format was therefore about a design, not a result.

The harness now registers **`lexora`** (canonicalize → `.lxz` v0 at the shipped default level) and **`lexora19`** (the same at zstd level 19) as systems, so our numbers sit beside the baselines on identical files with identical cost accounting.

## What was measured

- **Corpus:** `gutenberg-cat-partial` (tier T1-gutenberg-p0), **heldout split only**, first **17 files / 12.1 MiB** by path order. Parent manifest `40acccbf…`, which verifies with 0 problems.
- **Subset selection is recorded in the artifact** (`subset.selector = {split: heldout, max_bytes: 12582912}`), so the run is reproducible without hand-built manifests.
- **Reps:** 2. **Machine:** 2 vCPU container, Linux/gVisor, zstandard 0.25.0, Python 3.12.13.
- **Systems:** `lexora` (default level 9, ADR-0012), `lexora19`, `zstd19`.

## Results

| system | stored bytes | ratio | encode MiB/s |
|---|---|---|---|
| `lexora` (shipped default, level 9) | 4,283,912 | 0.3367 | 12.55 |
| `lexora19` (level 19) | 3,921,177 | 0.3082 | 1.39 |
| `zstd19` (frozen baseline) | 3,946,333 | 0.3102 | 1.36 |
| `xz9-lzma` (frozen baseline) | 3,898,204 | **0.3064** | 1.06 |

Per-file comparison, `lexora19` vs `zstd19`:

Against `zstd19`:

- **16 of 17 files smaller with LEXORA.**
- Aggregate **−0.637 %**; median per-file **−0.505 %**; range −0.84 % to +0.10 %.

Against `xz9` (added Session 62, the harder baseline):

- **0 of 17 files smaller** — xz wins every file.
- Aggregate **+0.59 %** (LEXORA larger).

Shipped default vs both baselines: **+8.5 %** larger than zstd-19, **+9.9 %** larger than xz-9, at **~10× the speed**.

## What this does and does not say

**It does say** three things, and the third is the important one:

1. At equal zstd level, LEXORA is **not worse than zstd-19** despite paying container overhead (128 B header + 56 B per block + 40 B trailer per file). Canonicalization earns back slightly more than the container costs.
2. **LEXORA sits between the two frozen baselines**: marginally better than zstd-19 (−0.64 %), marginally worse than xz-9 (+0.59 %), and xz wins on every single file.
3. Therefore **no amount of zstd tuning will move LEXORA past xz** — the v0 pipeline is canonicalization plus zstd, and zstd at any level does not beat LZMA on this corpus. That is not a defect in the implementation; it is the ceiling of the design, and it is precisely why the roadmap's later phases add PPMd, Brotli and trained dictionaries rather than more zstd levels. The R4 numbers make the ADR-0001 gate meaningful instead of rhetorical.

**It does not say** that LEXORA beats zstd-19. A **0.6 % aggregate difference over 12.1 MiB with 2 reps cannot be separated from noise** on a shared 2-vCPU container, and one file got *worse*. Anyone reading this as a win would be over-reading it; the honest statement is **"indistinguishable at this scope, with a consistent sign across 16 of 17 files"** — suggestive, not established.

**It does not measure the shipped default's trade-off as a win either:** the default is 8.5 % larger than zstd-19 and 9.9 % larger than xz-9 in exchange for ~10× the speed (ADR-0012's operating point). That is a deliberate choice, not a compression result.

**A note on the xz row.** This sandbox has no `xz` binary, so the row was produced by `xz9-lzma`: stdlib `lzma` at `FORMAT_XZ, preset=9` — the same format and preset through liblzma rather than the CLI. Size numbers are directly comparable; the timing is not quite, because a CPython call is not a subprocess. The artifact records which implementation ran.

**Peak RSS is absent from this run** — this container exposes no `VmHWM`, so the forked sampling returns nothing and the artifact records the reason instead of inventing a number. Memory results live in `benchmarks/results-rss-core.json`, measured by a different probe (`benchmarks/rss_probe.py`).

## What protocol scope would require

1. **Corpus ≥ 1 GiB** (OQ-8). Current snapshot: 593.4 MB — ~431 MB short, ~20 fetch passes here or one unattended loop.
2. **All three splits**, not heldout alone, with the leak audit re-run (currently 852/116/239, no lineage straddling).
3. **3 reps** per BENCHMARK_PROTOCOL §6.3, and a second machine class for the reference profile (REF-4G, OQ-7).
4. **`xz9` via the CLI** (this run used `xz9-lzma` because no `xz` binary exists here), on a machine where both are available so the timing rows are comparable.
5. **Owner sign-off** before anything enters `BENCHMARK_RESULTS.md`.

## Reproduce

```bash
python3 benchmarks/harness.py manifest --root <corpus> --out /tmp/manifest.json
python3 benchmarks/harness.py run --manifest /tmp/manifest.json \
    --out benchmarks/results-r4-smoke.json \
    --systems lexora,lexora19,zstd19 --reps 2 \
    --split heldout --max-bytes 12582912 --revision 4
```

The `--split` / `--max-bytes` selectors verify the **full** manifest hash before subsetting, and record the selector in the artifact, so a subset run never weakens provenance — it states exactly how it was cut.
