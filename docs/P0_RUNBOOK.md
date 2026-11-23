# P0 runbook — the protocol-scope benchmark, in the order it has to happen

> **Status:** Ready to run. Written 2026-11-23 because P0 was a list of *conditions* with no
> commands: the work that blocks the headline claim, `.lxdb` and REQ-BMK-003 could only be
> assembled by reading three documents and guessing at the harness.
> **Owner:** Dr Sohil Momin — [PATH_TO_V1](PATH_TO_V1.md) P7.1 (run) and P7.2 (sign off)
> **Related:** [PATH_TO_V1](PATH_TO_V1.md) §3 P0 · [BENCHMARK_PROTOCOL](BENCHMARK_PROTOCOL.md) ·
> [R6_PROTOCOL_SHAPED_2026-11-07.md](R6_PROTOCOL_SHAPED_2026-11-07.md) · `benchmarks/README.md`

## What this produces, and why it is the only thing left

P0 turns R6 — protocol-*shaped* at 5.9 MB — into a published revision at protocol scope. It is the
one unmet release precondition, it is what `.lxdb` (ADR-0013) is gated on by owner decision, and it
is what REQ-BMK-003 asks for. Nothing else on the register needs a machine.

**Budget:** 6–8 hours wall clock, ~2 GB free disk. CHCE runs at 0.39–0.45 MiB/s and the harness
compresses every file twice per rep (measurement + forked RSS probe).

## 0. The binaries — the estate already has them

