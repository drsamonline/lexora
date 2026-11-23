# ADR-0025: The gram index keeps its layout — the cost is row count, and packing does not fix it

- **Status:** Accepted 2026-11-23, under the owner's standing delegation recorded in
  [ADR-0004](ADR-0004-cleaning-error-metric.md) ("decide ADRs yourself", revocable). It ratifies
  the status quo: **no stored byte changes.** If the owner disagrees, nothing has to be undone.
- **Date:** 2026-11-23
- **Extends:** [ADR-0024](ADR-0024-tokenizer-recording.md) (the tokenizer and the short-query path)
- **Resolves:** P3.8 in [PATH_TO_V1](../PATH_TO_V1.md)
- **Evidence:** `benchmarks/gram_index_probe.py` → `benchmarks/results-gram-index.json`

## Context

`doc_grams` answers a one- or two-character CJK query from an index instead of scanning. It was
measured once at **~5x the stored payload**, and that number went into the CHANGELOG — from a
generator that was never committed. Two problems, and the second is the serious one:

1. the cost is real and needs a decision;
2. a figure with no artifact behind it cannot be re-derived, and this project's rule is that no
   number enters a document outside a published revision with its evidence.

So P3.8 asked for a packed-hash form of the table. This ADR records what happened when the
packing was measured instead of assumed: **it does not buy enough to justify a schema change, and
the cost is not where the proposal thought it was.**

## What was measured

`benchmarks/gram_index_probe.py` builds five layouts over identical data in one SQLite file and
reports page usage from `dbstat` — real pages, not arithmetic. Synthetic Zipfian Chinese, three
shapes chosen to separate the two effects a single document cannot distinguish.

| Shape | Stored payload (zstd-9) | `a_current` (ships) | `b_hash32` | `c_hash4` | `d_posting32` | `e_posting_text` |
|---|---|---|---|---|---|---|
| 1 doc × 20,000 chars | 24,668 B | 77,824 B — **3.15×** | 1.06× | 1.19× | **0.76×** | 0.76× |
| 50 docs × 4,000 chars | 223,804 B | 1,478,656 B — **6.61×** | 1.06× | 1.16× | **2.24×** | 2.09× |
| 500 docs × 400 chars | 223,679 B | 2,973,696 B — **13.29×** | 1.03× | 1.11× | **1.78×** | 1.75× |

`vs_current` is how much smaller the layout is; `d_posting32` and `e_posting_text` are inverted
indexes (one row per gram, packed doc ids), the rest are one row per (gram, document).

**And the best any of them does, measured against the payload it indexes:** 2.66× on the single
document, 2.95× on the small corpus, 7.49× where bigrams recur most. There is no packing that
makes this index small — only packing that makes it smaller than it is.

Three findings, in order of how much they change the plan:

**1. The cost is row count, not gram width.** A gram averages 3–6 UTF-8 bytes; a row costs
13.8–14.5 bytes. Hashing the gram to 32 bits saves **3–6 %**; storing it as a 4-byte BLOB saves
**11–19 %**. That is the whole of the "packed-hash form" P3.8 asked for: a schema version, a
migration and a verification path for a sixth of the cost.

**2. The inverted index wins only where bigrams recur across documents — and loses where they do
not.** 2.24× smaller on 50 documents that share a vocabulary; **0.76× on one document**, where
every posting list holds a single id and the blob overhead is pure loss. Which regime a real
catalog sits in is a fact about the corpus, and the corpus run is P0 — not yet done.

**3. "5× the stored payload" is a point on a curve, not a constant.** The same table costs 3.15×,
6.61× and 13.29× the payload depending only on how much the corpus repeats itself. The single
figure in the CHANGELOG is not wrong so much as under-determined, and it is now replaced by the
measured range with its artifact.

**Exactness was not the constraint.** A 32-bit CRC over these gram sets produced **zero
collisions** at all three shapes, so the verification pass that option 1 would have needed was
affordable — the option simply did not save enough to be worth having.

## Decision

**Keep `doc_grams(gram, doc_id)` as it is.** Change no stored byte, migrate nothing.

Replace the orphan figure with the measured range, cited to the artifact, in `CHANGELOG.md`,
`README.md` and [ADR-0024](ADR-0024-tokenizer-recording.md).

**The inverted index is recorded, not rejected.** `d_posting32` is the only layout that reduces
the cost materially, and it does so exactly when a catalog has many documents sharing bigrams —
which is the shape a real archive has. Revisit it when P0 gives a real corpus and the recurrence
ratio is measurable, with this probe as the baseline. Until then the honest position is the one
this ADR takes: state the cost, do not pay for a migration that buys a sixth.

## Consequences

- (+) No schema change, no migration, no exactness risk, and the cost is now reproducible and
  correctly stated.
- (+) The probe is committed, so the next person can re-derive every number in this ADR.
- (−) The index stays large relative to the payload. That is the price of answering a
  one-character CJK query without reading a blob, and it is now a *measured* price.
- (−) A future corpus may show the inverted index is worth it; that will be a new ADR, not a
  reopening of this one.

## What this ADR deliberately does not do

- It does not claim the shipped layout is optimal. It claims the alternatives were measured and
  none of them wins by enough to justify a v4 schema under the exactness constraint.
- It does not re-measure the query path's *time* — only its size. The short-query scan's latency
  bound is [ADR-0024](ADR-0024-tokenizer-recording.md)'s subject, and it is unchanged.
