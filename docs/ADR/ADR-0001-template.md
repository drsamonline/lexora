# ADR-NNNN: <Short title of the decision>

> **Status:** Proposed | Accepted | Rejected | Superseded by ADR-XXXX
> **Date:** YYYY-MM-DD
> **Deciders:** <who approved; project owner for Accepted>
> **Related documents:** <spec sections, docs, issues, commits>

## Context / Problem

What forces this decision? Include verified facts, constraints (RAM budget, losslessness invariant), and any blueprint conflict being resolved. Cite evidence, not memory.

## Decision drivers

- e.g., byte-exact recovery guarantee
- e.g., ≤ 4 GiB RAM operation
- e.g., benchmark fairness / leakage control
- e.g., implementation simplicity in Python

## Options considered

### Option A — <name>
- Description…
- **Pros:** …
- **Cons:** …

### Option B — <name>
- **Pros:** …
- **Cons:** …

(Add more as needed. "Do nothing" is an option when relevant.)

## Decision

<The choice made, in one or two normative sentences. If Proposed, state the recommendation and what approval is pending.>

## Consequences & trade-offs

- Positive: …
- Negative / accepted risks: …

## Impact analysis

| Dimension | Impact |
|---|---|
| Security | None / description |
| Performance / memory | None / description |
| Compatibility (format/spec) | None / description (breaking changes require version bump + migration note) |

## Implementation & test implications

- Files/modules expected to change: …
- New/updated tests required: …
- Benchmark revision implications: …

## Affected documents

- [ ] `docs/SPECIFICATION.md`
- [ ] `docs/PRODUCT_REQUIREMENTS.md`
- [ ] others: …
