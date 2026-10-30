# LEXORA Decisions Index (ADRs & Open Questions)

> **Status:** Active
> **Owner:** Unassigned
> **Last verified:** 2026-10-29 (Session 68 reconciliation: ADR register completed — 0007, 0008, 0010, 0011, 0012 were missing from the table; OQ-8 updated to "size met")
> **Related:** [ADR template](ADR/ADR-0001-template.md) · [Blueprint](../LEXORA_Full_Blueprint_Design_Master_Prompt.md)

This is an **index**, not a substitute for full ADRs. Material decisions require a numbered ADR file in [`ADR/`](ADR/).

## Accepted ADRs

| ADR | Resolves | Decision | Accepted |
|---|---|---|---|
| [ADR-0001 — Gate scope](ADR/ADR-0001-gate-scope.md) | OQ-1 | Two gates: per-category promotion ≥10% (validation + reproduced on held-out); corpus verdict Pass ≥10% / Partial ≥3% / Fail <3% | 2026-10-15, by documentation-architect delegation (owner directive "decide ADRs yourself"). Revocable by owner. |
| [ADR-0002 — Brotli role](ADR/ADR-0002-brotli-role.md) | OQ-2 | Brotli q11 = frozen measurement baseline only; never a selectable archive codec | 2026-10-15, same delegation. Revocable by owner. |
| [ADR-0003 — PPMd role](ADR/ADR-0003-ppmd-role.md) | OQ-3 | PPMd = measurement-only baseline; excluded from shipping codec registry | 2026-10-15, same delegation. Revocable by owner. |
| [ADR-0004 — Cleaning error metric](ADR/ADR-0004-cleaning-error-metric.md) | OQ-4 | Rule-audit metric on stratified seeded sample (≤1% point estimate, ≤2% bootstrap upper bound) + 100% automated invariant checks | 2026-10-15, same delegation. Revocable by owner. |
| [ADR-0005 — Python version](ADR/ADR-0005-python-version.md) | OQ-7 | Supported range `>=3.12,<4.0`, matching the only verified environment; widen only with test evidence | 2026-10-15, same delegation. Revocable by owner. |
| [ADR-0007 — `.lxz` v0 freeze](ADR/ADR-0007-container-v0-freeze.md) | OQ-11 | Frozen LXZ-0.1 byte layout: 128 B header (full SHA-256), one complete zstd frame per block, 56 B index entries, 40 B trailer; two amendments recorded at acceptance | 2026-10-16, Session 24 |
| [ADR-0008 — GUI toolkit & architecture](ADR/ADR-0008-gui-toolkit-architecture.md) | OQ-12 / OQ-13 | PySide6 via a `[gui]` extra in the same repo; Qt confined to function bodies so the core stays Qt-free. **Partly superseded by ADR-0011** (in-process service layer → CLI client) | 2026-10-17, Session 26 |
| [ADR-0010 — `.lxdb` direction](ADR/ADR-0010-lxdb-direction.md) | FORMAT_LXDB gates | `.lxdb` v0 = a container of `.lxz` members; block-pool design named as successor with a measurement-based trigger; **no byte layout** until the corpus gate closes | 2026-10-29, Session 53 |
| [ADR-0011 — GUI process separation](ADR/ADR-0011-gui-process-separation.md) | ADR-0009 §3 (LGPL) | The GUI is a **client of the CLI**, not an in-process library consumer: answers the LGPL question structurally, isolates Qt crashes, and is testable without Qt | 2026-10-29, Session 53 |
| [ADR-0012 — Default encode level](ADR/ADR-0012-default-encode-level.md) | Session 45 budget miss | `DEFAULT_LEVEL = 9` for library, CLI and GUI (one constant); level 19 stays available for archival. Fixes a real CLI/GUI disagreement (19 vs 3) | 2026-10-29, Session 53 |
| [ADR-0006 — License](ADR/ADR-0006-license-mit.md) | OQ-5 | ~~MIT~~ — **superseded by [ADR-0009](ADR/ADR-0009-license-polyform-noncommercial.md)** | 2026-10-15, Session 14, under standing delegation; superseded 2026-10-29 by explicit owner decision ("polyform") |
| [ADR-0009 — License](ADR/ADR-0009-license-polyform-noncommercial.md) | OQ-5 | **PolyForm Noncommercial 1.0.0**, © 2026 Dr. Sohil Momin; LICENSE at repo root (normative, incl. `Required Notice:`); SPDX `PolyForm-Noncommercial-1.0.0` in pyproject; source-available, not OSI-approved | 2026-10-29, Session 40, explicit owner decision after the licence contradiction was recorded in SESSION_LOG S39 |

**Delegation note:** ADR-0001…0004 were drafted in Batch B with recommended options and approved verbatim (Option C / B / B / B respectively) under the project owner's explicit 2026-10-15 instruction to decide ADRs autonomously. ADR-0005 (Session 12) and ADR-0006 (Session 14) follow the same standing delegation; ADR-0006 was additionally prompted by the owner's explicit "start working on" instruction for OQ-5. This is *not* independent owner review — the owner may amend or revoke any of them at any time; changes require superseding ADRs per policy.

To override: open a decision item here and draft an amending/superseding ADR.

## Open questions requiring project-owner input

