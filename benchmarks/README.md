# Reproducing the benchmarks

Everything here is deterministic given the corpus and the machine. The rule that
governs this directory: **no number appears in a document without an artifact that
produced it**, and no artifact is committed without the manifest digest it was
measured against. If a measurement cannot be reproduced, it is not reported.

```text
benchmarks/
  harness.py                  the only tool that produces measurement artifacts
  corpus.py                   corpus fetch (curated ids, or PG catalog selection)
  rss_probe.py                peak-RSS + throughput probe (separate method, separate artifact)
  provenance/                 committed sidecars: what the corpus contains, and its rights
  results-r0.json             R0 — smoke baseline (baselines only)
  results-r3.json             R3 — smoke baseline (baselines only)
  results-rss-core.json       peak RSS + throughput, encode/decode/canon, stream vs buffered
  results-level-sweep.json    encode level → speed/size/RAM curve on real prose
  results-r4-{train,validation,heldout}.json   R4 — LEXORA vs baselines, three splits
  results-r4-smoke.json       R4 first cut (12.1 MiB, single split, 2 reps) — kept for history
```

## 0. Environment capture (do this first, always)

```bash
python3 benchmarks/harness.py env          # writes benchmarks/env.json
```

An artifact whose environment is unknown is not evidence. `env.json` records the
interpreter, codec library, CPU count and OS — the things that make a timing number
comparable or not.

## 1. Corpus

**Curated ids** (small, fast, what the early revisions used):

```bash
python3 benchmarks/harness.py corpus-fetch --languages en --min-mb 0.5 --dest corpus/gutenberg-r0
```

**Catalog selection** (what the ≥1 GiB target needs). Selection is *deterministic*:
filter the official catalog to `Type=Text` + `Language=en`, order by PG id ascending,
take `--catalog-limit`. The catalog's SHA-256 is recorded in the snapshot, so the same
digest and filter reproduce the same id list.

```bash
python3 benchmarks/harness.py corpus-fetch \
    --catalog-limit 2500 --min-mb 0.05 \
    --dest corpus/gutenberg-cat --catalog-cache corpus/_catalog
```

**It resumes, and it is safe to interrupt.** Existing files whose SHA-256 matches the
record are not re-downloaded; provenance is checkpointed every 25 files and is always
a *superset* of what was already recorded. Re-running the same command adds to the
same snapshot — that is how the current 746 MB snapshot was built, pass by pass.

If a run was killed and the record looks short:

```bash
python3 benchmarks/harness.py corpus-reconcile --root corpus/gutenberg-cat
```

It hashes the texts on disk and rebuilds the record. Files whose id is outside the
requested set are counted as `orphaned` and deliberately **not** claimed.

Corpus texts are gitignored; only the provenance sidecars are committed:

```bash
python3 benchmarks/harness.py corpus-commit --root corpus/gutenberg-cat
```

## 2. Manifest, verify, split audit

```bash
python3 benchmarks/harness.py manifest     --root corpus/gutenberg-cat --out /tmp/manifest.json
python3 benchmarks/harness.py verify       --manifest /tmp/manifest.json
python3 benchmarks/harness.py audit-splits --manifest /tmp/manifest.json
```

`manifest` hashes every file and writes `manifest_sha256`; `verify` re-hashes and
reports problems; `audit-splits` fails if a **lineage** straddles splits, because a
work appearing in both train and heldout stops the benchmark measuring generalisation.
All three must be clean before any run is worth doing.

## 3. The measurement run

```bash
python3 benchmarks/harness.py run \
    --manifest /tmp/manifest.json \
    --out benchmarks/results-r4-heldout.json \
    --systems lexora,lexora19,zstd19,xz9-lzma \
    --reps 3 --split heldout --max-bytes 31457280 --revision 4
```

**Systems** (`SYSTEMS` in `harness.py`):

| name | what it is |
|---|---|
| `lexora` | the shipped pipeline: canonicalize → `.lxz` v0 at `DEFAULT_LEVEL` (ADR-0012) |
| `lexora19` | the same at zstd level 19 — the *size-comparable* row, since comparing a level-9 default with a level-19 baseline measures the level, not the pipeline |
| `zstd19` | frozen baseline, in-process `python-zstandard` |
| `xz9` | frozen baseline via the `xz` CLI (skipped when absent) |
| `xz9-lzma` | frozen baseline via stdlib `lzma`, `FORMAT_XZ`, preset 9 — same format and preset, different implementation; sizes comparable, timings not quite |

`--split` and `--max-bytes` cut a **subset** of a *verified* manifest and record the
selector in the artifact, so a smoke run states exactly how it was bounded. The full
manifest hash is checked before subsetting, so a subset never weakens provenance.

Every run asserts **cost accounting** (REQ-CMP-004): reported stored bytes must equal
the file on disk, byte for byte. A system that miscounts aborts the run instead of
producing a number.

## 4. Memory and throughput (separate probe, separate method)

`harness.py run` measures size and time. It does **not** produce trustworthy memory
numbers on every host, so peak RSS and throughput live in their own artifact:

```bash
python3 benchmarks/rss_probe.py --sizes 1,4,16,32,64 --reps 1 --append        # peak RSS
python3 benchmarks/rss_probe.py --canon-only --sizes 16,64 --reps 2 --append  # canonicalizer
python3 benchmarks/rss_probe.py --level-sweep --levels 1,3,6,9,12,15,19 \
        --sweep-input /path/to/real-prose.txt --overwrite                     # level curve
```

Notes that cost someone an afternoon each:

- The probe **refuses to overwrite** an existing artifact without `--append` or
  `--overwrite`. Trust that refusal.
- Peak RSS comes from `ru_maxrss` via `os.wait4`, not from sampling `/proc` — this
  container exposes no `VmHWM`, so the harness's sampling method returns nothing here.
- Use **real prose**, not synthetic or highly repetitive text. Repeating byte patterns
  compress in under a second at level 19 and flatter every number you take.

## 5. Reading an artifact

```bash
python3 - <<'PY'
import json
d = json.load(open("benchmarks/results-r4-heldout.json"))
rows = d["rows"]; inp = sum(r["input_bytes"] for r in rows if r["system"] == "lexora")
for s in d["systems_run"]:
    rs = [r for r in rows if r["system"] == s]
    stored = sum(r["stored_bytes_median"] for r in rs)
    t = sum(r["encode_s_median"] for r in rs)
    print(f"{s:11} ratio {stored/inp:.4f}  {inp/2**20/t:6.2f} MiB/s")
PY
```

Each row carries `input_bytes`, per-rep `stored_bytes_*` and `encode_s_*` (min/median/
max), the split and the path — enough to recompute any aggregate and to disagree with
one.

## 6. What the current numbers are, and what they are not

R4 across three splits, 172 files / 78.6 MiB, 3 reps: `lexora19` **0.3090** vs
`zstd19` **0.3109** and `xz9-lzma` **0.3068** — LEXORA between the two baselines, a
small consistent advantage over zstd and a small consistent deficit against xz. See
[docs/R4_SMOKE_DRAFT.md](../docs/R4_SMOKE_DRAFT.md).

**That is smoke scope, not a verdict.** Protocol scope requires a corpus ≥1 GiB, all
three splits at full size, 3 reps, `xz9` via the CLI, a second machine class and owner
sign-off before anything enters [docs/BENCHMARK_RESULTS.md](../docs/BENCHMARK_RESULTS.md).
