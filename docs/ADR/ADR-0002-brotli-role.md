# ADR-0002: Role of Brotli (Baseline vs. Candidate)

> **Status:** Proposed (awaiting owner approval — resolves OQ-2)
> **Date:** 2026-10-15
> **Owner:** Unassigned
> **Related:** [Blueprint §8, §9, §12](../../LEXORA_Full_Blueprint_Design_Master_Prompt.md) · [DECISIONS.md](../DECISIONS.md)

## Context / Problem

Blueprint sections assign Brotli conflicting roles: §8 defines Core as Zstandard only; §9 lists alternatives including Brotli as a possible candidate; §12 pins four frozen comparison baselines (Zstd-19, Brotli q11, XZ, PPMd). Documentation and code must state one authoritative role set.

## Decision drivers

- Baselines are yardsticks, not shipping codecs; mixing roles corrupts benchmark verdicts.
- Core decoder surface should stay minimal on 4 GiB targets.

## Options considered

- **A.** Brotli as shipping default — rejected; contradicts Core = Zstd.
- **B. (Recommended)** Brotli q11 is a **frozen comparison baseline only**. It is never auto-selected for archives. If future evidence suggests Brotli beats Zstd on some category, introducing it as a selectable codec requires a *new* ADR plus the ADR-0001 promotion gate.
- **C.** Remove Brotli from baselines — rejected; strong general-purpose yardstick, cheap to run.

## Decision (proposed)

Adopt **Option B**: Brotli = measurement baseline, non-selectable. Same structural treatment applied to XZ and PPMd (see ADR-0003 for PPMd's RAM caveat).

## Consequences and trade-offs

- (+) Clear separation: `codec_id` space contains only Zstd (Core) + promoted candidates.
- (−) None significant.

## Implementation and test implications

- Benchmark harness invokes external `brotli` CLI/lib at quality 11 solely for baseline runs.
- Format registry reserves IDs so baseline-only codecs cannot silently appear in archives.

## Open — owner input needed

Reply "accept ADR-0002" (or amend). Until accepted, COMPRESSION_ARCHITECTURE.md labels this arrangement **Proposed**.
