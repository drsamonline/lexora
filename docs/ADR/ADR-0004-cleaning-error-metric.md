# ADR-0004: Operational Definition of the ≤1% Cleaning Error Rate

> **Status:** Accepted 2026-10-15 by documentation-architect delegation (owner directive "decide ADRs yourself"; revocable by owner — resolves OQ-4)
> **Date:** 2026-10-15
> **Owner:** Unassigned
> **Related:** [Blueprint §3](../../LEXORA_Full_Blueprint_Design_Master_Prompt.md) · [DECISIONS.md](../DECISIONS.md) · REQ-CAN-007

## Context / Problem

The blueprint's goal "cleaning error rate ≤ 1%" has no operational definition: what counts as an error, over what unit (character? word? document?), measured against what reference, on which dataset. Without a definition, REQ-CAN-007 cannot be tested and Phase 0 cannot exit.

## Decision drivers

- Must be measurable with modest manual effort on a 4 GiB prototype budget.
- Must protect against *silent* data corruption (the real risk of cleaning).
- Deterministic recomputation from stored artifacts.

## Options considered

- **A.** Edit-distance ratio vs. hand-corrected gold text for the whole corpus — accurate but too expensive to label ≥1 GiB in three languages.
- **B. (Recommended)** **Rule-audit metric** on a labeled sample:
  - Unit: canonicalized document.
  - Metric: `error_rate = (bytes changed by rules that the reviewer marks incorrect) / (total bytes)` computed over a stratified random sample (≥200 documents per language, seeded selection recorded in the manifest).
  - Two reviewers; disagreements adjudicated and logged.
  - Pass condition: point estimate ≤ 1% **and** 95% bootstrap upper bound ≤ 2% (guards small-sample noise).
  - Additionally: 100% automated invariant checks (rule table only touches whitelisted byte classes; everything else passes through unchanged — REQ-CAN-003 golden vectors).
- **C.** Self-certification via rule logs only — rejected; cannot catch rules applied where inappropriate.

## Decision (proposed)

Adopt **Option B**. CANONICALIZATION.md will host the rule table; the sample + review protocol lives under the benchmark corpus policy. Until accepted, REQ-CAN-007 stays **Blocked**.

## Consequences

- (+) Cheap, repeatable, tied to lineage-safe sampling.
- (−) Sample-based: a rare catastrophic rule bug could evade detection — mitigated by invariant tests (Option B second half) covering 100% of archived content.

## Implementation and test implications

- Sampling script with seed recorded in corpus manifest hash.
- Review worksheet template (add to docs/templates/ once metric approved).

## Resolution

**Accepted Option B on 2026-10-15** under the project owner's directive to decide ADRs autonomously (documentation-architect delegation; revocable by owner via superseding ADR).