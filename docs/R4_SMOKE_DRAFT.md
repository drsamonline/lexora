# R4 smoke revision — LEXORA against the frozen baseline (DRAFT, not published)

> **Status:** DRAFT for owner review (Session 60, 2026-10-29). **Smoke scope, not protocol scope.** Nothing here may be published into [BENCHMARK_RESULTS.md](BENCHMARK_RESULTS.md) without owner sign-off per QUALITY_PLAN, and **no ADR-0001 verdict is implied** — the corpus is 593 MB against a ≥1 GiB requirement and the run used a 12.1 MiB subset with 2 reps.
> **Artifacts:** `benchmarks/results-r4-train.json`, `-validation.json`, `-heldout.json` — now at **revision 5** against the 1 GiB corpus (Session 66); the same three files held revision 4 against the 746 MB corpus, and `results-r4-smoke.json` is the original 12.1 MiB cut.
> **Related:** [BENCHMARK_PROTOCOL.md](BENCHMARK_PROTOCOL.md) · [BENCHMARK_RESULTS.md](BENCHMARK_RESULTS.md) · [COST_MODEL.md](COST_MODEL.md) · [ADR-0001](ADR/ADR-0001-gate-scope.md) · [ADR-0012](ADR/ADR-0012-default-encode-level.md) · [CORPUS_POLICY.md](CORPUS_POLICY.md)

## Why this exists

Until this revision, **LEXORA had never been measured against anything.** R1–R3 measured the *frozen baselines* against each other (zstd-19 vs xz-9) on a smoke corpus; the project's own pipeline appeared in no table. Every claim about the format was therefore about a design, not a result.

The harness now registers **`lexora`** (canonicalize → `.lxz` v0 at the shipped default level) and **`lexora19`** (the same at zstd level 19) as systems, so our numbers sit beside the baselines on identical files with identical cost accounting.

## What was measured

- **Corpus:** `gutenberg-cat-partial` (tier T1-gutenberg-p0), **heldout split only**, first **17 files / 12.1 MiB** by path order. Parent manifest `40acccbf…`, which verifies with 0 problems.
- **Subset selection is recorded in the artifact** (`subset.selector = {split: heldout, max_bytes: 12582912}`), so the run is reproducible without hand-built manifests.
- **Reps:** 2. **Machine:** 2 vCPU container, Linux/gVisor, zstandard 0.25.0, Python 3.12.13.
- **Systems:** `lexora` (default level 9, ADR-0012), `lexora19`, `zstd19`.

## R5 — repeated on the full ≥1 GiB corpus (Session 66)

The corpus reached 1.014 GiB in Session 65, so the run was repeated against it: **revision 5**, parent manifest `56d9443d…` (2344 files, verifies with 0 problems), **184 files / 80.4 MiB**, three splits, 3 reps.

| system | ratio (R5, 1 GiB corpus) | ratio (R4, 746 MB corpus) |
|---|---|---|
| `lexora` (default, L9) | 0.3360 | 0.3352 |
| `lexora19` | **0.3101** | 0.3090 |
| `zstd19` | 0.3120 | 0.3109 |
| `xz9-lzma` | **0.3077** | 0.3068 |

`lexora19` vs `zstd19`: **178 of 184 files smaller, −0.60 %**. Against `xz9-lzma`: **0 of 184, +0.77 %**.

**The conclusions did not move.** Same ordering, same effect sizes to within 0.03 percentage points, on a different file set drawn from a corpus 39 % larger. That reproducibility is the most useful thing these two revisions establish: the result is a property of the pipeline and the corpus class, not of one lucky sample. It is still a *small* effect and still smoke scope — see the five protocol-scope conditions at the end.

## Results — all three splits, 3 reps (Session 63, 746 MB corpus)

**172 files, 78.6 MiB, every split, 3 reps.** This supersedes the 12.1 MiB single-split cut below, which is kept because it was the first measurement and its numbers are unchanged.

| system | ratio (all splits) |
|---|---|
| `lexora` (shipped default, level 9) | 0.3352 |
| `lexora19` | **0.3090** |
| `zstd19` | 0.3109 |
| `xz9-lzma` | **0.3068** |

Per split, the ordering never changes:

| split | files / MiB | lexora | lexora19 | zstd19 | xz9-lzma |
|---|---|---|---|---|---|
| train | 63 / 30.1 | 0.3325 | 0.3077 | 0.3097 | 0.3056 |
| validation | 78 / 30.3 | 0.3409 | 0.3176 | 0.3194 | 0.3154 |
| heldout | 31 / 18.2 | — | — | — | — |

File-level: `lexora19` is smaller than `zstd19` on **167 of 172 files** (−0.60 % aggregate) and smaller than `xz9-lzma` on **0 of 172** (+0.74 %). The sign is consistent across all three splits and 3 reps — stronger than the single-split cut, still a **small** effect.

## Results — the first cut (12.1 MiB, heldout only, 2 reps)

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

**It does not say** that LEXORA beats zstd-19 by a *useful* margin. The three-split run (172 files, 3 reps) reproduces the sign consistently — 167 of 172 files, −0.60 % aggregate, same direction in train, validation and heldout — so this is stronger than the first cut, but **0.6 % is still a small effect**: it is larger than the run-to-run variation we can see (reps agree to the byte on stored size) and smaller than what a different corpus, a different zstd version, or the container's 168-byte overhead on many tiny files could shift. The defensible statement is **"a small, consistent advantage over zstd-19, and a small, consistent deficit against xz-9"** — not "beats the baseline".

**It does not measure the shipped default's trade-off as a win either:** the default is 8.5 % larger than zstd-19 (0.3352 vs 0.3109) in exchange for ~9× the speed (ADR-0012's operating point). That is a deliberate choice, not a compression result.

**A note on the xz row.** This sandbox has no `xz` binary, so the row was produced by `xz9-lzma`: stdlib `lzma` at `FORMAT_XZ, preset=9` — the same format and preset through liblzma rather than the CLI. Size numbers are directly comparable; the timing is not quite, because a CPython call is not a subprocess. The artifact records which implementation ran.

**Peak RSS is absent from this run** — this container exposes no `VmHWM`, so the forked sampling returns nothing and the artifact records the reason instead of inventing a number. Memory results live in `benchmarks/results-rss-core.json`, measured by a different probe (`benchmarks/rss_probe.py`).

## What protocol scope would require

1. ~~Corpus ≥ 1 GiB (OQ-8)~~ — **met**: 2395 files / 1.054 GiB, manifest `c92cf578…`, 0 problems, no lineage straddling. This condition no longer blocks anything.
2. **All three splits**, not heldout alone, with the leak audit re-run (currently 852/116/239, no lineage straddling).
3. **3 reps** per BENCHMARK_PROTOCOL §6.3, and a second machine class for the reference profile (REF-4G, OQ-7).
4. **`xz9` via the CLI** (this run used `xz9-lzma` because no `xz` binary exists here), on a machine where both are available so the timing rows are comparable.
5. **Owner sign-off** before anything enters `BENCHMARK_RESULTS.md`.

## Reproduce

```bash
python3 benchmarks/harness.py manifest --root <corpus> --out /tmp/manifest.json
for split in train validation heldout; do
  python3 benchmarks/harness.py run --manifest /tmp/manifest.json \
      --out benchmarks/results-r4-$split.json \
      --systems lexora,lexora19,zstd19,xz9-lzma --reps 3 \
      --split $split --max-bytes 31457280 --revision 4
done
```

The `--split` / `--max-bytes` selectors verify the **full** manifest hash before subsetting, and record the selector in the artifact, so a subset run never weakens provenance — it states exactly how it was cut.