`xz`, `7z`, `brotli` and `ziptastic` are **not** in this container, and for a while that was recorded
as "absent from the environment". They are not absent from the estate:
[`drsamonline/heavenzip`](https://github.com/drsamonline/heavenzip) ships them under `bin/` —
`ziptastic-1.4.5-linux-x86_64`, `xz` 5.8.4, `7z` 26.05, `brotli` 1.2.0, `zstd` 1.5.4 — built by its
own CI. Clone it once and point everything at the directory:

```bash
git clone --depth 1 https://github.com/drsamonline/heavenzip ~/heavenzip
export LEXORA_ZIPTASTIC=~/heavenzip/bin/ziptastic-1.4.5-linux-x86_64
```

The preflight and the selector probe both take `--bin-dir ~/heavenzip/bin`. That is also how the
ziptastic real-binary test stops skipping, and how `brotli q11` and `ppmd-7z` became measurable at
all — the first numbers either has ever had in this project came from exactly this.

**One caveat worth knowing:** ADR-0014 pins ziptastic **1.2.0**; the estate ships **1.4.5** (CHCE
format v8). The adapter's 27 tests pass against 1.4.5, but a protocol-scope run should record which
version produced it — `benchmarks/selector_probe.py` records the version string beside every number
for that reason.

## 0.5 Preflight — ten seconds, and it saves the other seven hours

```bash
python scripts/p0_preflight.py \
    --corpus corpus/gutenberg-r0 \
    --manifest benchmarks/MANIFEST.json \
    --out-root benchmarks \
    --bin-dir ~/heavenzip/bin \
    --out benchmarks/p0-preflight.json
```

It checks the five things that otherwise fail *late*:

| Check | NO-GO means |
|---|---|
| corpus ≥ 1 GiB, every manifest file present and the right size, all three splits | a partial snapshot fails at the first split |
| `xz` on PATH | P0.3 wants the **CLI** row, not `xz9-lzma`; without it every split must be re-run |
| `7z` on PATH | P0.3a wants a `ppmd-7z` row in every split — the measurement that settles OQ-18 |
| ≥ 2 GiB free where artifacts land | three splits × 3 reps × six systems |
| machine class vs `benchmarks/env.json` | P0.2 wants a **second** class; the same box is a re-run, not a second class |

Exit code **2** means something is NO-GO; the report names each one and how to fix it.
`--allow-missing-7z` is for running a deliberately smaller claim — the report records that it is
smaller, and OQ-18 stays open.

## 1. Corpus, if it is not on this machine yet

```bash
python benchmarks/harness.py corpus-fetch --dest corpus/gutenberg-r0 --owner-root data/raw --tier auto
python benchmarks/harness.py corpus-reconcile --root corpus/gutenberg-r0
python benchmarks/harness.py manifest --root corpus/gutenberg-r0 --out benchmarks/MANIFEST.json
python benchmarks/harness.py verify --manifest benchmarks/MANIFEST.json
python benchmarks/harness.py audit-splits --manifest benchmarks/MANIFEST.json
```

`corpus-fetch` needs network access. If the snapshot is already on a disk, copy it and skip the
fetch; `manifest` + `verify` are what make it auditable. **`verify` must report zero problems** —
a corpus that does not verify produces numbers nobody can defend.

## 2. Record the machine

```bash
python benchmarks/harness.py env --out benchmarks/env.json
```

This is the file P0.2 is judged against: a second machine class means a second `env.json` beside
the first, not a second run on the same box.

## 3. The runs — one command per split, all systems

```bash
# train
python benchmarks/harness.py run --manifest benchmarks/MANIFEST.json \
    --split train --reps 3 --revision 7 \
    --systems "lexora,lexora19,zstd19,xz9,ppmd-7z,lexora-chce,chce-raw" \
    --out benchmarks/results-p0-train.json

# validation
python benchmarks/harness.py run --manifest benchmarks/MANIFEST.json \
    --split validation --reps 3 --revision 7 \
    --systems "lexora,lexora19,zstd19,xz9,ppmd-7z,lexora-chce,chce-raw" \
    --out benchmarks/results-p0-validation.json

# heldout
python benchmarks/harness.py run --manifest benchmarks/MANIFEST.json \
    --split heldout --reps 3 --revision 7 \
    --systems "lexora,lexora19,zstd19,xz9,ppmd-7z,lexora-chce,chce-raw" \
    --out benchmarks/results-p0-heldout.json
```

Notes that matter:

- **`--split` per file, not one command.** The three artifacts are what a revision is published
  from, and a single combined run cannot be re-run split-by-split when one of them fails.
- **`--revision 7`** — R6 is the last used number. The harness stamps it into every artifact, and
  it is what `tests/test_benchmark_claims.py` will check documents against.
- **`--systems` is explicit.** The default is `zstd19,xz9`; the CHCE pair and `ppmd-7z` are the
  whole point of this run and will not appear unless named. A system that is unavailable is
  recorded as skipped rather than stubbed — never stubbed.
- **`xz9`, not `xz9-lzma`.** P0.3 is about the CLI. `xz9-lzma` is the library, and it is what R6
  used.

## 4. Verify the artifacts before publishing

```bash
python - <<'PY'
import json, pathlib
for split in ("train", "validation", "heldout"):
    doc = json.loads(pathlib.Path(f"benchmarks/results-p0-{split}.json").read_text())
    systems = sorted({r["system"] for r in doc["rows"]})
    print(f"{split:11s} revision={doc['benchmark_revision']} rows={len(doc['rows'])} systems={systems}")
    assert doc["benchmark_revision"] == 7, "the revision did not reach the artifact"
    assert {"lexora", "zstd19", "xz9"} <= set(systems), "a required system is missing"
PY
```

Every split must show the same systems. A split where `ppmd-7z` silently vanished is the failure
mode `--allow-missing-7z` exists to make *visible*.

## 5. Sign off, then publish

This is P7.2 and it is the owner's, not a session's: [RELEASE_PROCESS](RELEASE_PROCESS.md) and
[ADR-0001](ADR/ADR-0001-gate-scope.md) make the verdict yours. Publishing means a revision block in
[BENCHMARK_RESULTS.md](BENCHMARK_RESULTS.md) with its manifest hash, environment and per-split
tables — and then `scripts/check-benchmark-claims.py --strict`, which CI runs, will hold every
document that quotes the numbers to the artifact.

## What this run does *not* close

- **`.lxdb`** opens *after* this, not before (ADR-0013 is gated on it by owner decision).
- **REQ-CAN-007** — the cleaning-error rate needs two human reviewers on a worksheet
  (`docs/CLEANING_AUDIT.md`), and no amount of compression measurement substitutes for it.
- **The claim itself.** A published revision is a measurement with a scope label. Whether the
  pipeline passes ADR-0001 is the verdict step, and it can come out either way — R6 already shows a
  small advantage over zstd-19 and a small deficit against xz-9.

## If something fails

| Symptom | Cause | Fix |
|---|---|---|
| `verify` reports problems | corpus copied incompletely, or a file was edited | re-copy; never edit corpus files — the manifest pins their sizes and hashes |
| a system is "skipped" in the artifact | binary absent at run time | install it and re-run **that split**; the artifact records the skip rather than faking a row |
| preflight says SAME machine class | this is R6's box | P0.2 needs a second one; run on a different class and keep both `env.json` files |
| a split takes far longer than 8 h | CHCE at 0.39 MiB/s on a slow disk | run the splits in separate sessions; each artifact is independent |
