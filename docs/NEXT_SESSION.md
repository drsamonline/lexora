# Next Session Resume Card

**Last verified state:** 2026-11-23 — `main` @ `931aac4`. **Gate: 765 passed, 3 skipped** with
both language plugins installed; `scripts/linkcheck.py` → ALL INTERNAL LINKS OK. **No open PRs,
no open issues.** Two alphas are tagged and both say *not for production data*.

**Read this first, then [PATH_TO_V1.md](PATH_TO_V1.md) for the order and the scope.** This card
is only the state and the split of work. That file is the plan of record.

## Where the project is

| | |
|---|---|
| Release | `v0.2.0-alpha.1` (2026-11-18) and `v0.1.0-alpha.1` (2026-11-09) — alpha, **not for production data**; **R5, the protocol benchmark, is still the one unmet release precondition** |
| Tests | 765 passed, 3 skipped — measured 2026-11-23 on `main`, both plugins installed |
| CLI | 11 subcommands; `zstd` default, `ziptastic` (CHCE) as the max-ratio preset; **PPMd withdrawn** (ADR-0021) |
| Archive | `.lxz` v0 frozen (ADR-0007); `codec_id` level-neutral since ADR-0020, old id read-only |
| Query | `lexora db` — SQLite sidecar over `.lxz` payloads; 0.34 s query, index ~7.6 % of text; schema **v3** with per-document tokenizer (ADR-0024) and `doc_grams` for 1–2 character CJK queries |
| Ingest | TXT + PDF text layer (ADR-0017); OCR via external Tesseract (ADR-0019); OCR accuracy never checked against a human transcript |
| GUI | Query view, a client of the CLI (ADR-0011), offscreen-tested |
| Languages | en, hi (`hi-1`), zh (`zh-1`, `trigram`) — selectable with `--language`; Gujarati designed for, not built |

## What is left, in the order it matters

1. **P0 — gate G2, the protocol-scope benchmark.** The only item that blocks the headline claim
   *and* `.lxdb`. Environmental, not analytical: the 1.054 GiB snapshot, a second machine class,
   the `xz` CLI row, the `ppmd-7z` row (settles OQ-18), then owner sign-off. ~2 GB disk, 6–8 h.
2. **P1 — `.lxdb`** (ADR-0013, Proposed) — gated on P0 by owner decision. Do not start it first.
3. **P3.5** — the cleaning-error rate (REQ-CAN-007, ADR-0004) operationalised; header/footer dedup
   (CAN-R10) needs it before code.
4. **P3.8** — the `doc_grams` table costs ~5× the stored payload; a packed-hash form, or the ratio
   carried into BENCHMARK_RESULTS as a stated cost of queryability.
5. **P2.4** — `[gui]` extra notices (NOTICE + LGPL/GPL texts + About view).
6. **P4.3** — second machine class at 4 GiB with the index in RAM. **P4.4** — `pyside6<6.12` is a
   workaround for a Bus error at Qt teardown, not a preference.
7. **P6 — release (M7):** versioned package, release-process dry run, "Unreleased" emptied at cut.

## Who does what

**Work that can be done in a working session, without you** (in rough order of value per hour):

| # | Task | Done when |
|---|---|---|
| A1 | **P3.5** — build the labelled sample and measure the cleaning-error rate | A report with the ADR-0004 metric, a point estimate and a bootstrap upper bound |
| A2 | **P3.8** — packed-hash `doc_grams` | Grams cost ≤1× the stored payload at equal recall, differential test still green |
| A3 | **P2.4** — GUI notices | NOTICE + LGPL/GPL texts in the About view, asserted by a test |
| A4 | **P4.4** — re-test `pyside6>=6.12` | The GUI suite exits 0, not just passes |
| A5 | **P5.1 / P5.2** — the Session-69→70 hole; the contribution-licensing line in CONTRIBUTING | Both closed |
| A6 | **A drift guard** — a test that reads the milestone table and fails when a row claims a capability whose test file is missing | The three drifts found on 2026-11-23 would each have failed it |

**Work only you can do** — [PATH_TO_V1](PATH_TO_V1.md) §3 P7, because it needs your hardware,
your verdict or your name:

| # | Item | Why it cannot be delegated |
|---|---|---|
| P7.1 | **Run P0** on a machine with ~2 GB disk, `xz`, 6–8 h | The corpus run has to happen where the corpus is; no container here can host it |
| P7.2 | **Sign off the R5/G2 revision** | RELEASE_PROCESS and ADR-0001 make your verdict the gate |
| P7.3 | **OQ-18** — `7z` binary plugin, PPMd inside ziptastic, or drop the preset | A codec-policy decision; it changes what "max-ratio" means |
| P7.4 | **OCR language scope** — English only, + `chi_sim`, or + Hindi/Gujarati | Product scope, and it decides what the accuracy sample contains |
| P7.5 | **Commercial licensing** — PolyForm Noncommercial has no paid track today | A licence decision, ADR-0009 territory, your name on the file |
| P7.6 | **PyPI, or source-only installs** | A release action; nothing is published today |
| P7.7 | **Review documentation Batches D–E** | "Pending owner review" since Session 11 |
| P7.8 | **Rotate the GitHub token shared in chat** (Sessions 36/37) | Only you can revoke it |

## Open decisions

- **OQ-18** — PPMd as max-ratio preset. Blocked on a working implementation: `pyppmd`/`py7zr`
  corrupt 3–8 % of real files (ADR-0021 withdrawal). Candidates: the `7z` binary as an external
  plugin, or PPMd inside ziptastic.
- **OCR language scope** — English only, English + Chinese, or add Hindi/Gujarati.

## Standing rules that are easy to lose

- **Verify before claiming.** Four sessions running have found a check that lied. Run the command,
  read the output, and prefer the check where you *see* the failure.
- **A number in prose is a claim.** The live count is the CI badge; a measured count lives in
  [STATUS.md](STATUS.md) next to its date. `tests/test_readme_claims.py` enforces the shape.
- **`--level` is a usage error (exit 2) when out of range** on every verb (ADR-0018).
- **PPMd is a baseline, not a codec** (ADR-0021 withdrawn). A test asserts it stays unregistered.
- **Plugins affect ingestion only; decoding never needs one** (ADR-0022).
- **English keeps the `lexcan-0.1` provenance label** deliberately — no archive is rewritten twice
  in a week.
- **The harness measures raw bytes; lexora packs canonical bytes.** A green baseline row is not
  proof the codec path is sound.
- **No format bytes before the gate** — `.lxdb` waits for G2, exactly as `.lxz` waited for ADR-0007.
