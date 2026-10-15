# ADR-0003: PPMd as Baseline Despite Unsuitability as Primary Codec

> **Status:** Accepted 2026-10-15 by documentation-architect delegation (owner directive "decide ADRs yourself"; revocable by owner — resolves OQ-3)
> **Date:** 2026-10-15
> **Owner:** Unassigned
> **Related:** [Blueprint §11, §12](../../LEXORA_Full_Blueprint_Design_Master_Prompt.md) · [DECISIONS.md](../DECISIONS.md)

## Context / Problem

§11 notes PPMd is a poor primary codec for the low-RAM Python prototype (memory-hungry order-N models, weak library support), yet §12 pins PPMd as one of four frozen baselines. This looks contradictory unless roles are separated.

## Options considered

- **A.** Drop PPMd from baselines — rejected; PPMd remains a strong text-compression yardstick, especially for natural-language data, and omitting it would weaken claims of competitiveness.
- **B. (Recommended)** PPMd is a **measurement-only baseline**. It can never become a selectable archive codec in the Python prototype. The token-level bounded PPM *candidate* (blueprint §9) is a separate, purpose-built implementation and does not inherit this exclusion.
- **C.** Allow PPMd as codec behind a feature flag — deferred; revisit only if a native decoder is implemented and memory-budgeted.

## Decision (proposed)

Adopt **Option B**. REQ-BMK-002 keeps PPMd pinned as baseline; REQ-CMP-002 codec registry excludes it.

## Consequences

- (+) No contradiction; honest yardstick retained; shipping surface stays small.
- (−) Baseline runs need an external PPMd tool (`7z`/`ppmd`), documented in BUILD_GUIDE.

## Resolution

**Accepted Option B on 2026-10-15** under the project owner's directive to decide ADRs autonomously (documentation-architect delegation; revocable by owner via superseding ADR).