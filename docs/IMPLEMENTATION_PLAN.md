# LEXORA Implementation Plan

> **Status:** Draft (sequencing plan; execution starts only after P0 exit criteria relevant to code are met)
> **Owner:** Documentation architect (delegated)
> **Last verified:** 2026-10-15 — repository is documentation-only; no implementation started
> **Related:** [PHASES.md](PHASES.md) · [TASK_BREAKDOWN.md](TASK_BREAKDOWN.md) · [ROADMAP.md](ROADMAP.md) · [ACCEPTANCE_CRITERIA.md](ACCEPTANCE_CRITERIA.md)

## Purpose & scope

How the phases get executed: ordering, work-package sizes, decision prerequisites, and invariants that must hold throughout. PHASES.md defines *what* each phase exits on; this file defines *how we walk through them*.

## Standing invariants (never violated during implementation)

1. **Lossless core law:** after canonicalization, `decode(encode(C)) == C` byte-exact. Any commit that could break it without a failing test is a process defect.
2. **Cost honesty:** every candidate's serialized bytes counted (REQ-CMP-004) before any size claim.
3. **Gate discipline:** nothing becomes a selectable codec without ADR-0001 promotion evidence; baselines stay measurement-only (ADR-0002/0003).
4. **Traceability sync:** code PR updates IMPLEMENTATION_MATRIX + REQUIREMENTS_TRACEABILITY rows in the same session.
5. **Docs describe reality:** status flips require evidence links (QUALITY_PLAN gates).

## Execution order & rationale

| Step | Work package | Depends on | Why here |
|---|---|---|---|
| 1 | Finish P0 doc batches D–E | — | Cheap now; prevents rework when code lands |
| 2 | Freeze canonicalization rule table v0 + golden vectors (P0-T6) | review of CANONICALIZATION rules | Everything downstream consumes canonical bytes; freezing early protects determinism |
| 3 | Resolve OQ-7 → packaging skeleton, CI harness shape | owner/delegation | Blocks all code |
| 4 | `.lxz` v0 layout freeze ADR (P1-T3) | step 2 field needs | Format first, encoder second — avoids inventing offsets twice |
| 5 | Canonicalizer TXT-only + tests (P1-T2) | steps 2–4 | Smallest end-to-end slice proving the invariant machinery |
| 6 | Zstd block codec + reader/writer + CLI (P1-T4/T5) | step 5 | Core baseline usable ⇒ quick-start commands become real |
| 7 | Memory/perf harness (P1-T6) | step 6 | Budget compliance proven at P1 exit |
| 8 | Corpus assembly + lineage splitter (P2-T1/T2) | OQ-8 | Benchmarks need frozen data |
| 9 | Baseline runners + verdict report (P2-T3/T4) | steps 6+8 | First honest numbers ever published |
| 10 | PDF text-layer, then OCR path (P3) | OQ-10 | Ingestion breadth after compression core proven |
| 11 | Candidate codecs one-by-one behind promotion gate (P4) | step 9 harness | Each earns its keep or gets retired |
| 12 | `.lxdb` layer (P5), security campaign (P6), release (P7) | prior exits | Deferred by design |

## Session sizing

Work packages above decompose into ≤5-file commits (master-prompt §1.6 checkpoint rule). Recommended session target: one task ID from TASK_BREAKDOWN.md plus continuity updates.

## Risk-ordered watchlist

| Risk | Mitigation already planned |
|---|---|
| Format churn invalidating fixtures | Layout freeze ADR before encoder (step 4) |
| Benchmark leakage inflating results | Lineage audit fails run (BENCHMARK_PROTOCOL §2) |
| Low-RAM violations discovered late | RSS checks from P1 exit onward, not P7 |
| Delegated decisions overturned | Superseding-ADR pattern; delegation basis recorded (DECISIONS.md) |
| Docs drift from code | Traceability sync invariant #4 + Batch E CI checks |

## Explicitly out of plan (until owner scope change)

Source-level losslessness (pre-canonicalization recovery), GPU acceleration, server/multi-user deployment, PyPI publication before P7 with real license (OQ-5).
