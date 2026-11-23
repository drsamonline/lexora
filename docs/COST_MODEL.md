# Cost Model

> **Status:** Active — the formula, plus a byte-exact auditor for `.lxz` v0 (REQ-CMP-004)
> **Owner:** Documentation architect (delegated)
> **Last verified:** 2026-11-23 against `main` @ `8d8835a`
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

## The auditor (`REQ-CMP-004`)

`benchmarks/cost_audit.py` checks this formula against a real archive instead of restating it. It
decomposes an `.lxz` into the model's terms and requires the sum to equal the file size **exactly** —
no tolerance, because a tolerance is where an unaccounted field hides.

| Cost-model term | `.lxz` v0 | Size |
|---|---|---|
| `payload(r, b)` | the compressed block bytes | Σ `compressed_size` |
| `blockHeader(b)` + `blockMetadata` | the index entry: offset, sizes, per-block SHA-256 | 56 B × blocks |
| `indexContribution(b)` | the same entry — charged **once** | 0 additional |
| archive header | magic, version, flags, ids, limits, header hash | 128 B |
| archive trailer | index offset, index length, index hash | 40 B |
| `sideTables`, `dictionaryShare`, `residualBytes` | v0 carries no grammar, dictionary or literal tails | 0 |

**Why the double-count matters, and it is not hypothetical bookkeeping.** Charging the index entry
to `blockMetadata` *and* `indexContribution` makes the accounting 56 bytes per block **larger** than
the archive — the codec looks better than it is. Forgetting the trailer makes it 40 bytes **smaller**
— it looks like a saving. Both errors flatter the thing being measured, which is why they survive
review. A test pins each term to its owner.

Measured on a one-block archive of 8,800 canonical bytes: **287 B = 128 header + 63 payload + 56
index + 40 trailer**, unaccounted **0**. A byte inserted between the index and the trailer is
reported as unaccounted rather than absorbed.

**What this does not do:** it audits the *counting*, not the *choosing*. Rule 2's argmin over
enabled candidates is REQ-CMP-003 and is not implemented — v0 selects by pinned preset
(ADR-0015). And because v0 has no side tables or dictionary, three terms in the table above are
structurally zero; the audit proves nothing is unaccounted, not that every candidate's cost has
been computed.

## Reproducibility requirements

- Formula version string stored in archive manifest (`costmodel-vX.Y` proposed).
- Any change to what counts (e.g., new metadata field) requires benchmark re-run; historical results invalidated for comparison purposes.

## Open decisions

1. External-dictionary amortization scheme (Phase 3 prerequisite).
2. Index attribution method (per-block share vs. charged to archive total then divided by block count).
3. Tie-break priority list finalization.