| ID | Question | Background / conflict evidence | Blocking? |
|---|---|---|---|
| ~~OQ-1~~ | ~~Scope of the ≥10% Pass gate~~ | **RESOLVED 2026-10-15 by [ADR-0001](ADR/ADR-0001-gate-scope.md)** (accepted via owner delegation). | No |
| ~~OQ-2~~ | ~~Brotli role~~ | **RESOLVED 2026-10-15 by [ADR-0002](ADR/ADR-0002-brotli-role.md)** (accepted via owner delegation). | No |
| ~~OQ-3~~ | ~~PPMd role~~ | **RESOLVED 2026-10-15 by [ADR-0003](ADR/ADR-0003-ppmd-role.md)** (accepted via owner delegation). | No |
| ~~OQ-4~~ | ~~Cleaning error-rate measurement~~ | **RESOLVED 2026-10-15 by [ADR-0004](ADR/ADR-0004-cleaning-error-metric.md)** (accepted via owner delegation). | No |
| ~~OQ-5~~ | ~~Project license.~~ | **RESOLVED — [ADR-0009](ADR/ADR-0009-license-polyform-noncommercial.md) (2026-10-29):** PolyForm Noncommercial 1.0.0, `LICENSE` at repo root, SPDX in pyproject. Supersedes [ADR-0006](ADR/ADR-0006-license-mit.md) (MIT). | No |
| ~~OQ-6~~ | ~~GitHub repository URL (`owner/repo`), visibility, and default branch.~~ | **RESOLVED by events (2026-10-30):** `https://github.com/drsamonline/lexora`, **public**, default branch **`main`**. Pushes, CI runs on `main`, and GitHub Pages at `drsamonline.github.io/lexora` all use it. |
| ~~OQ-7~~ | ~~Supported Python version range for the prototype.~~ | **RESOLVED 2026-10-15 by [ADR-0005](ADR/ADR-0005-python-version.md)** — `>=3.12,<4.0` (accepted via owner delegation). | No |
| **OQ-8** | Benchmark corpus: source, rights, privacy classification (clinical?), size ≥ 1 GiB, language mix. | **Size met 2026-10-29 (Session 67):** 2395 files / 1.054 GiB from Project Gutenberg (catalog-selected, P0 public domain), manifest `c92cf578…`, 0 problems, no lineage straddling. **Still open:** language mix (English-only per owner directive 2026-10-16; Hindi/Gujarati deferred), per-item rights verification via RDF, and a protocol-scope benchmark run. |
| ~~OQ-9~~ | ~~Adopt Conventional Commits + Keep-a-Changelog + SemVer for the repo?~~ | **RESOLVED in practice (2026-10-30):** every commit since Session 42 uses Conventional Commits (`feat`/`fix`/`docs`/`chore`/`bench`/`test`), `CHANGELOG.md` follows Keep-a-Changelog, and versions are PEP 440 dev versions (`0.0.1.dev1`). **SemVer tags are deliberately deferred** until the first release; that decision returns with the release question, not before. |
| **OQ-10** | OCR stack availability target (Tesseract version, Hindi/Gujarati traineddata) and whether it ships in docs/examples. | Optional dependency; offline constraint interacts with install guide. | Before ingestion phase |
| ~~OQ-11~~ | ~~Accept/amend/reject [ADR-0007](ADR/ADR-0007-container-v0-freeze.md): freeze a minimal `.lxz` v0 byte layout.~~ | **RESOLVED 2026-10-17:** owner explicitly delegated the decision ("DECIDE UR SELF"); ADR-0007 **accepted with recorded amendments** (see "Amendments applied at acceptance" in the ADR). Container + `pack`/`unpack` implemented against the amended layout; 96 tests passing. | No — container work unblocked and landed |
| ~~OQ-12~~ | ~~GUI toolkit: PySide6 (proposed) vs Tkinter fallback vs defer to GUI-M1 kickoff.~~ | **RESOLVED 2026-10-17 (Session 26)** under standing owner delegation ("DECIDE UR SELF"): **PySide6** via [ADR-0008](ADR/ADR-0008-gui-toolkit-architecture.md) (Accepted). Revocable by owner like all delegated ADRs. | No |
| ~~OQ-13~~ | ~~GUI packaging: same repo via `[gui]` extra (proposed) vs sibling repo.~~ | **RESOLVED 2026-10-17 (Session 26)** via [ADR-0008](ADR/ADR-0008-gui-toolkit-architecture.md): same repo, optional `[gui]` extra; core install stays Qt-free. | No |
| **OQ-14** | Should the GUI expose dictionary/trained-model compression post-P1, or stay format-minimal? | Provisionally answered in [ADR-0008](ADR/ADR-0008-gui-toolkit-architecture.md) decision 5: **format-minimal through GUI-M3**; revisit when dictionary compression actually lands in the library (nothing to expose today). Owner may override. | No |
| ~~OQ-15~~ | ~~GitHub Actions paused by owner (free-tier minutes exhausted, 2026-10-17).~~ | **RESOLVED (2026-10-30):** CI is running again and green on `main` — runs `41045077241` (503 passed) and `41104306951` (503 passed) both succeeded, and the workflow now pins `actions/checkout` v5 and `actions/setup-python` v6 after GitHub's Node-20 deprecation warning. The local gate remains `pytest -q` + `scripts/linkcheck.py` before every commit. |

## Decision rules (from master prompt §1.1)

1. Owner instruction > Accepted ADRs > Approved spec > Blueprint > Code/tests reality > Session notes > Drafts.
2. Conflicts affecting behavior/format/security/scope ⇒ stop, document here, propose ADR, ask owner.
3. Never silently pick an interpretation.

## How to add an ADR

1. Copy [`ADR/ADR-0001-template.md`](ADR/ADR-0001-template.md) to `ADR/ADR-NNNN-short-title.md`.
2. Fill context, options, decision, consequences. Status starts **Proposed**.
3. Add a row above; move to "Accepted" only on owner approval.
4. Update affected documents and the changelog in the same session.
