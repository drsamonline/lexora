# The path to v1.0 — what is left, and in what order

> **Status:** Active. **This is the only list of remaining work.** If it disagrees with a
> session note or a chat summary, this file wins on *sequencing*; accepted ADRs still win on
> *decisions*. Update it whenever something lands — an item that is done and still listed
> here is worse than no list.
> **Last verified:** 2026-11-07 (Session 76, PDF ingestion landed — P3.1/P3.2/P3.4 done. Session 75, against `main` at `bc6e58b`, gate 567 passed / 1 skipped)
> **Related:** [ROADMAP.md](ROADMAP.md) (milestones) · [PHASES.md](PHASES.md) (phases) · [DECISIONS.md](DECISIONS.md) (ADRs + open questions) · [STATUS.md](STATUS.md) (verified state) · [NEXT_SESSION.md](NEXT_SESSION.md) (resume card)

### Scope change (2026-11-08): languages arrive as plugins

The owner's direction — *support other languages through plugins, built later and added later, so
Lexora becomes a practical tool* — moves multilingual support from "a branch of the canonicaliser
per language" to **an interface with implementations behind it** ([ADR-0022](ADR/ADR-0022-language-plugins.md)).
What that changes here:

- **English is no longer the only language *or* a special case.** It becomes the first plugin,
  shipped with the seam so the interface is exercised from day one.
- **Hindi, Gujarati and Chinese become packages**, not core work. The charter's multilingual goal
  stops depending on this repository's release cycle.
- **v1.0's language condition changes** from "English, Hindi and Gujarati supported" to "**the
  plugin seam is proven by at least two languages**" — which is a weaker promise on paper and a
  much more honest one, because the second language is what proves the interface.
- **A new condition appears:** an archive written with a plugin must be **readable without it**.
  That is the property that keeps the format safe as the plugin ecosystem grows.

## 1. The final product — v1.0, defined

Lexora v1.0 is **an offline, low-resource text archive you can query**, whose compression
claims are earned rather than asserted. Concretely, it is done when all six hold:

1. **Ingest.** A folder of TXT and PDF files becomes canonical text — PDF text layer
   extracted, scanned pages optionally OCR'd, with a clear report when OCR is absent
   (REQ-ING-001…004).
2. **Exactness.** `decode(encode(C)) == C` for every canonical byte string, enforced by a
   round trip at build time and tested per block. *Already true.*
3. **A measured claim.** A published benchmark revision showing the ratio against both frozen
   baselines, at protocol scope, with owner sign-off — not a subset run.
4. **One queryable archive file.** `.lxdb`: documents, metadata, full-text and a compressed
   block pool in a single file, with append/edit/delete/compact, crash-safe commit, and
   bounded decode of only what a query touches.
5. **A GUI** over the same operations, as a client of the CLI (ADR-0011), tested offscreen.
6. **A release.** Versioned package, release dry-run, CI green, no claim in any document that
   is not backed by an artifact in this repo.

Not in v1.0: original scan/OCR reconstruction, lossy summarisation, a zip replacement,
multi-user concurrency, cloud anything.

## 2. Where we actually are

| Piece | State | Evidence |
|---|---|---|
| Canonicalisation + `.lxz` v0 container | **Done** | ADR-0007; 9 golden vectors + invariant suite |
| Exact round trip | **Done** | per-block round-trip gate; fuzz suites |
| Codec choice | **Done** | ADR-0014 (registry), ADR-0015 (zstd default, CHCE max-ratio preset) |
| CHCE advantage measured | **Done, smoke + protocol-shaped** | −19.75 % (smoke), −18.51 % vs `xz -9` (R6) |
| Queryable archive (`lexora db`) | **Done, sidecar design** | ADR-0016; 21 tests; 0.34 s query / 0.47 s retrieval |
| `.lxdb` single-file | **Proposed, no bytes** | ADR-0013, gated on G2 |
| Protocol-scope benchmark (G2) | **Shape done, scale not** | R6: 3 splits, 3 reps, 6 systems, leak audit clean, at 5.9 MB |
| PDF ingestion (text layer) | **Done** | ADR-0017; `ingest.py`; 15 tests |
| OCR (external Tesseract plugin) | **Done** | ADR-0019; `ocr_core.py`; 15 tests; real 99-page scan |
| Multilingual (hi, gu) | **Not started** | deferred by owner; English-only build scope |
| GUI query view | **Done** | `gui/query.py`; 14 offscreen tests; parity with the CLI asserted |
| GUI on subprocess (ADR-0011) | **Done** | `service.py` is a CLI client; 10 argv-level tests |
| Release | **Not started** | M7 / P7 |

> **Execution order lives elsewhere.** [BATCH_PLAN.md](BATCH_PLAN.md) groups the same work
> into cost-based batches — quick wins first, small items combined, the hardware-bound ones
> last. This file stays the scope of record; that one is the order of work.

## 3. Remaining work, in dependency order

### P0 — Close gate G2 (blocks `.lxdb`, unblocks the headline claim)

