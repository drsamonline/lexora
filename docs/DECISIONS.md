# LEXORA Decisions Index (ADRs & Open Questions)

> **Status:** Active
> **Owner:** Unassigned
> **Last verified:** 2026-10-15 (commit `816f58f`)
> **Related:** [ADR template](ADR/ADR-0001-template.md) · [Blueprint](../LEXORA_Full_Blueprint_Design_Master_Prompt.md)

This is an **index**, not a substitute for full ADRs. Material decisions require a numbered ADR file in [`ADR/`](ADR/).

## Accepted ADRs

*None yet.* No ADR has been accepted by the project owner.

## Proposed ADRs (drafted 2026-10-15, Batch B — awaiting owner accept/amend/reject)

| ADR | Resolves | Recommended resolution (pending approval) |
|---|---|---|
| [ADR-0001 — Gate scope](ADR/ADR-0001-gate-scope.md) | OQ-1 | Two gates: per-category promotion ≥10% (validation + reproduced on held-out); corpus verdict Pass ≥10% / Partial ≥3% / Fail <3% |
| [ADR-0002 — Brotli role](ADR/ADR-0002-brotli-role.md) | OQ-2 | Brotli q11 = frozen measurement baseline only; never a selectable archive codec |
| [ADR-0003 — PPMd role](ADR/ADR-0003-ppmd-role.md) | OQ-3 | PPMd = measurement-only baseline; excluded from shipping codec registry |
| [ADR-0004 — Cleaning error metric](ADR/ADR-0004-cleaning-error-metric.md) | OQ-4 | Rule-audit metric on stratified seeded sample (≤1% point estimate, ≤2% bootstrap upper bound) + 100% automated invariant checks |

To approve: reply e.g. "accept ADR-0001" (or amend). On acceptance, flip the ADR status, move its row above to Accepted, and unblock the corresponding SPECIFICATION.md sections.

## Open questions requiring project-owner input

| ID | Question | Background / conflict evidence | Blocking? |
|---|---|---|---|
| **OQ-1** | Scope of the ≥10% Pass gate: per-file codec promotion (blueprint §10) vs. whole-corpus benchmark verdict (§12)? | Blueprint lists a "≥10% improvement" rule in both contexts with different granularity. Needs one normative reading + one advisory reading. | Yes — before SPECIFICATION.md freeze (Batch B) |
| **OQ-2** | Is Brotli a *frozen comparison baseline*, an *optional candidate codec*, or both? | Blueprint §8 treats Core as Zstd; §9 lists alternatives incl. Brotli; §12 lists four baselines (Zstd-19, Brotli q11, XZ, PPMd). Roles must be distinct and documented. | Yes — before benchmark protocol (Batch C) |
| **OQ-3** | Is PPMd a frozen baseline despite being described as unsuitable as primary codec on low-RAM targets? | §11 caveat vs. §12 baseline list. Likely resolution: baseline for measurement only, never a shipping default. | Yes — before benchmark protocol |
| **OQ-4** | How is the "≤1% cleaning error rate" measured? Definition, dataset, metric, and tolerance are unspecified. | §3 goal statement lacks an operational definition; REQ-CAN-007 currently blocked. | Yes — before Phase 0 exit |
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
