# LEXORA Documentation Portal

> **Status:** Active (Batches A–E — governance, architecture, engineering, security/operations, GitHub & release polish)
> **Owner:** Unassigned
> **Last verified:** 2026-10-17 (reconciled with Session 37+ state: CLI app + `.lxz` v0 container landed, GUI milestones M1–M3 landed experimentally, benchmark revisions R1+R2 published, PolyForm Noncommercial 1.0.0 license per ADR-0009, superseding ADR-0006's MIT)

LEXORA = **L**ayered **EX**act-text **O**ptimized... see [PROJECT_CHARTER.md](PROJECT_CHARTER.md) for the authoritative definition and full naming. Core idea: clean text conservatively → canonical UTF-8 bytes → compress with byte-exact recovery.

## Start here

| If you are… | Read… |
|---|---|
| Visiting for the first time | [../README.md](../README.md) |
| Resuming work after a break | [NEXT_SESSION.md](NEXT_SESSION.md), then [STATUS.md](STATUS.md) |
| Looking for what is real vs. planned | [STATUS.md](STATUS.md) and the maturity table in the README |
| Wanting the approved design rationale | [../LEXORA_Full_Blueprint_Design_Master_Prompt.md](../LEXORA_Full_Blueprint_Design_Master_Prompt.md) |

## Users

The Phase-1 CLI exists and is tested (`canon`, `zround`, `pipe`, `pack`, `unpack` — `.lxz` v0 per accepted ADR-0007): see [CLI_REFERENCE.md](CLI_REFERENCE.md) — it documents only implemented commands and their real exit codes. A desktop GUI exists in experimental milestones M1–M3 (window shell, async job runner, panels, settings persistence, pickers/crash diagnostics — landed Sessions 27–34, offscreen-tested; not yet released): see [DESIGN_GUI.md](DESIGN_GUI.md) and [GUI_SCREENSHOTS.md](GUI_SCREENSHOTS.md). Still not written:

- `USER_GUIDE.md` — not yet written (planned, Batch C)
- [INSTALLATION.md](INSTALLATION.md) / [BUILD_GUIDE.md](BUILD_GUIDE.md) — exist as drafts; the editable install itself is verified (see [P1_EVIDENCE_DRAFT.md](P1_EVIDENCE_DRAFT.md)) but the docs' full instructions await owner review
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) — Batch D draft (symptom map for the designed system; partially superseded by the shipped exit-code table in [CLI_REFERENCE.md](CLI_REFERENCE.md))

## Developers

- `DEVELOPMENT_SETUP.md` — Batch C draft; Python range resolved by [ADR-0005](ADR/ADR-0005-python-version.md) (`>=3.12,<4.0`; OQ-7 closed Session 12)
- [PRODUCT_REQUIREMENTS.md](PRODUCT_REQUIREMENTS.md) — numbered requirements (`REQ-*`)
- [GLOSSARY.md](GLOSSARY.md) — terminology used across all docs
- [QUALITY_PLAN.md](QUALITY_PLAN.md) — Batch C draft; `TESTING_GUIDE.md` not yet written (deferred to when test tooling exists)

## Architecture & specification

- [DEPENDENCY_LICENCE_REVIEW.md](DEPENDENCY_LICENCE_REVIEW.md) — third-party licence obligations for the GUI extra (PySide6/Qt under PolyForm Noncommercial); **review awaiting an owner decision** (proposed ADR-0010)


- [PROJECT_CHARTER.md](PROJECT_CHARTER.md) — problem, goals, constraints, non-goals
- [MASTER_BLUEPRINT.md](MASTER_BLUEPRINT.md) — distilled architecture view (source-of-truth remains the root blueprint file)
- [SPECIFICATION.md](SPECIFICATION.md) — `LEXORA-SPEC-1.0-draft`, normative but **not approved** (blocked on ADRs 0001–0004 + rule-table freeze)
- [CANONICALIZATION.md](CANONICALIZATION.md) — rule table draft; **not frozen**
- [COMPRESSION_ARCHITECTURE.md](COMPRESSION_ARCHITECTURE.md) — Core Zstd baseline + experimental candidates (none shipping)
- [COST_MODEL.md](COST_MODEL.md) — total serialized-byte accounting rules
- [TOKENIZER_SPEC.md](TOKENIZER_SPEC.md) — candidate-layer tokenizer v0 draft
- [OCR_PIPELINE.md](OCR_PIPELINE.md) — optional OCR flow and failure semantics
- [FORMAT_LXZ.md](FORMAT_LXZ.md) — ⚠️ v0 EXPERIMENTAL — byte layout frozen by accepted ADR-0007; implemented in `src/lexora/container.py`; pre-release, not a stable format
- [FORMAT_LXDB.md](FORMAT_LXDB.md) — ⚠️ DEFERRED, not designed
- Diagrams: [pipeline](diagrams/pipeline.mmd) · [system context](diagrams/system-context.mmd) · [session resume](diagrams/session-resume.mmd)

## Testing & benchmarks

