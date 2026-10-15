# Cost Model

> **Status:** Proposed (formula-level; constants unmeasured)
> **Owner:** Unassigned
> **Last verified:** 2026-10-15
> **Related:** [SPECIFICATION.md §4.2–§4.3](SPECIFICATION.md) · [COMPRESSION_ARCHITECTURE.md](COMPRESSION_ARCHITECTURE.md) · REQ-CMP-003/004

## Purpose & Scope

Defines how codec/candidate selection compares alternatives on a single, honest currency: **total serialized bytes of everything required to decode**. No numbers in this document are measured results; they are structural definitions.

## The accounting rule (`REQ-CMP-004`)

For each block *b* and candidate representation *r*:

```text
TotalCost(b, r) = payload(r, b)
                + blockHeader(b)                 # codec ID, profile ID, flags, lengths
                + blockMetadata                  # checksums, compressed-size fields
                + sideTables(r, b)               # e.g., Re-Pair grammar, record schema/template
                + dictionaryShare(r)             # embedded dict bytes OR amortized external-ref cost
                + indexContribution(b)           # archive-index bytes attributable to b
                + residualBytes(r)               # literal fallback / diff tails
```

Rules:

1. **Nothing is free.** If the decoder needs it, its bytes count — including "shared" structures. Shared dictionaries/grammars are charged either fully to one archive (embedded) or via an explicit external-reference resolution policy recorded in the manifest; amortization schemes must be defined before Phase 3 and reviewed by ADR.
2. **Selection metric.** Per block, choose argmin over enabled candidates of TotalCost; ties broken by fixed candidate priority order (pinned → determinism, `REQ-CMP-003`).
3. **Gate comparisons** use corpus totals: `sum(TotalCost)` over held-out vs. best frozen baseline's equivalent total, per [ADR-0001](ADR/ADR-0001-gate-scope.md).
4. **Non-byte costs are out of band.** CPU time and RAM do not enter the byte formula but act as *hard eligibility filters* (resource budgets, RESOURCE_LIMITS doc pending Batch C/D). A candidate that wins bytes but busts memory is ineligible, not "compensated".

## Overhead examples (illustrative structure only — no real figures)

| Candidate | Typical overhead source | Failure mode the model catches |
|---|---|---|
| Shared dictionary | Dict bytes embedded per small archive | Tiny archives "optimized" with a 100 KB dict net-worse than plain Zstd |
| Re-Pair | Grammar table size | Grammar trained for large docs hurting short-doc blocks |
| Token PPM | Model parameters serialized per block | Complexity without size win |
| Record coding | Schema description | Misdetected records paying schema cost for nothing |

## Reproducibility requirements

- Formula version string stored in archive manifest (`costmodel-vX.Y` proposed).
- Any change to what counts (e.g., new metadata field) requires benchmark re-run; historical results invalidated for comparison purposes.

## Open decisions

1. External-dictionary amortization scheme (Phase 3 prerequisite).
2. Index attribution method (per-block share vs. charged to archive total then divided by block count).
3. Tie-break priority list finalization.
