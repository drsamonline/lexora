# LEXORA Requirements Traceability

> **Status:** Draft (chain template populated; Implementation/Test/Evidence stages empty because no code exists — verified 2026-10-15)
> **Owner:** Documentation architect (delegated)
> **Related:** [PRODUCT_REQUIREMENTS.md](PRODUCT_REQUIREMENTS.md) · [IMPLEMENTATION_MATRIX.md](IMPLEMENTATION_MATRIX.md) · [ACCEPTANCE_CRITERIA.md](ACCEPTANCE_CRITERIA.md) · [TEST_STRATEGY.md](TEST_STRATEGY.md)

## Purpose

For every mandatory requirement, trace the chain
`Requirement → Design → Implementation → Test → Evidence → Release gate`
and expose any missing link as a gap. Optional (S/N) requirements may use lighter verification but still need a named method.

## How to read the chain columns

- **Req** — ID from PRODUCT_REQUIREMENTS.md.
- **Design** — normative section that defines behavior.
- **Impl** — module/file with passing code (currently: none exist).
- **Test** — automated test or review procedure (IDs reserved in IMPLEMENTATION_MATRIX.md).
- **Evidence** — committed artifact (log, report, fixture hash).
- **Gate** — release/phase gate the requirement blocks.

## Chain table

| Req | Design | Impl | Test | Evidence | Gate | Gap |
|---|---|---|---|---|---|---|
| REQ-ING-001 | SPEC §1.1–1.2 | — | T-ING-101 | — | P1 exit | No code |
| REQ-ING-002 | SPEC §1.3 | — | T-ING-102 | — | P3 exit | No code; PDF lib undecided |
| REQ-ING-003 | OCR_PIPELINE | — | T-ING-103 | — | P3 exit | OQ-10 open |
| REQ-ING-004 | SPEC §1.4 | — | T-ING-104 | — | P1 exit | Format unfrozen |
| REQ-CAN-001 | CANONICALIZATION §Determinism | — | T-CAN-101 | — | P1 exit | Rule table unfrozen |
| REQ-CAN-002 | CANONICALIZATION §Output form | — | T-CAN-102 | — | P0 exit (freeze) + P1 | BOM/newline policy pending |
| REQ-CAN-003 | CANONICALIZATION rule table | — | T-CAN-103 | — | P1 exit | Rules Proposed |
| REQ-CAN-004 | SPEC §2.4 | — | T-CAN-104 | — | P1 exit | Depends on format |
| REQ-CAN-005 | CANONICALIZATION §Scripts | — | T-CAN-105 | — | P1 exit | hi/gu vectors not authored |
| REQ-CAN-006 | CAN-R09 / OCR_PIPELINE | — | T-CAN-106 | — | P3 exit | Threshold unmeasured |
| REQ-CAN-007 | ADR-0004 (Accepted) | — | T-CAN-107 | — | P3 exit | Metric defined; sample run missing |
| REQ-CMP-001 | SPEC §3.1 | — | T-CMP-101 | — | **P1 hard gate** | Core invariant unproven |
| REQ-CMP-002 | SPEC §4.1–4.6 | — | T-CMP-102 | — | P1 exit | Registry absent |
| REQ-CMP-003 | COST_MODEL §Selection | — | T-CMP-103 | — | P4 exit | Only Zstd initially |
| REQ-CMP-004 | COST_MODEL formula | — | T-CMP-104 | — | P2/P4 exit | Auditor absent |
| REQ-CMP-005 | SPEC §4.4 / RESOURCE_LIMITS | — | T-CMP-105 | — | P1 exit | Numeric limits pending PERFORMANCE_BUDGET |
| REQ-CMP-006 | SPEC §4.5 | — | T-CMP-106 | — | P1 exit | — |
| REQ-EXP-001 | SPEC §5.2 (ADR-0001) | — | T-EXP-101 | — | P4 per-candidate | Harness absent |
| REQ-EXP-002 | CORPUS_POLICY §Splits | — | T-EXP-102 | — | P2 exit | Corpus absent (OQ-8) |
| REQ-EXP-003 | BENCHMARK_PROTOCOL §Ablation | — | T-EXP-103 | — | each benchmark rev | — |
| REQ-FMT-001 | FORMAT_LXZ (PROPOSED) | — | T-FMT-101 | — | P1-T3 freeze | Layout intentionally not invented |
| REQ-FMT-002 | FORMAT_LXZ §Limits | — | T-FMT-102 | — | P1 exit | Values pending |
| REQ-FMT-003 | FORMAT_LXZ §Compat | — | T-FMT-103 | — | P1 exit | — |
| REQ-FMT-004 | FORMAT_LXDB (proposal) | — | — | — | P5 entry | Deferred by design |
| REQ-BMK-001 | CORPUS_POLICY | — | T-BMK-101 | — | P2 exit | OQ-8 |
| REQ-BMK-002 | SPEC §4.6 (ADR-0002/0003) | — | T-BMK-102 | — | P2 exit | Baseline tooling install path undocumented yet |
| REQ-BMK-003 | SPEC §5.2 | — | T-BMK-103 | — | M2 verdict | No results until real run |
| REQ-BMK-004 | BENCHMARK_PROTOCOL §Reporting | — | T-BMK-104 | — | P2 exit | Report schema drafted this batch |
| REQ-RES-001 | RESOURCE_LIMITS / PERFORMANCE_BUDGET | — | T-RES-101 | — | P1 exit + each phase | Reference machine undefined |
| REQ-RES-002 | DECISIONS OQ-7 | — | CI matrix | — | before P1 code | **Blocked: OQ-7 unanswered** |
| REQ-RES-003 | INSTALLATION / BUILD_GUIDE | — | T-RES-103 | — | P7 release | Vendoring plan missing |
| REQ-SEC-001 | SPEC §4 / THREAT_MODEL (Batch D) | — | fuzz | — | P6 exit | Fuzz target needs code first |
| REQ-SEC-002 | CORPUS_POLICY §Privacy | — | audit | — | P2 exit | Classification unknown (OQ-8) |
| REQ-SEC-003 | ENCRYPTION_PROFILE (Batch D) | — | KAT | — | P6 (if scoped) | Scope confirmation pending |
| REQ-SEC-004 | FORMAT_LXZ §Checksums | — | bit-flip | — | P1 exit | Hash algo pending format freeze |

## Gap summary (mandatory requirements without any verification means realized)

All implementation-stage links are currently gaps because the repository contains no code — this is expected at Phase 0 and recorded honestly rather than hidden. The two decisions that *block* closing gaps earliest are **OQ-7** (Python version → enables P1) and **OQ-8** (corpus → enables P2).

## Maintenance rule

Any PR/commit touching implementation MUST update the matching row(s) here and in IMPLEMENTATION_MATRIX.md in the same session; a chain cell may only move forward with a committed evidence link.