The only thing between R6 and a publishable revision. **Environmental, not analytical** —
R6 already showed the result reproduces across splits and reps.

| # | Item | Done when |
|---|---|---|
| P0.1 | Run on the **1.054 GiB** snapshot, not 5.9 MB | Artifacts for all three splits at full size |
| P0.2 | **Second machine class** (REF-4G) for the reference profile | A second environment in the artifact |
| P0.3 | **`xz` via the CLI**, not `xz9-lzma` | `xz9` row present and timed comparably |
| P0.3a | **Include `ppmd-7z`** — the charter named PPMd (ADR-0003) and it was never measured; it came out 18.4 % under `xz -9` ([ECOSYSTEM_REVIEW](ECOSYSTEM_REVIEW_2026-11-08.md)) and decides OQ-18 | A `ppmd-7z` row in every split |
| P0.4 | **Owner sign-off**, then publish as a revision | A row in BENCHMARK_RESULTS.md, not a draft |

Budget **hours**: CHCE runs at 0.39–0.45 MiB/s and the harness compresses every file twice
per rep (measurement + forked RSS probe). See [R6_PROTOCOL_SHAPED_2026-11-07.md](R6_PROTOCOL_SHAPED_2026-11-07.md).

### P1 — `.lxdb`, the single queryable file (blocked on P0)

Design is recorded and must not be re-litigated: [ADR-0013](ADR/ADR-0013-lxdb-layout.md).
One file = superblock + compressed serialised-SQLite index image + append-only payload
blocks + segment directory. Mutation = append payload, rewrite index, commit by superblock
flip. **Build order:**

| # | Step | Done when |
|---|---|---|
| P1.1 | Superblock + payload append + read-only reader | Round-trips a document; refuses a bad superblock |
| P1.2 | Index image: serialise, compress, hash-check, materialise | Query works from the embedded image (measured 10 ms) |
| P1.3 | Commit-by-flip with **crash injection** | Kill between append and flip → recovers to previous generation |
| P1.4 | Compaction | Dead ratio triggers a merge; reports what it removed |
| P1.5 | Layout revision of ADR-0013 with magic, widths, ordering, vectors | Vectors checked in, conformance suite green |
| P1.6 | `catalog.py` moves onto `.lxdb`; `lexora db` surface unchanged | ADR-0016's 21 tests pass against the new storage |

### P2 — GUI (independent of P0/P1; the backend is already done)

Per ADR-0011 the GUI is a **client of the CLI**, so the contract is fixed: search box →
`lexora db search --json`, result list, preview → `lexora db get`.

| # | Item | Done when |
|---|---|---|
| ~~P2.1~~ | ~~Query panel (search + metadata filters + result list)~~ | **DONE 2026-11-07** — `gui/query.py`, reachable from the ribbon; 14 offscreen tests |
| ~~P2.2~~ | ~~Preview pane decoding only the selected document~~ | **DONE 2026-11-07** — test asserts the other match's text is absent from the preview |
| ~~P2.3~~ | ~~Moving `gui/service.py` onto subprocess calls (the open half of ADR-0011)~~ | **DONE 2026-11-08** — every byte-level operation is a CLI call; `tests/test_service_is_a_cli_client.py` asserts argv, stdin payload and exit-code mapping. `run_canon_meta` stays in-process, documented and asserted as the one exception |
| ~~P2.3a~~ | ~~Decide the exit code for an out-of-range `--level`~~ | **DECIDED 2026-11-07 by [ADR-0018](ADR/ADR-0018-level-usage-error.md): exit 2 on every surface.** The CLI moved to where the GUI already was, so no GUI code changed. 23 tests, including a CLI↔GUI parity assertion |
| ~~P2.3b~~ | ~~CLI cannot read stdin; no `zdecode` verb~~ | **DONE 2026-11-08** — `_read("-")` is stdin, `_open_input()` gives streaming paths a seekable handle, and `zdecode` exists. Found on the way: `zround --out -` wrote nothing at all |
| P2.4 | Notices for the `[gui]` extra if it ships (R3 obligation) | NOTICE + LGPL/GPL texts + About-view notice |

Needs a **Qt-capable machine** (PySide6 + `libegl1`); nothing here can be honestly claimed
without offscreen tests.

### P3 — Ingestion: PDF, then OCR (independent; the other half of the original pitch)

| # | Item | Done when |
|---|---|---|
| ~~P3.1~~ | ~~PDF text layer extraction, page order preserved (REQ-ING-002)~~ | **DONE 2026-11-07** — `src/lexora/ingest.py`, pypdf, page order asserted, 15 tests |
| ~~P3.2~~ | ~~Provenance in archive metadata (REQ-ING-004)~~ | **DONE 2026-11-07** — `mode`/`engine`/`engine_version`/`pages`/`pages_without_text`/`text_sha256` stored and filterable |
| ~~P3.3~~ | ~~Optional OCR with graceful skip (REQ-ING-003)~~ | **DONE 2026-11-07** — [ADR-0019](ADR/ADR-0019-ocr-plugin.md): Tesseract as an external binary, `--ocr --lang`, no PDF renderer needed; 15 tests; verified on a real 99-page scan. **Language scope still open** (that scan needs `eng+chi_sim`) |
| ~~P3.4~~ | ~~PyMuPDF needs its own ADR first (AGPL)~~ | **RESOLVED 2026-11-07 by [ADR-0017](ADR/ADR-0017-pdf-engine.md):** pypdf (BSD-3) chosen instead — the copyleft question is removed, not answered |
| P3.5 | Cleaning-error rate ≤1 % operationalised (REQ-CAN-007, ADR-0004) | Sample-review report |

