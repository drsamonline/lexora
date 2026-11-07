# CHCE on lexora's own corpus — smoke measurement, 2026-11-07

> **Scope: SMOKE.** 19 files, 19.4 MB of canonical bytes, one corpus class, one
> machine, one run. This answers a question the previous session had to leave open —
> *does ziptastic's Silesia advantage transfer to lexora's corpus at all?* — and it
> answers it clearly. It is **not** an ADR-0001 verdict, not a published benchmark
> revision, and not a protocol-scope run. Artifact:
> `benchmarks/results-chce-smoke.json` (per-file rows, binary checksum, corpus list).

## Why this exists

ADR-0014 built the codec seam and deliberately left zstd as the default, because the
only ratio evidence for CHCE was **ziptastic's own** measurement on a 10-file Silesia
subset. That is not this corpus. OQ-16 recorded the gap. This closes it far enough to
decide with, and leaves the protocol run as the step that would make it publishable.

## Method

Every codec saw **identical bytes**: Project Gutenberg text passed through lexora's own
`canonicalize()` (CAN-R01/R02/R05, `lexcan-0.1`) — i.e. what an archive actually
stores. Comparing codecs on raw text would measure a pipeline this project does not
ship. Before any CHCE size was counted, the frame was decoded and compared to its
input; 19/19 were byte-exact.

| | |
|---|---|
| codec under test | ziptastic 1.2.0 (CHCE format v8), `c -9`, serial path, sha256 `4bebce37…` |
| baselines | zstd-9 (lexora's shipped default), zstd-19 (the R5 baseline setting), `xz -9` (lzma preset 9) |
| corpus | 19 Gutenberg texts, 19,824,293 raw → **19,432,350 canonical bytes** |
| machine | 2 vCPU / 2 GiB container — **sizes exact, throughput indicative only** |

## Result

| codec | total bytes | ratio vs canonical |
|---|---|---|
| zstd-9 (default) | 6,514,541 | 0.3352 |
| zstd-19 | 5,944,104 | 0.3059 |
| `xz -9` | 5,871,796 | 0.3022 |
| **CHCE (`-9`)** | **4,712,272** | **0.2425** |

- **CHCE is 19.75 % smaller than `xz -9`**, and 27.67 % smaller than zstd-9.
- **19 of 19 files** are smaller than `xz -9` — no file goes the other way. Per-file
  range: −16.40 % (`pg4300`, Ulysses) to −21.61 % (`pg1342`, Pride and Prejudice).
- Throughput measured here: zstd-9 **15.9 MiB/s**, `xz -9` **1.08 MiB/s**, CHCE
  **0.50 MiB/s**.

The consistency matters more than the magnitude: the per-file spread is 5 points wide
across nineteen different books, which is what a *modelling* win looks like rather than
a lucky sample. Silesia's −11.83 % was dragged down by two binary files where CHCE is
level with `xz`; a pure-prose corpus shows what the text case alone is worth.

## What this does and does not change

**Does.** It settles the question ADR-0014 could not: the effect transfers, and on this
corpus class it is roughly **twice ADR-0001's ≥10 % Pass threshold**. Lexora's R5
position was **+0.77 % worse than `xz -9`**; with CHCE the same pipeline would be
~20 % better. That is the difference between "v0 cannot pass xz by tuning zstd" and a
pipeline that does.

**Does not.**

1. **Make CHCE the default.** Two reasons, both real. It would make an external binary
   mandatory for the base install — today `pip install lexora` needs only zstandard —
   and these numbers are smoke scope. A default change should follow the protocol run,
   not precede it.
2. **Constitute an ADR-0001 verdict.** That gate wants a protocol-scope run on the
   R4/R5 corpus (184 files, 1.054 GiB, three splits) with per-category promotion on
   validation and reproduction on held-out. This sample is one split, one class, no
   held-out set.
3. **Say anything about non-prose.** lexora's scope is English text, so that is what was
   measured. A binary-heavy corpus would land near `xz` (Silesia's `sao`/`samba` rows
   are −0.001 % and −0.64 %).

## Recommendation

Keep `zstd` as `DEFAULT_CODEC` and add CHCE as a documented **max-ratio preset**
(`--codec ziptastic`), which is what the code already does. Then run the protocol-scope
comparison on the R4/R5 corpus; if it reproduces at ~−19 %, the case for flipping the
default — or for making the binary a recommended, not required, install — is
evidence-backed rather than argued. OQ-16 stays open until that run exists, but it is
no longer blocked on a build machine: the release binary works, and `lexora doctor`
confirms it.
