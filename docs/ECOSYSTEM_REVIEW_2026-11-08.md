# Ecosystem review — eight repositories, 2026-11-08

> **Why this exists.** The owner sent eight links with no instruction. Read as the same
> question as ziptastic: *what are these, and what can Lexora actually take?* Every claim
> below was checked against the repo (metadata, README, licence file) or measured here; nothing
> is inferred from a repository name.
> **Scope:** what is worth adopting, what is worth reading before writing `.lxdb`, and what is
> a different product wearing similar words.

## The table

| Repository | What it actually is | Licence | Verdict |
|---|---|---|---|
| [phiresky/sqlite-zstd](https://github.com/phiresky/sqlite-zstd) | SQLite extension: transparent **row-level** zstd compression with per-group **dictionary training** and incremental maintenance. 1.7k★, Rust | **LGPL-3.0** | **Evaluate** — a genuine alternative to Lexora's blob store |
| [miurahr/py7zr](https://github.com/miurahr/py7zr) | Pure-Python 7z read/write; PPMd/LZMA2/Zstd/Brotli/BCJ/Delta/AES. 559★ | **LGPL-2.1** (PPMd via `pyppmd`) | **Adopted as a baseline** — see the measurement below |
| [borgbackup/borg](https://github.com/borgbackup/borg) | Deduplicating archiver: content-defined chunking, segments, compaction, authenticated encryption. 13.9k★ | BSD-3-Clause | **Read before `.lxdb`** — closest existing design to ADR-0013 |
| [zpaq/zpaq](https://github.com/zpaq/zpaq) | Journaling archiver with **context mixing**; the practical ratio ceiling for text. 643★, last push 2022 | Public domain | **Reference only** — ratio ceiling and journaling model |
| [meta/zstd](https://github.com/meta/zstd) | The reference implementation behind `python-zstandard` | BSD-3 / GPLv2 | **Reference** — `--train` dictionaries, version pinning |
| [headroomlabs-ai/headroom](https://github.com/headroomlabs-ai/headroom) | Compresses tool output/logs/RAG chunks **before an LLM reads them**. 79k★ | Apache-2.0 | **Out of scope** — lossy by design |
| [liufanfanlff/C3-Context-Cascade-Compression](https://github.com/liufanfanlff/C3-Context-Cascade-Compression) | Research code: LLM-based "context cascade" text compression. 318★ | none stated | **Out of scope** — lossy |
| [eschluntz/compress](https://github.com/eschluntz/compress) | GPT-based text compression for keyboard expansions. 1.4k★ | none stated | **Out of scope** — lossy |

## The measurement that matters: PPMd was never in the table

`py7zr` + `pyppmd` make PPMd available as a plain `pip install` — no external binary. Measured
here on the same 19-file, 18.5 MiB canonical Gutenberg sample used for the CHCE work:

| codec | ratio | vs `xz -9` | throughput |
|---|---|---|---|
| zstd-9 | 0.3352 | +10.9 % | 15.9 MiB/s |
| zstd-19 | 0.3059 | +1.2 % | 1.4 MiB/s |
| `xz -9` | 0.3022 | — | 1.1 MiB/s |
| **PPMd (7z)** | **0.2466** | **−18.4 %** | **2.43 MiB/s** |
| CHCE `-9` | 0.2425 | −19.7 % | 0.50 MiB/s |

Two things follow, and the second is uncomfortable for a decision already made.

1. **The published baselines were incomplete.** Lexora compares against zstd, xz and brotli.
   PPMd beats `xz -9` by 18.4 % — bigger than the gap the project has been arguing about — and
   it is named in the charter (ADR-0003) as a comparison point that was never actually measured.
   It is now a harness system (`ppmd-7z`), so the protocol run can include it.

2. **CHCE's ratio advantage over PPMd is 1.7 %, for 5× the encode time and an external binary.**
   ADR-0015 made CHCE the max-ratio preset on the strength of a −19.75 % result. Against a
   baseline that was in the table, that number is still right; against PPMd it is nearly a tie
   bought with an order of magnitude of speed and a build dependency. A user choosing "smallest
   file" would usually be better served by PPMd; a user on a machine that cannot install
   `ziptastic` can *only* be served by PPMd.

**Caveats, stated rather than buried:** one corpus class (Gutenberg prose), smoke scope, PPMd at
default 7z parameters (untuned — larger order/memory would likely close the 1.7 %), and the
measurement includes the 7z container header (~120 B/file). This is enough to justify putting
PPMd in the table and reopening the preset question; it is not enough to publish a claim.

## What to take from each, concretely

**borg — read it before implementing ADR-0013.** Its segment/compaction model is the same shape
`.lxdb` needs: append-only segments, a commit record, compaction that rewrites only live data,
and authenticated encryption over both. ADR-0013 already chose append-payload /
rewrite-index / commit-by-superblock-flip; borg is the worked example of what breaks in that
design (partial commits, interrupted compaction, index/payload divergence) and is worth a few
hours before the crash-injection tests are written.

**sqlite-zstd — the architectural alternative worth an ADR.** Lexora keeps the index in SQLite
and the payload in `.lxz` blobs *beside* it. sqlite-zstd collapses that: compressed columns
inside SQLite, random access retained, dictionaries trained per group. Against it: LGPL-3.0
loaded in-process (needs the ADR-0009 treatment), blobs "fully copied into memory" on read, no
`ATTACH`, partial DDL. It also does the thing Lexora's M4 phase wants — **dictionary training** —
and does it on rows rather than documents, which is the right granularity for small records.
Worth an ADR comparing it with the blob store before `.lxdb` freezes anything.

**zpaq — the honest ceiling.** If a future benchmark reports Lexora at ratio X, zpaq is the
number that says how much room is left. Its journaling (add/version/extract) is also the
mutation model `.lxdb` is imitating. Reference only: last push 2022, and context mixing is far
outside what this project would implement.

**meta/zstd — dictionaries and pinning.** `zstd --train` is the mechanism behind the M4
dictionary phase and behind sqlite-zstd's grouping; the repo is also where the pinned version in
`pyproject.toml` comes from. Nothing new, but it is the source of truth for both.

## Why the three LLM compressors are out of scope — and why that is worth writing down

`C3`, `eschluntz/compress` and `headroom` all compress text by *understanding* it and
regenerating it. They are **lossy by construction**: the original bytes cannot be recovered, by
design. Lexora's one promise is `decode(encode(C)) == C`, byte-exact, for every input. Adopting
any of them would not extend Lexora; it would make it a different product with a weaker
guarantee, and the guarantee is the whole reason to trust an archive.

`headroom`'s 79k stars is a market signal worth naming honestly rather than ignoring: the
demand is for **compressing what an LLM reads**, not for storing documents smaller. That is a
real product and it is not this one. If Lexora ever wants a "summarise for retrieval" feature it
belongs beside the archive, labelled lossy, never inside it.

## Actions taken

- `ppmd-7z` registered as a harness system, with an availability gate (no `py7zr` → a named skip,
  never a silent drop). Measured in the harness: 0.2291 vs `lexora19` 0.2857 on a 4-file subset.
- `py7zr` + `pyppmd` added to the `dev` extra — a benchmark dependency, not a runtime one.
- **OQ-18 opened, briefly answered, and re-opened.** [ADR-0021](ADR/ADR-0021-codec-policy-v2.md) made PPMd
  the max-ratio preset and was **withdrawn the same day**: `pyppmd`/`py7zr` corrupt 3–8 % of real
  documents. PPMd survives as a *baseline* only — and the ratio finding stands. ADR-0015's reasoning was sound for the evidence it had;
  this evidence is new.
