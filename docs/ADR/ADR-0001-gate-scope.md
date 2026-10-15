# ADR-0001: Scope of the ≥10% Acceptance Gate

> **Status:** Proposed (awaiting owner approval — resolves OQ-1)
> **Date:** 2026-10-15
> **Owner:** Unassigned
> **Related:** [Blueprint §10, §12](../../LEXORA_Full_Blueprint_Design_Master_Prompt.md) · [DECISIONS.md](../DECISIONS.md) · [SPECIFICATION.md](../SPECIFICATION.md)

## Context / Problem

The blueprint states a "≥10% improvement" rule in two different contexts:

1. **§10 (candidate promotion):** an optional codec/candidate earns a place per-file/per-category when it beats the incumbent by a margin.
2. **§12 (benchmark verdict):** the whole system Pass/Fails against frozen baselines on the held-out corpus (Pass ≥10%, Partial ≥3%, Fail <3%).

Left unresolved, these could be read as one global rule, causing either (a) candidates rejected despite corpus-level wins, or (b) a shipping default justified only by per-file cherry-picking.

## Decision drivers

- Normative spec must have exactly one meaning per gate.
- Reproducibility: gates must map to concrete measurements.
- Low-resource target: avoid complexity that does not pay for itself.

## Options considered

- **A.** Single whole-corpus gate; drop per-file promotion. Simple, but discards legitimate per-domain wins (e.g., numeric records).
- **B.** Single per-file gate; corpus verdict derived from it. Fragile — small files create noisy percentages.
- **C. (Recommended)** Two distinct gates with explicit roles:
  - **Promotion gate (per category):** a candidate may replace the incumbent for a document *category* only if total stored size (REQ-CMP-004 accounting) improves ≥10% on **validation** split for that category, and the win reproduces on **held-out**.
  - **Benchmark verdict (whole corpus, held-out):** Pass ≥10%, Partial ≥3%, Fail <3% vs. best frozen baseline, computed on total stored bytes across the corpus.

## Decision (proposed)

Adopt **Option C**. SPECIFICATION.md will define both gates normatively; BENCHMARK_PROTOCOL.md will operationalize them. REQ-BMK-003 refers to the verdict gate; REQ-EXP-001 refers to the promotion gate.

## Consequences and trade-offs

- (+) Both per-domain and global evidence required before anything ships.
- (−) More benchmark bookkeeping (per-category tables required in results reports).

## Security / performance / compatibility impact

None directly; reduces risk of shipping unjustified complexity.

## Implementation and test implications

- Benchmark harness must emit per-category and per-corpus totals.
- Split audit script must enforce lineage separation for both gates.

## Open — owner input needed

Reply "accept ADR-0001" (or amend) to unblock normative wording in SPECIFICATION.md §Gates. Until accepted, SPECIFICATION.md marks this section **Proposed**.
