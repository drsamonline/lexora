# Compression Architecture

> **Status:** Proposed (design level; nothing implemented)
> **Owner:** Unassigned
> **Last verified:** 2026-10-15
> **Related:** [SPECIFICATION.md §4–§6](SPECIFICATION.md) · [COST_MODEL.md](COST_MODEL.md) · [MASTER_BLUEPRINT.md](MASTER_BLUEPRINT.md)

## Purpose & Scope

Describes how canonical bytes `C` become archives: the Core Zstandard baseline, experimental candidate representations, the selection policy, dependencies between stages, ablation/retirement, and fallback behavior. No performance claims appear here — see [BENCHMARK_RESULTS placeholder note in index.md](index.md); none exist.

## Core baseline (the shipping floor)

- **Codec:** Zstandard via the `zstandard` Python binding *(binding choice proposed; OQ-7 pins Python version first)*.
- **Profiles (proposed IDs):** `zstd-fast` (low level, streaming), `zstd-max` (level 19-class, block mode) — exact levels frozen when format ADR defines profile ID space.
- **Block policy:** fixed-cap blocks with configurable ceiling so single-document decode stays bounded (`REQ-CMP-005`). Block size numbers are **not yet measured**; budget TBD in RESOURCE_LIMITS doc (Batch C/D).
- Dictionaries optional even in Core: an archive MAY reference a dictionary (§Dictionary identity, SPEC §6) but Core decoding without one MUST succeed for dictionaries marked optional.

## Candidate representations (experimental — not shipping features)

| Candidate | Idea | Serialized overhead that must be paid for | Dependency |
|---|---|---|---|
| Shared dictionary | zstd dict trained on training split | Dictionary bytes (embedded) or ID+hash resolution cost | REQ-EXP-002 lineage audit |
| Re-Pair grammar | Iterative pair replacement; store grammar + encoded stream | Grammar table size vs. stream savings | Tokenizer-free; block-local grammars preferred for memory |
| Bounded token PPM | Small-order context model over tokens from [TOKENIZER_SPEC.md](TOKENIZER_SPEC.md) | Model params/context limits; RAM bound | Tokenizer spec + literal fallback |
| Numeric/record coding | Column-wise delta/varint for record-shaped data | Schema/template description bytes | Record detection reliability |
| Template + residual | Cluster near-duplicate docs; store template + diffs | Template store + residual entropy | Dedup pipeline; corpus category evidence |

All candidates remain **disabled defaults** until they pass the promotion gate ([ADR-0001](ADR/ADR-0001-gate-scope.md)) under full cost accounting ([COST_MODEL.md](COST_MODEL.md)).

## Selection policy

```mermaid
flowchart TD
  IN[Canonical bytes C] --> CORE[Zstd profile set\nalways evaluated]
  IN --> CAT{Category detector\n(record/numeric/etc.)}
  CAT -->|eligible| CANDS[Evaluate enabled candidates]
  CORE --> COST[Cost model:\ntotal serialized bytes\nREQ-CMP-004]
  CANDS --> COST
  COST -->|incumbent wins| PICK[Per-block codec choice]
  PICK --> OUT[Archive + manifest of choices]
```

- Evaluation order and settings pinned → reproducible selection (`REQ-CMP-003`).
- Per-block (not per-archive) granularity proposed; final granularity awaits format ADR.

## Ablation plan & retirement

- Every benchmark revision re-runs each candidate against the incumbent with the candidate disabled (ablation).
- Retirement thresholds (proposed): candidate dropped if its category win < 3% on held-out for two consecutive revisions, or if decoder complexity/RAM violates resource budgets.
- Retired candidates keep reserved codec IDs forever (never reused) for format hygiene.

## Fallback behavior

1. If any candidate infrastructure fails at encode time ⇒ fall back to Core Zstd silently-but-logged; never fail the archive job for an experimental path.
2. Decoder encountering unknown codec ID ⇒ refuse cleanly (`REQ-CMP-006`); never approximate.

## What this document does NOT claim

- No ratio improvements over Zstd/Brotli/XZ/PPMd are asserted anywhere.
- No candidate is described as available to users today.
