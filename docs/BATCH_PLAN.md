# Batch plan — 2026-11-08

> **Status:** Active. This is the **execution order**; [PATH_TO_V1.md](PATH_TO_V1.md) remains the
> scope of record (what v1.0 means, what is deliberately out). Where they disagree, PATH_TO_V1
> wins on *scope* and this file wins on *order*.
> **Why batching:** the remaining work is uneven — several items take under an hour and are
> user-visible, while the two big ones need hardware I do not have. Doing them in dependency
> order would mean starting with the thing that cannot be started, so they are grouped by
> *cost and risk* instead: cheap and certain first, small items combined, large ones last.
> **Audited:** 2026-11-08, `main` at `e37a6e7`, gate **672 passed, 0 skipped**, CI green.

## 1. Current state (verified, not remembered)

| | |
|---|---|
| Gate | **672 passed, 0 skipped** — `PYTHONPATH=src:. python3 -m pytest -q` with PySide6 + the ziptastic binary present |
| CI on `main` | green (last three runs: success) |
| Open PRs / issues | none |
| Code | 5,915 lines in `src/` across 12 modules; 6,013 lines of tests |
| Decisions | 20 ADRs; OQ-10 and OQ-16 closed; F1 (`codec_id` naming) still open |
| CLI surface | **11 verbs**: `batch canon db doctor inspect pack pipe unpack verify zdecode zround` |
| Features shipped | canonicalisation, `.lxz` container, two codecs, queryable archive (`lexora db`), PDF text layer, OCR as an external plugin, GUI query view, GUI on the CLI |
| Not started | protocol-scope benchmark (P0), `.lxdb` (P1), release (P6), 4 GiB resource test (P4.3) |

**What the audit looked for, in priority order** (correctness → security → performance → design),
and what it found — every line verified by running the command, not by reading a doc:

| # | Sev | Finding | Evidence |
|---|---|---|---|
| F1 | **Medium** | **The front page does not mention the query archive at all**, and claims "nine subcommands" when there are eleven. `lexora db` is the headline feature of the last three sessions and is invisible to a new reader. | `README.md:107`; `grep -c "lexora db" README.md` → **0**; `docs/index.html` → **0** |
| F2 | Low | **`cmd_zdecode` is defined twice** in the CLI. Identical bodies, so no behaviour change — the second silently shadows the first. Nothing caught it because both are the same function. | `src/lexora/cli.py:266` and `:335` (ruff `F811`) |
| F3 | Low | **Seven unused imports**, mostly leftovers from the subprocess refactor — `service.py` still imports `canonicalize`, `unpack`, `compress`, `decompress` that it no longer calls. | `gui/service.py:37,39,40`; `container.py:41`; `gui/app.py:25`; `gui/crash.py:27` (ruff `F401`) |
| F4 | Low | `ocr_core.py` imports `PIL.Image` purely as an availability probe, which reads as a real dependency. | `ocr_core.py:179` |
| F5 | Info | SQL flagged as possible injection. **It is safe today** — the `IN` clause is built from `?` placeholders and the metadata key is validated — but the guard is `key.replace("_","").isalnum()`, and `isalnum()` accepts Unicode letters. | `catalog.py:443-457` |
| F6 | Info | Eight `raise` statements inside `except` without `from`, so the cause chain is lost in tracebacks. | `cli.py` ×8 (ruff `B904`) |

**And the things that came back clean**, which matter as much: no bare `except:`, no
`shell=True` / `os.system` / `eval`, **every** `subprocess.run` carries a timeout (4 call sites,
verified individually), no `TODO`/`FIXME`/`XXX`/`HACK` anywhere in `src/`, and no open security
finding above "Info".

---

## 2. Batch 0 — needs you, and blocks the rest

Nothing in batches 1–2 depends on these; batches 3–4 do.

| Item | What you do | Why it blocks |
|---|---|---|
| **P0 — the protocol benchmark** | A machine with ~2 GB disk + `xz`, then the corpus fetch and three split runs (~6–8 h). Commands in [PATH_TO_V1 §P0](PATH_TO_V1.md). | The "20 % smaller than `xz`" claim stays *smoke* until this runs, and `.lxdb` is gated behind it by your own decision |
| **OCR language scope** | Decide: English only, English + Chinese (your scan needs `chi_sim`), or add Hindi/Gujarati per the charter | Sets the default `--lang` and the fixtures |
| **F1 — `codec_id` naming** | One line: rename now, or at v0→v1? [ADR-0020](ADR/ADR-0020-codec-id-naming.md) is written and the mechanism decided; only the *when* is open (OQ-17). Recommendation: **now** | Blocks Batch 2's first item |
| **A 4 GiB box** (optional) | Any machine with 4 GiB RAM | P4.3, the only resource claim not yet tested on target hardware |

