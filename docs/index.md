# LEXORA Documentation Portal

> **Status:** Active (Batch A — governance & navigation)
> **Owner:** Unassigned
> **Last verified:** 2026-10-15 (commit `816f58f`)

LEXORA = **L**ayered **EX**act-text **O**ptimized... see [PROJECT_CHARTER.md](PROJECT_CHARTER.md) for the authoritative definition and full naming. Core idea: clean text conservatively → canonical UTF-8 bytes → compress with byte-exact recovery.

## Start here

| If you are… | Read… |
|---|---|
| Visiting for the first time | [../README.md](../README.md) |
| Resuming work after a break | [NEXT_SESSION.md](NEXT_SESSION.md), then [STATUS.md](STATUS.md) |
| Looking for what is real vs. planned | [STATUS.md](STATUS.md) and the maturity table in the README |
| Wanting the approved design rationale | [../LEXORA_Full_Blueprint_Design_Master_Prompt.md](../LEXORA_Full_Blueprint_Design_Master_Prompt.md) |

## Users

*No user-facing functionality exists yet.* These documents will be created when commands actually exist:

- `USER_GUIDE.md` — not yet written (planned, Batch C)
- `CLI_REFERENCE.md` — not yet written (planned; must document only implemented commands)
- `INSTALLATION.md` / `BUILD_GUIDE.md` — not yet written (no build tooling exists)
- `TROUBLESHOOTING.md` — not yet written (Batch D)

## Developers

- `DEVELOPMENT_SETUP.md` — *planned, Batch C* (not yet created; Python version itself is an open decision — see [DECISIONS.md](DECISIONS.md) OQ-7)
- [PRODUCT_REQUIREMENTS.md](PRODUCT_REQUIREMENTS.md) — numbered requirements (`REQ-*`)
- [GLOSSARY.md](GLOSSARY.md) — terminology used across all docs
- `TESTING_GUIDE.md`, `QUALITY_PLAN.md` — *planned, Batch C*

## Architecture & specification

- [PROJECT_CHARTER.md](PROJECT_CHARTER.md) — problem, goals, constraints, non-goals
- [MASTER_BLUEPRINT.md](MASTER_BLUEPRINT.md) — distilled architecture view (source-of-truth remains the root blueprint file)
- [SPECIFICATION.md](SPECIFICATION.md) — `LEXORA-SPEC-1.0-draft`, normative but **not approved** (blocked on ADRs 0001–0004 + rule-table freeze)
- [CANONICALIZATION.md](CANONICALIZATION.md) — rule table draft; **not frozen**
- [COMPRESSION_ARCHITECTURE.md](COMPRESSION_ARCHITECTURE.md) — Core Zstd baseline + experimental candidates (none shipping)
- [COST_MODEL.md](COST_MODEL.md) — total serialized-byte accounting rules
- [TOKENIZER_SPEC.md](TOKENIZER_SPEC.md) — candidate-layer tokenizer v0 draft
- [OCR_PIPELINE.md](OCR_PIPELINE.md) — optional OCR flow and failure semantics
- [FORMAT_LXZ.md](FORMAT_LXZ.md) — ⚠️ PROPOSED, not a stable format
- [FORMAT_LXDB.md](FORMAT_LXDB.md) — ⚠️ DEFERRED, not designed
- Diagrams: [pipeline](diagrams/pipeline.mmd) · [system context](diagrams/system-context.mmd) · [session resume](diagrams/session-resume.mmd)

## Testing & benchmarks

- `TEST_STRATEGY.md`, `BENCHMARK_PROTOCOL.md`, `CORPUS_POLICY.md` — *planned, Batch C*
- `BENCHMARK_RESULTS.md` — *planned, Batch C*. **No validated benchmark results exist.** Any numbers appearing anywhere before a frozen-protocol run are invalid.

## Security & privacy

- `SECURITY.md`, `SECURITY_ARCHITECTURE.md`, `THREAT_MODEL.md`, `PRIVACY_AND_DATA_HANDLING.md`, `ENCRYPTION_PROFILE.md` — *planned, Batch D*. No security guarantees are currently claimed.

## Operations & troubleshooting

- `ERROR_HANDLING.md`, `LOGGING_AND_DIAGNOSTICS.md`, `RESOURCE_LIMITS.md`, `runbooks/*` — *planned, Batch D*

## Project management & resumability

- [STATUS.md](STATUS.md) — current verified state
- [PROGRESS.md](PROGRESS.md) — phase-by-phase completion
- [SESSION_LOG.md](SESSION_LOG.md) — append-only dated session history
- [NEXT_SESSION.md](NEXT_SESSION.md) — resume card
- `ROADMAP.md`, `PHASES.md`, `IMPLEMENTATION_PLAN.md`, `IMPLEMENTATION_MATRIX.md`, `REQUIREMENTS_TRACEABILITY.md` — *planned, Batch C*

## Decisions & history

- [DECISIONS.md](DECISIONS.md) — index of ADRs and open decisions
- [ADR/](ADR/) — decision records: [ADR-0001 gate scope](ADR/ADR-0001-gate-scope.md) · [ADR-0002 Brotli role](ADR/ADR-0002-brotli-role.md) · [ADR-0003 PPMd role](ADR/ADR-0003-ppmd-role.md) · [ADR-0004 cleaning metric](ADR/ADR-0004-cleaning-error-metric.md) — all **Proposed**, none accepted; [template](templates/ADR_TEMPLATE.md)
- [../CHANGELOG.md](../CHANGELOG.md) — change history
- [templates/](templates/) — reusable document templates ([session note](templates/SESSION_NOTE_TEMPLATE.md), [ADR](templates/ADR_TEMPLATE.md))

---

### Document status legend

| Label | Meaning |
|---|---|
| *(link)* | Exists and reflects verified reality |
| *planned, Batch X* | Intentionally not created yet — creating empty placeholders is prohibited |
