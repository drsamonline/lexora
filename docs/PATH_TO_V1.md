# The path to v1.0 — what is left, and in what order

> **Status:** Active. **This is the only list of remaining work.** If it disagrees with a
> session note or a chat summary, this file wins on *sequencing*; accepted ADRs still win on
> *decisions*. Update it whenever something lands — an item that is done and still listed
> here is worse than no list.
> **Last verified:** 2026-11-07 (Session 75, against `main` at `bc6e58b`, gate 567 passed / 1 skipped)
> **Related:** [ROADMAP.md](ROADMAP.md) (milestones) · [PHASES.md](PHASES.md) (phases) · [DECISIONS.md](DECISIONS.md) (ADRs + open questions) · [STATUS.md](STATUS.md) (verified state) · [NEXT_SESSION.md](NEXT_SESSION.md) (resume card)

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
| PDF / OCR ingestion | **Not started** | M3 / P3 |
| Multilingual (hi, gu) | **Not started** | deferred by owner; English-only build scope |
| GUI | **Partly** — M1–M3 panels exist, no query panel | ADR-0011 implementation open |
| Release | **Not started** | M7 / P7 |

## 3. Remaining work, in dependency order

### P0 — Close gate G2 (blocks `.lxdb`, unblocks the headline claim)

The only thing between R6 and a publishable revision. **Environmental, not analytical** —
R6 already showed the result reproduces across splits and reps.

| # | Item | Done when |
|---|---|---|
| P0.1 | Run on the **1.054 GiB** snapshot, not 5.9 MB | Artifacts for all three splits at full size |
| P0.2 | **Second machine class** (REF-4G) for the reference profile | A second environment in the artifact |
| P0.3 | **`xz` via the CLI**, not `xz9-lzma` | `xz9` row present and timed comparably |
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
| P2.1 | Query panel (search + metadata filters + result list) | Offscreen test: a query returns rows |
| P2.2 | Preview pane decoding only the selected document | Test asserts one decode per selection |
| P2.3 | Ingest/compact actions with progress and refusal surfacing | Parity test: GUI bytes == CLI bytes |
| P2.4 | Notices for the `[gui]` extra if it ships (R3 obligation) | NOTICE + LGPL/GPL texts + About-view notice |

Needs a **Qt-capable machine** (PySide6 + `libegl1`); nothing here can be honestly claimed
without offscreen tests.

### P3 — Ingestion: PDF, then OCR (independent; the other half of the original pitch)

| # | Item | Done when |
|---|---|---|
| P3.1 | PDF text layer extraction, page order preserved (REQ-ING-002) | Fixture PDFs → canonical text |
| P3.2 | Provenance in archive metadata: source, mode, engine/version (REQ-ING-004) | Schema + round-trip test |
| P3.3 | Optional OCR with graceful skip (REQ-ING-003) | CI job with and without OCR |
| P3.4 | PyMuPDF needs **its own ADR** first (AGPL vs PolyForm) | ADR accepted, or a different engine chosen |
| P3.5 | Cleaning-error rate ≤1 % operationalised (REQ-CAN-007, ADR-0004) | Sample-review report |

### P4 — Correctness and consistency debt

| # | Item | Why it matters |
|---|---|---|
| P4.1 | **F1: `codec_id` says `zstd-raw-l19` on level-9 archives** | Every default archive names a level it did not use; level 9 vs 19 indistinguishable. Frozen format field → needs an ADR and a rename window at v0→v1 |
| P4.2 | `--jobs` is documented experimental and measured 20–40 % *slower* | Either find a workload where it wins or drop the flag |
| P4.3 | Second machine class / resource limits at 4 GiB with the index in RAM | ADR-0013 puts the index in memory (~7 % of text); must be tested against the target machine |

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