- [TEST_STRATEGY.md](TEST_STRATEGY.md), [BENCHMARK_PROTOCOL.md](BENCHMARK_PROTOCOL.md), [CORPUS_POLICY.md](CORPUS_POLICY.md) — Batch C drafts
- [BENCHMARK_RESULTS.md](BENCHMARK_RESULTS.md) — active register; **two smoke-scope revisions published (R1 + R2, tier T1-gutenberg-p0)** — baseline-vs-baseline numbers only (Zstd-19 vs XZ-9), **no LEXORA-vs-baseline results and no ADR-0001 verdict exist**. Any number outside a published revision or without its tier label is invalid. Draft closure evidence lives separately in [P1_EVIDENCE_DRAFT.md](P1_EVIDENCE_DRAFT.md) (awaiting owner verdict).

## Security & privacy

- Root [SECURITY.md](../SECURITY.md) — reporting process only; **no security guarantees claimed** (nothing implemented).
- [SECURITY_ARCHITECTURE.md](SECURITY_ARCHITECTURE.md) — trust boundaries, asset inventory, REQ-SEC mechanism map (design intent).
- [THREAT_MODEL.md](THREAT_MODEL.md) — attacker profiles + threat register TM-01…TM-13.
- [PRIVACY_AND_DATA_HANDLING.md](PRIVACY_AND_DATA_HANDLING.md) — P0–P3 classification tiers, dictionary-leakage policy, incident handling.
- [ENCRYPTION_PROFILE.md](ENCRYPTION_PROFILE.md) — ⚠️ PROPOSED, out of current scope (Phase 9 gate; no cipher decided).

## Operations & troubleshooting

- [ERROR_HANDLING.md](ERROR_HANDLING.md) — error taxonomy E-*, severities, fail-closed contract (proposed codes).
- [LOGGING_AND_DIAGNOSTICS.md](LOGGING_AND_DIAGNOSTICS.md) — levels, privacy-safe log rules, run-manifest format.
- [RESOURCE_LIMITS.md](RESOURCE_LIMITS.md) — LIM-* candidate ceilings (Batch C draft, pending format freeze).
- Runbooks: [BENCHMARK_RUNBOOK.md](runbooks/BENCHMARK_RUNBOOK.md) · [CORRUPTION_TRIAGE.md](runbooks/CORRUPTION_TRIAGE.md) · [PERFORMANCE_TRIAGE.md](runbooks/PERFORMANCE_TRIAGE.md) · [RECOVERY_RUNBOOK.md](runbooks/RECOVERY_RUNBOOK.md)
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) — symptom→cause→action index.

## Project management & resumability

- [STATUS.md](STATUS.md) — current verified state
- [PROGRESS.md](PROGRESS.md) — phase-by-phase completion
- [SESSION_LOG.md](SESSION_LOG.md) — append-only dated session history
- [NEXT_SESSION.md](NEXT_SESSION.md) — resume card
- [ROADMAP.md](ROADMAP.md), [PHASES.md](PHASES.md), [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md), [IMPLEMENTATION_MATRIX.md](IMPLEMENTATION_MATRIX.md), [REQUIREMENTS_TRACEABILITY.md](REQUIREMENTS_TRACEABILITY.md) — Batch C drafts

## Decisions & history

- [DECISIONS.md](DECISIONS.md) — index of ADRs and open decisions
- [ADR/](ADR/) — decision records: [ADR-0001 gate scope](ADR/ADR-0001-gate-scope.md) · [ADR-0002 Brotli role](ADR/ADR-0002-brotli-role.md) · [ADR-0003 PPMd role](ADR/ADR-0003-ppmd-role.md) · [ADR-0004 cleaning metric](ADR/ADR-0004-cleaning-error-metric.md) · [ADR-0005 Python version](ADR/ADR-0005-python-version.md) · [ADR-0006 license = MIT (superseded)](ADR/ADR-0006-license-mit.md) · [ADR-0007 `.lxz` v0 container freeze](ADR/ADR-0007-container-v0-freeze.md) · [ADR-0008 GUI toolkit/architecture](ADR/ADR-0008-gui-toolkit-architecture.md) · [ADR-0009 PolyForm Noncommercial license](ADR/ADR-0009-license-polyform-noncommercial.md) — all **Accepted** (2026-10-15…29, owner delegation / owner decision; see DECISIONS.md note); [template](templates/ADR_TEMPLATE.md)
- [../CHANGELOG.md](../CHANGELOG.md) — change history
- [templates/](templates/) — reusable document templates ([session note](templates/SESSION_NOTE_TEMPLATE.md), [ADR](templates/ADR_TEMPLATE.md))

## Contributing & releases *(Batch E)*

- [../CONTRIBUTING.md](../CONTRIBUTING.md) — ground rules (honesty policy), current workflow, branching & PR guidance
- [.github/pull_request_template.md](../.github/pull_request_template.md) — required PR checklist (verification actually run, decisions affected)
- Issue templates: [design proposal](../.github/ISSUE_TEMPLATE/design-proposal.yml) · [documentation error report](../.github/ISSUE_TEMPLATE/documentation.yml)
- [RELEASE_PROCESS.md](RELEASE_PROCESS.md) — release preconditions, proposed versioning scheme (OQ-9 pending), rollback policy; **no releases or tags exist yet**

---

### Document status legend

| Label | Meaning |
|---|---|
| *(link)* | Exists and reflects verified reality |
| *planned, Batch X* | Intentionally not created yet — creating empty placeholders is prohibited |
