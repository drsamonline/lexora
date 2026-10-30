# Release notes — unreleased body of work (Sessions 39–64)

> **Status:** No release exists and no version tag has ever been cut (`docs/DECISIONS.md` OQ-9 is still open). This document records what the tree contains *now* so a future release has something honest to draw on — it is not a changelog of releases, and nothing here is published as a supported artifact.
> **Related:** [CHANGELOG.md](../CHANGELOG.md) (per-session detail) · [STATUS.md](STATUS.md) · [CLI_REFERENCE.md](CLI_REFERENCE.md) · [R4_SMOKE_DRAFT.md](R4_SMOKE_DRAFT.md) · [benchmarks/README.md](../benchmarks/README.md)

## What this project is, in one paragraph

LEXORA canonicalizes text into deterministic bytes and compresses those bytes with a guarantee of **byte-exact recovery**: `decode(encode(C)) == C`, enforced at build time. The `.lxz` v0 container is frozen (ADR-0007), every core path streams so memory is flat in document size, and the CLI can canonicalize, pack, unpack, verify, inspect, batch and self-diagnose a whole tree.

## What is new since the last status snapshot (Session 37)

**Memory: every core path is now bounded.**
- `pack`, `unpack` and `canon` each gained a streaming implementation, byte-identical to the buffered one and pinned by tests down to one-byte chunks. Encode peak RSS went from 196.9 MiB to **126.1 MiB flat** at 32 MiB input; decode from 116.1 MiB to **34.8 MiB**; canonicalization from 216.2 MiB to **35.5 MiB**. Measured in `benchmarks/results-rss-core.json`.

**The CLI grew from five verbs to nine.**
- `verify` — audit an archive without producing payload bytes; best-effort per-block reporting, exit 7 on any failure.
- `inspect` — a readable summary of one archive (or a directory of them) including the **REQ-CMP-004 accounting identity**: header + Σ frames + index + trailer must equal the file length. It prints `OK` or `MISMATCH` and exits 7 on mismatch.
- `batch` — many files in one invocation, `--op canon|pack|unpack`, deterministic ordering, structure preserved, per-file JSON report. Partial failure returns **exit 1**; `--stop-on-error` returns the failing file's own code.
- `doctor` — install-health report with a **live round-trip self-test**, so a bug report carries facts instead of guesses.

**Hardening, with real bugs found rather than asserted.**
- Fuzzing the reader found two genuine gaps: the reader trusted the *header's own* limits (a hostile header could declare a 2^60 block cap and defeat every pre-allocation check — now clamped to LIM-01/LIM-02 with `E-RES-004`), and a corrupt zstd frame header could drive an allocation attempt (now refused on a frame-vs-index size mismatch before decoding).
- Fuzzing the writer found that packing into a missing or unwritable directory raised a **traceback and exited 1**, contradicting the documented exit-3 contract.
- Real signals: the atomic-write guarantee holds under SIGINT, SIGTERM and SIGKILL — no partial destination ever — and SIGTERM no longer leaves temp-file debris.

**Measurement now includes LEXORA itself.**
- Until Session 60 the results tables measured only the *baselines* against each other. The harness now registers `lexora` and `lexora19` as systems, so the pipeline sits beside zstd-19 and xz-9 on identical files with identical cost accounting.
- **R4, three splits, 172 files / 78.6 MiB, 3 reps:** `lexora19` **0.3090**, `zstd19` **0.3109**, `xz9-lzma` **0.3068** — LEXORA between the two baselines, smaller than zstd-19 on 167 of 172 files, larger than xz-9 on all of them. **Smoke scope, not a verdict**; see the draft.

**Licensing settled.** PolyForm Noncommercial 1.0.0 (ADR-0009), with `LICENSE` normative and its `Required Notice:` line travelling with every artifact. The GUI's LGPL question is answered structurally: the GUI becomes a **client of the CLI** (ADR-0011), so Qt is never linked into the engine.

**Two decisions recorded that shape what comes next.** `.lxdb` v0 will be a container of `.lxz` members (ADR-0010) — the block-pool design that actually fixes per-document overhead is named as the successor with a measurement-based trigger. And the default encode level is **9** (ADR-0012), one constant shared by library, CLI and GUI, replacing a state where the CLI used 19 and the GUI settings hardcoded 3.

## How to try it

```bash
pip install -e ".[dev]"
lexora doctor                                    # is this install healthy?
printf 'alpha\r\nbeta\r\n' > in.txt
lexora canon --in in.txt --out canon.txt         # canonicalize
lexora pack  --in canon.txt --out a.lxz          # pack (default level 9)
lexora verify  --in a.lxz                        # audit
lexora inspect --in a.lxz --verify               # human-readable summary
lexora unpack  --in a.lxz --out back.txt         # decode, refusing unverified output
diff canon.txt back.txt && echo "round trip exact"
```

For a tree: `lexora batch --in DIR --out-dir OUT --op canon` (then `--op pack`, `--op unpack`, and `lexora inspect --in OUT`).

## Test and gate state

- `python3 -m pytest -q` → **492 passed, 1 skipped** (the skip is a Qt-dependent widget test; PySide6 is an optional extra).
- `python3 scripts/linkcheck.py` → **ALL INTERNAL LINKS OK**.
- The suite includes deterministic fuzz suites for the reader and writer, an interruption suite that kills real processes with real signals, and streaming-parity suites at chunk sizes down to one byte.

## Known limits (stated, not hidden)

- **The corpus meets the ≥1 GiB requirement** (2395 files / 1.054 GiB, OQ-8) but **no protocol-scope benchmark run has been done** — R4/R5 use bounded subsets, so the numbers are smoke scope and will change.
- **No GUI work landed.** ADR-0011 chose process separation; implementing it needs a Qt-capable machine, and this development environment cannot install PySide6.
- **`.lxdb` has no byte layout** — the direction is decided (ADR-0010), the layout is gated on the corpus benchmark and assigned to ADR-0013.
- **`lexora` does not beat xz-9** on size at equal level, and the current design cannot: v0 is canonicalization plus zstd. That is what the roadmap's PPMd/Brotli/dictionary phases exist for.
- **Peak RSS is not measurable in this container** (no `VmHWM`); those numbers come from `ru_maxrss` in `benchmarks/rss_probe.py` instead.
- **CI is paused** by owner decision (OQ-15); the local gate is `pytest` plus linkcheck.
- **No push from the agent environment**: the brokered GitHub credential is read-only, so changes arrive as patches applied by the owner.

## What a release would need

A version number and tag (OQ-9), a green CI run rather than a local one (OQ-15), a protocol-scope benchmark with owner sign-off, and a decision on whether the GUI ships at all — `[gui]` is currently an opt-in extra with no shipped artifact.
