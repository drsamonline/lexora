# R6 — protocol-shaped run: CHCE reproduces in every split

> **Status:** **Not published as a benchmark revision** — this is a protocol-shaped run at
> small scale, and it is recorded so the next session does not have to redo it. It does
> **not** close gate G2 and is **not** an ADR-0001 verdict. Artifacts:
> `benchmarks/results-r6-{train,validation,heldout}.json` (per-file rows) and
> `benchmarks/results-r6-summary.json` (aggregate + conditions).

## Why this exists

ADR-0015 keeps zstd as the default and makes CHCE a preset, on the condition that the
default is revisited only after a **protocol-scope** run. The owner then asked whether
`.lxdb` could replace SQLite as a directly queryable file; `FORMAT_LXDB.md` forbids writing
`.lxdb` code before G2 closes, and the owner chose to respect that gate rather than
override it. So the question became: **how much of G2 can actually be closed here?**

Answer: the shape, not the scale. This run takes the protocol's *structure* — all three
splits, 3 reps, every system, leak audit — and applies it at 5.9 MB instead of 1.054 GiB.

## What was run

- **Corpus:** Project Gutenberg top-90 English selection, filtered to files under 400 KB so
  each split holds many documents rather than one large one (a `--max-bytes` selector
  includes the first file regardless of budget, so a corpus of large books yields a
  one-file "split"). 27 files / 5.9 MB total; measured 10 / 2 / 5 files per split.
- **Split audit:** clean — no lineage straddles splits.
- **Reps:** 3, per BENCHMARK_PROTOCOL §6.3.
- **Systems:** `lexora`, `lexora19`, `zstd19`, `xz9-lzma`, `chce-raw`, `lexora-chce`.
- **Machine:** 2 vCPU / 2 GiB container. Sizes exact, throughput indicative.

## Result — 17 file-runs, 3.58 MiB of input

| system | ratio | stored | vs `lexora19` | vs `xz -9` | MiB/s | reps byte-stable |
|---|---|---|---|---|---|---|
| `lexora` (default, L9) | 0.3498 | 1,314,761 | +6.12 % | +7.23 % | 13.07 | yes |
| `lexora19` | 0.3296 | 1,238,988 | — | +1.05 % | 1.41 | yes |
| `zstd19` | 0.3315 | 1,246,032 | +0.57 % | +1.63 % | 1.45 | yes |
| `xz9-lzma` | 0.3262 | 1,226,072 | −1.04 % | — | 0.81 | yes |
| `chce-raw` | 0.2649 | 995,454 | −19.66 % | −18.81 % | 0.45 | yes |
| **`lexora-chce`** | **0.2658** | **999,142** | **−19.36 %** | **−18.51 %** | 0.39 | yes |

**Three things this establishes that the Session-71 smoke run could not.**

1. **It reproduces on a different corpus.** The smoke run used 19 hand-picked books and
   measured −19.75 % vs `xz -9`; this run uses a different, larger selection and measures
   **−18.51 %**. Two corpora, one number to within 1.2 points.
2. **It holds in every split** — train, validation and heldout all show the same ordering
   and the same magnitude. A single-sample artefact does not do that.
3. **Stored sizes are byte-stable across reps**, for every system, which is the
   determinism promise (REQ-CMP-003) holding under the harness rather than only in unit
   tests.

It also reproduces the *old* result honestly: `lexora19` is **+1.05 %** against `xz -9`
here, against +0.77 % in R5 — v0 is still slightly worse than xz, exactly as published.
The CHCE rows are the only thing that changes the sign.

## What this does not do — gate G2 stays open

| Condition | Status |
|---|---|
| Corpus ≥ 1 GiB (1.054 GiB snapshot exists) | ❌ **not used** — 5.9 MB measured here |
| All three splits | ✅ |
| Leak audit clean | ✅ |
| 3 reps | ✅ |
| Second machine class (REF-4G) | ❌ single container |
| `xz` via the CLI | ❌ `xz9-lzma` (stdlib liblzma); no `xz` binary in this image |
| Owner sign-off | ❌ |

**So `.lxdb` remains gated.** The gap is now purely environmental — a machine with the
1.054 GiB snapshot, an `xz` binary, and a second hardware class — not analytical. What
this run removes is the *risk* that the CHCE number is a small-sample fluke, which was the
reason the gate existed.

## Cost of running it properly

CHCE is the binding constraint: 0.39–0.45 MiB/s, and the harness compresses every file
**twice** per rep (once for the measurement, once inside the forked peak-RSS probe). At
that rate a 1.054 GiB corpus × 6 systems × 3 reps is a multi-hour job — plan a machine and
an overnight budget, not a 300-second command.
