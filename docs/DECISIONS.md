# LEXORA Decisions Index (ADRs & Open Questions)

> **Status:** Active
> **Owner:** Unassigned
> **Last verified:** 2026-10-15 (commit `816f58f`)
> **Related:** [ADR template](ADR/ADR-0001-template.md) · [Blueprint](../LEXORA_Full_Blueprint_Design_Master_Prompt.md)

This is an **index**, not a substitute for full ADRs. Material decisions require a numbered ADR file in [`ADR/`](ADR/).

## Accepted ADRs

| ADR | Resolves | Decision | Accepted |
|---|---|---|---|
| [ADR-0001 — Gate scope](ADR/ADR-0001-gate-scope.md) | OQ-1 | Two gates: per-category promotion ≥10% (validation + reproduced on held-out); corpus verdict Pass ≥10% / Partial ≥3% / Fail <3% | 2026-10-15, by documentation-architect delegation (owner directive "decide ADRs yourself"). Revocable by owner. |
| [ADR-0002 — Brotli role](ADR/ADR-0002-brotli-role.md) | OQ-2 | Brotli q11 = frozen measurement baseline only; never a selectable archive codec | 2026-10-15, same delegation. Revocable by owner. |
| [ADR-0003 — PPMd role](ADR/ADR-0003-ppmd-role.md) | OQ-3 | PPMd = measurement-only baseline; excluded from shipping codec registry | 2026-10-15, same delegation. Revocable by owner. |
| [ADR-0004 — Cleaning error metric](ADR/ADR-0004-cleaning-error-metric.md) | OQ-4 | Rule-audit metric on stratified seeded sample (≤1% point estimate, ≤2% bootstrap upper bound) + 100% automated invariant checks | 2026-10-15, same delegation. Revocable by owner. |

**Delegation note:** These four ADRs were drafted in Batch B with recommended options and approved verbatim (Option C / B / B / B respectively) under the project owner's explicit 2026-10-15 instruction to decide ADRs autonomously. This is *not* independent owner review — the owner may amend or revoke any of them at any time; changes require superseding ADRs per policy.

To override: open a decision item here and draft an amending/superseding ADR.

## Open questions requiring project-owner input

| ID | Question | Background / conflict evidence | Blocking? |
|---|---|---|---|
| ~~OQ-1~~ | ~~Scope of the ≥10% Pass gate~~ | **RESOLVED 2026-10-15 by [ADR-0001](ADR/ADR-0001-gate-scope.md)** (accepted via owner delegation). | No |
| ~~OQ-2~~ | ~~Brotli role~~ | **RESOLVED 2026-10-15 by [ADR-0002](ADR/ADR-0002-brotli-role.md)** (accepted via owner delegation). | No |
| ~~OQ-3~~ | ~~PPMd role~~ | **RESOLVED 2026-10-15 by [ADR-0003](ADR/ADR-0003-ppmd-role.md)** (accepted via owner delegation). | No |
| ~~OQ-4~~ | ~~Cleaning error-rate measurement~~ | **RESOLVED 2026-10-15 by [ADR-0004](ADR/ADR-0004-cleaning-error-metric.md)** (accepted via owner delegation). | No |
| **OQ-5** | Project license. | No LICENSE file exists; README cannot show a license badge; legal reuse terms undefined. | Before any public release |
| **OQ-6** | GitHub repository URL (`owner/repo`), visibility, and default branch. | No git remote configured. Blocks badges, CI workflows, issue templates wiring. | Before Batch E |
| **OQ-7** | Supported Python version range for the prototype. | Blueprint says "Python-first" but pins nothing. Blocks dependency policy + CI matrix. | Before Phase 1 code |
| **OQ-8** | Benchmark corpus: source, rights, privacy classification (clinical?), size ≥ 1 GiB, language mix. | Nothing assembled; CORPUS_POLICY depends on this. | Before Phase 1 benchmarks |
| **OQ-9** | Adopt Conventional Commits + Keep-a-Changelog + SemVer for the repo? | CHANGELOG format chosen provisionally (Keep-a-Changelog); needs formal adoption via ADR. | Before first release |
| **OQ-10** | OCR stack availability target (Tesseract version, Hindi/Gujarati traineddata) and whether it ships in docs/examples. | Optional dependency; offline constraint interacts with install guide. | Before ingestion phase |

## Decision rules (from master prompt §1.1)

1. Owner instruction > Accepted ADRs > Approved spec > Blueprint > Code/tests reality > Session notes > Drafts.
2. Conflicts affecting behavior/format/security/scope ⇒ stop, document here, propose ADR, ask owner.
3. Never silently pick an interpretation.

## How to add an ADR

1. Copy [`ADR/ADR-0001-template.md`](ADR/ADR-0001-template.md) to `ADR/ADR-NNNN-short-title.md`.
2. Fill context, options, decision, consequences. Status starts **Proposed**.
3. Add a row above; move to "Accepted" only on owner approval.
4. Update affected documents and the changelog in the same session.
