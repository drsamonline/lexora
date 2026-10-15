# LEXORA Acceptance Criteria

> **Status:** Draft (criteria are testable statements; none evaluated yet — no code exists, verified 2026-10-15)
> **Owner:** Documentation architect (delegated)
> **Related:** [PRODUCT_REQUIREMENTS.md](PRODUCT_REQUIREMENTS.md) · [PHASES.md](PHASES.md) · [REQUIREMENTS_TRACEABILITY.md](REQUIREMENTS_TRACEABILITY.md) · [BENCHMARK_PROTOCOL.md](BENCHMARK_PROTOCOL.md)

## Purpose

Convert requirements into binary, checkable acceptance statements per phase gate. "Met" requires committed evidence, not assertion.

## Global criteria (apply at every release/phase cut)

| ID | Criterion | Verification | Met? |
|---|---|---|---|
| AC-G-1 | No document claims a feature is implemented unless code + passing tests exist in-repo | Doc audit + link/test run | Partially enforced via docs discipline; formal check planned (Batch E CI) |
| AC-G-2 | All internal documentation links resolve | `python3 scripts/linkcheck.py` → `ALL INTERNAL LINKS OK` | ✅ 2026-10-15 |
| AC-G-3 | Numeric gates identical everywhere (≥10% / ≥3%, 70/10/20, ≤1%/≤2%) | grep audit across docs | ✅ this batch (single source: SPEC §5.2, ADRs) |
| AC-G-4 | Continuity files (STATUS/PROGRESS/SESSION_LOG/NEXT_SESSION) updated & consistent each session | Session checklist | ✅ each session end |
| AC-G-5 | No benchmark numbers without a reproducible run artifact | BENCHMARK_RESULTS review | ✅ (file states "No validated benchmark results yet") |

## P0 — Foundations exit

| ID | Criterion | Linked req |
|---|---|---|
| AC-P0-1 | Rule table CAN-R01…Rn frozen with version string, byte-class whitelist, and ≥10 golden vectors per rule incl. hi/gu combining-mark cases | REQ-CAN-002/003/005 |
| AC-P0-2 | Every accepted decision has an ADR marked Accepted with date and basis | OQ set |
| AC-P0-3 | SPECIFICATION approved as `LEXORA-SPEC-1.0` via ADR-0005 or remains draft with documented reason | — |
| AC-P0-4 | Python version range decided (OQ-7) and recorded in DEPENDENCY_POLICY + build config plan | REQ-RES-002 |

## P1 — Core pipeline exit (hard gates)

| ID | Criterion | Linked req |
|---|---|---|
| AC-P1-1 | For every fixture C: `decode(encode(C)) == C` byte-exact, including 0-byte input, block-boundary ±1 sizes, all-NUL canonical content | REQ-CMP-001 |
| AC-P1-2 | Re-encoding unchanged canonical bytes twice yields identical archives (determinism) | REQ-CMP-003 |
| AC-P1-3 | Decoder refuses unknown codec IDs / must-understand flags with specific error codes, zero output bytes written | REQ-CMP-006, REQ-FMT-003 |
| AC-P1-4 | Single-document decode peak RSS ≤ budget in RESOURCE_LIMITS on reference machine; measured, not asserted | REQ-CMP-005, REQ-RES-001 |
| AC-P1-5 | `.lxz` v0 layout frozen by ADR + checked-in test vectors before release of the format label | REQ-FMT-001 |
| AC-P1-6 | Bit-flips anywhere in container fail checksum with refusal (no partial file emitted) | REQ-SEC-004 |

## P2 — Benchmark exit

| ID | Criterion | Linked req |
|---|---|---|
| AC-P2-1 | Corpus manifest ≥1 GiB, en/hi/gu, hash-pinned; split audit proves no lineage crosses train/val/held-out | REQ-BMK-001, REQ-EXP-002 |
| AC-P2-2 | Baselines run with pinned versions/settings; totals include every serialized byte | REQ-BMK-002, REQ-CMP-004 |
| AC-P2-3 | Verdict computed per ADR-0001 (Pass ≥10% / Partial ≥3% / Fail <3%) from repeated runs with variance reported | REQ-BMK-003/004 |
| AC-P2-4 | BENCHMARK_RESULTS.md contains only numbers reproducible from committed harness + manifest hashes | AC-G-5 |

## P3 — PDF/OCR exit

| ID | Criterion | Linked req |
|---|---|---|
| AC-P3-1 | Text-layer PDFs extract with page order preserved (golden fixtures) | REQ-ING-002 |
| AC-P3-2 | OCR absent ⇒ pipeline completes with documented skip report (no crash) | REQ-ING-003 |
| AC-P3-3 | Cleaning error rate ≤1% point estimate AND ≤2% bootstrap upper bound on seeded stratified sample (ADR-0004); 100% invariant checks pass | REQ-CAN-006/007 |
| AC-P3-4 | Every correction logged with engine confidence and rule ID | REQ-CAN-006 |

## P4–P7

Criteria inherit PHASES.md exit lists; each candidate additionally requires AC-P4-x: promotion evidence per ADR-0001 committed to BENCHMARK_RESULTS.md revision section before its codec ID becomes selectable. Release (P7) additionally requires real badges only, license present (OQ-5), CI green (OQ-6).

## Evidence format

Each "Met" flips with: commit hash, command run, output location (file in repo or attached log path), date, verifier role.
