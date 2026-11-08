# Next Session Resume Card

**Last verified state:** 2026-11-09 — **`v0.1.0-alpha.1` is released.** `main` at `1862c6d`,
tag `v0.1.0-alpha.1`, **736 tests, 0 skipped**, CI green, linkcheck clean. The published wheel was
downloaded back from GitHub and its SHA-256 matched the build.

**Read this first, then [BATCH_PLAN.md](BATCH_PLAN.md) for the order and [PATH_TO_V1.md](PATH_TO_V1.md)
for the scope.** This card is only the state; those two are the plan.

## Where the project is

| | |
|---|---|
| Release | `v0.1.0-alpha.1` — alpha, **not for production data**; R5 (protocol benchmark) is the only unmet precondition |
| Tests | 736 passed, 0 skipped |
| CLI | 11 verbs; 2 codecs (`zstd` default, `ziptastic` CHCE optional) |
| Archive | `.lxz` v0 frozen (ADR-0007); `codec_id` level-neutral since ADR-0020, old id read-only |
| Query | `lexora db` — SQLite index over `.lxz` payloads; 0.34 s query, index 7.6 % of text |
| Ingest | TXT/PDF text layer; OCR via external Tesseract (ADR-0019) |
| GUI | `lexora-gui` → Query archive…; shells out to the CLI (ADR-0011) |
| Languages | plugin seam live (ADR-0022); **English only** |

## What is NOT done, in the order it matters

1. **The protocol-scope benchmark (R5).** Blocks the compression claim *and* `.lxdb`. Needs a
   machine with ~2 GB disk, `xz`, and ~6–8 hours. Commands: PATH_TO_V1 §P0. `ppmd-7z` is now in
   the table, so this run also settles OQ-18.
2. **A second language.** The seam is built and tested; no second implementation exists. Chinese
   would prove it against the owner's own scanned document; Hindi/Gujarati are the charter's list.
3. **`.lxdb`** (ADR-0013, Proposed) — gated on (1) by owner decision.
4. **OCR accuracy** — plumbing verified on a real 99-page scan, accuracy never checked against a
   human transcript.
5. **Header/footer dedup** (CAN-R10) — the supplied scan repeats one stamp 99 times; needs the
   ADR-0004 error metric before code.
6. **Encryption profile** — ADR-0009 left it Proposed.
7. **Catalog tokenizer recording** — small; only matters once a second tokenizer exists (CJK).

## Open decisions

- **OQ-18** — should PPMd be the max-ratio preset? **Blocked on a working implementation**:
  `pyppmd`/`py7zr` corrupt 3–8 % of real files (ADR-0021 withdrawal). Candidates: the `7z` binary
  as an external plugin, or PPMd inside ziptastic.
- **OCR language scope** — English only, English + Chinese, or add Hindi/Gujarati.

## Standing rules that are easy to lose

- **Verify before claiming.** Three sessions in a row found a check that lied: a corpus sweep that
  concatenated files, a "broken" codec that had never been broken, and a test fixture that was one
  sentence repeated 400 times. Run the command, read the output, and prefer the check where you
  *see* the failure.
- **`--level` is a usage error (exit 2) when out of range** on every verb (ADR-0018).
- **PPMd is a baseline, not a codec** (ADR-0021 withdrawn). A test asserts it stays unregistered.
- **Plugins affect ingestion only; decoding never needs one** (ADR-0022).
- **English keeps the `lexcan-0.1` provenance label** deliberately — no archive is rewritten twice
  in a week.
- **The harness measures raw bytes; lexora packs canonical bytes.** A green baseline row is not
  proof the codec path is sound.