### P4 — Correctness and consistency debt

| # | Item | Why it matters |
|---|---|---|
| ~~P4.1~~ | ~~F1: `codec_id` names a level it does not use~~ | **DONE 2026-11-08** — [ADR-0020](ADR/ADR-0020-codec-id-naming.md) accepted (owner: rename now). Id is `zstd-raw`; the old id is a read-only alias; legacy vector kept as a fixture; 4 compatibility tests |
| ~~P4.2~~ | ~~`--jobs` measured *slower*~~ | **Measured twice, now at scale** (88 files / 79 MB: canon 1.53→2.27 s, pack 6.14→8.45 s for jobs 1→4). Kept and documented as a loss on small-core hosts — removing a flag is a behaviour change with no upside |
| P4.3 | Second machine class / resource limits at 4 GiB with the index in RAM | ADR-0013 puts the index in memory (~7 % of text); must be tested against the target machine |
| P4.4 | **`pyside6<6.12` is a workaround, not a preference** | 6.12 aborts with a Bus error *after* the GUI suite passes, at Qt teardown on a headless runner. The tests are green; the exit code is not. Revisit when a later release fixes it, or when the GUI suite stops leaking widgets at exit |

### P5 — Documentation debt

| # | Item |
|---|---|
| P5.1 | **The Session-69→70 hole**: `SESSION_LOG.md` jumps from 2026-10-29 to Session 70, but `DECISIONS.md` records OQ-6/OQ-15 resolved 2026-10-30 and `STATUS.md` a 2026-11-03 verification. That work has no session record |
| P5.2 | `CONTRIBUTING.md` has no contribution-licensing line — matters the moment an outside patch arrives |
| P5.3 | `ROADMAP.md` milestone statuses lag reality (M2 in progress, M5 direction decided) |

### P6 — Release (M7 / P7)

Versioned package, release-process dry run, CHANGELOG "Unreleased" emptied at cut, CI green,
badges earned for real, migration guide activated.

## 4. Do-not-forget register

Things that were agreed, cost real work, and would be easy to lose in a later session. Each
is someone's actual decision, not a suggestion:

- **CHCE stays a preset, zstd stays the default** ([ADR-0015](ADR/ADR-0015-codec-policy.md)). Do not flip `DEFAULT_CODEC` on smoke or protocol-shaped numbers; that is what P0 is for.
- **`.lxdb` was deliberately not built yet** ([ADR-0013](ADR/ADR-0013-lxdb-layout.md), Proposed). The owner declined to override the gate. Do not start it before P0.
- **The GUI is a client of the CLI** ([ADR-0011](ADR/ADR-0011-gui-process-separation.md)) — not an in-process library consumer. This was an LGPL question before it was an architecture one.
- **Word-dictionary, delta, byte-shuffle and LZP preprocessing are measured dead** (ziptastic's negative-results table). Do not re-propose them; −0.38 % on English and +0.93 % on Polish is the number that killed the best-looking one.
- **CAN-R01 makes compressed output larger for non-ASCII text** — deliberately. Canonical UTF-8 and minimum bytes are different objectives; do not "fix" the canonicaliser for ratio.
- **Index costs ~7 % of text and is stored uncompressed** ([ADR-0016](ADR/ADR-0016-queryable-archive.md)). That is the price of queryability, not a bug to optimise away by compressing the index in place.
- **Multilingual and PDF/OCR are still unbuilt** — the current product is English TXT only, which is a scope reduction, not a completed goal.

## 5. Sequencing rules (do not break these)

1. **No format bytes before the gate.** `FORMAT_LXDB.md` G2 exists because freezing a layout
   before the benchmark that judges it is the error ADR-0007 avoided for `.lxz`.
2. **ADR before behaviour change.** A default, a format field or a licence change gets a
   record, not a commit message.
3. **Measure before claiming.** No number enters BENCHMARK_RESULTS.md outside a published
   revision with its tier label; no ratio claim without an artifact.
4. **Verify before reporting done.** The gate command runs and its output is read —
   `PYTHONPATH=src:. python3 -m pytest -q` plus `python3 scripts/linkcheck.py`.

## 6. What we are deliberately not doing

A `.zip` replacement; lossy text compression or summarisation; beating baselines on
non-text data; multi-user concurrency or a server; a hand-written query engine (SQLite is
embedded for exactly that reason); neural compression; formal security certification.
