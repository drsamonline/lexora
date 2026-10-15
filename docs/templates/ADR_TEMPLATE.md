# ADR Template

Canonical copy of the decision-record template. Working location for future numbered records: `docs/ADR/ADR-NNNN-short-title.md`. Index & open questions: [../DECISIONS.md](../DECISIONS.md).

```markdown
# ADR-NNNN: <Short title of the decision>

> **Status:** Proposed | Accepted | Rejected | Superseded by ADR-XXXX
> **Date:** YYYY-MM-DD
> **Deciders:** <who approved; project owner for Accepted>
> **Related documents:** <spec sections, docs, issues, commits>

## Context / Problem
What forces this decision? Cite verified facts and evidence (blueprint section, measured data), not memory.

## Decision drivers
- byte-exact recovery guarantee / RAM budget / benchmark fairness / simplicity / …

## Options considered
### Option A — <name>
**Pros:** …  **Cons:** …
### Option B — <name>
**Pros:** …  **Cons:** …

## Decision
<Normative statement of the choice. If Proposed: recommendation + what approval is pending.>

## Consequences & trade-offs
Positive / negative / accepted risks.

## Impact analysis
| Dimension | Impact |
|---|---|
| Security | None / description |
| Performance / memory | None / description |
| Compatibility (format/spec) | None / breaking? version bump + migration note |

## Implementation & test implications
Files to change; tests required; benchmark revision implications.

## Affected documents
- [ ] docs/SPECIFICATION.md
- [ ] docs/PRODUCT_REQUIREMENTS.md
- [ ] others
```

## Numbering & lifecycle rules
1. Take the next unused number from `docs/ADR/README.md` index.
2. Status starts **Proposed**; only the project owner flips it to **Accepted**.
3. Accepted ADRs are immutable; supersede with a new ADR instead of editing.
4. Update `docs/DECISIONS.md` index and `CHANGELOG.md` in the same session.
