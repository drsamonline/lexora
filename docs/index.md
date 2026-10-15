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
- `MASTER_BLUEPRINT.md` — *planned, Batch B* (distilled view of the root blueprint file, which remains source of truth)
- `SPECIFICATION.md` (`LEXORA-SPEC-1.0-draft`) — *planned, Batch B* (normative)
- `COMPRESSION_ARCHITECTURE.md`, `CANONICALIZATION.md`, `TOKENIZER_SPEC.md`, `COST_MODEL.md`, `FORMAT_LXZ.md`, `FORMAT_LXDB.md` — *planned, Batch B*

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

- [DECISIONS.md](DECISIONS.md) — index of ADRs and open decisions (including four known blueprint conflicts pending resolution)
- `ADR/` — architecture decision records ([template](ADR/ADR-0001-template.md)); none accepted yet
- [../CHANGELOG.md](../CHANGELOG.md) — change history
- [templates/](templates/) — reusable document templates ([session note](templates/SESSION_NOTE_TEMPLATE.md), [ADR](templates/ADR_TEMPLATE.md))

---

### Document status legend

| Label | Meaning |
|---|---|
| *(link)* | Exists and reflects verified reality |
| *planned, Batch X* | Intentionally not created yet — creating empty placeholders is prohibited |