## 3. Batch 1 — quick wins, one PR, no decisions (~1–2 hours)

Cheap, certain, and mostly **user-visible**, which is why it goes first: the repository's front
door currently undersells what exists.

| # | Item | Verification |
|---|---|---|
| 1 | Delete the duplicate `cmd_zdecode` (F2) | `grep -c "def cmd_zdecode"` → 1 |
| 2 | `ruff --fix` the unused imports (F3); replace the `PIL.Image` probe with `importlib.util.find_spec` (F4) | `ruff check src/ --select F401` → clean |
| 3 | **Front page: nine → eleven verbs, and a `lexora db` example** (F1) | `grep -c "lexora db" README.md` → > 0 |
| 4 | **Landing page: add the query archive** (F1/F7) | `grep -c "lexora db" docs/index.html` → > 0 |
| 5 | Tighten the metadata filter guard to ASCII word chars (F5) | existing `test_filter_key_is_validated` + a Unicode key case |
| 6 | `B904` sweep — add `from exc` / `from None` (F6) | `ruff check src/ --select B904` → clean |
| 7 | **New test: the documented verb count matches the CLI's** | fails today, passes after item 3 |

Item 7 is the point of the batch: F1 happened because a *number in prose* had nothing checking
it. The same class of drift has now bitten this repo three times (test counts, level defaults,
subcommand counts), and a test costs ten lines.

**Risk:** low. No behaviour changes except the filter guard (stricter) and error chaining
(better tracebacks). Nothing touches the format, the codecs or the archive bytes.

## 4. Batch 2 — small items combined (~half a day)

Grouped because each is too small to justify its own PR, and they share one theme: *make the
things we already claim true.*

| # | Item | Depends on |
|---|---|---|
| 1 | **F1 implementation** — reader accepts both `zstd-raw-l19` and the new level-neutral id; writer emits the new one; migration note; golden vectors regenerated | Batch 0's F1 decision |
| ~~2~~ | ~~Resource-limit harness (P4.3 prep)~~ | **DONE 2026-11-08** — `benchmarks/index_rss_probe.py` measures the query path (index resident + one document) with `--cap-mib` as a pass/fail gate; first numbers in `results-rss-index.json`. Still open: the run on a real 4 GiB box at scale |
| 3 | `lexora db` quickstart in the README's "try this" block, and the GUI's first-run guidance pointing at `db init` | Batch 1 item 3 |
| 4 | OCR: document `--lang` combinations and the mixed-script caveat in `QUERY_ARCHIVE.md` (the ADR says it; the guide should too) | — |

## 5. Batch 3 — medium, one at a time (1–2 days each)

| # | Item | Why it is not in Batch 2 |
|---|---|---|
| 1 | OCR quality pass: real Tesseract, a human-checked sample of 3 pages, then the accuracy note in ADR-0019 loses its "unproven" caveat | Needs the binary and your eyes |
| 2 | Header/footer dedup as a **canonicalisation rule** (CAN-R10) for boilerplate stamps — the supplied scan repeats one line 99 times | A cleaning rule needs the ADR-0004 error metric, not just code |
| 3 | Encryption profile (ADR-0009 left it Proposed) | Touches the format; needs its own ADR before code |

## 6. Batch 4 — large, needs hardware (days, and a machine)

| # | Item | Gate |
|---|---|---|
| 1 | **P0** protocol-scope benchmark → publish R7 | Batch 0 |
| 2 | **P1** `.lxdb` per ADR-0013 (single file, embedded compressed index, commit-by-superblock-flip, crash injection) | P0, because you chose to respect the gate |
| 3 | **P6** release v1.0 — version, release dry-run, CHANGELOG cut | P1 |

---

## 7. Sequencing rules

1. **Batch 1 before everything.** It is cheap, it is user-facing, and item 7 stops a drift class
   that has recurred three times.
2. **Batches 2 and 3 are independent of each other** and of Batch 4; run them in whatever order
   the owner's attention allows.
3. **Batch 4 never starts before Batch 0's benchmark**, by the owner's explicit decision of
   2026-11-07 — not by preference.
4. **A batch ships as one PR** with the gate run and its output read. A batch that is
   "mostly done" is not done; partial work stays on its branch.
