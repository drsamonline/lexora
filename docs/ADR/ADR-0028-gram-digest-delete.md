# ADR-0028: A delete follows a per-document gram digest, not the vocabulary

- **Status:** Accepted 2026-11-28, under the owner's standing delegation recorded in
  [ADR-0004](ADR-0004-cleaning-error-metric.md) ("decide ADRs yourself", revocable).
  It completes [ADR-0027](ADR-0027-schema-v4-gram-postings.md), whose own text named this
  as the open number ("`compact()` still never rebuilds the gram index" and the query side
  of v4 is settled while the delete side is not).
- **Date:** 2026-11-28
- **Extends:** [ADR-0024](ADR-0024-tokenizer-recording.md) (the short-query path),
  [ADR-0027](ADR-0027-schema-v4-gram-postings.md) (the posting-list layout)
- **Evidence:** `benchmarks/gram_delete_probe.py` → `benchmarks/results-gram-delete.json`;
  `tests/test_gram_delete_digest.py` (15 tests, 8 mutations of the shipped code all red)

## Context

Schema v4 made a gram **lookup** cost the size of the answer: one primary-key read, one
decode. It left the **delete** costing the size of the vocabulary, because
`_grams_delete` had no way to know which posting lists a document had reached except by
decoding every one of them. On the shape the row named — 500 documents, ~15k grams — that
is 19,478 posting lists decoded to remove one document.

The cost is not hypothetical: `add()` of a changed path supersedes the old row, and a
supersede is a delete. Every edit paid the whole vocabulary.

## What was measured

`benchmarks/gram_delete_probe.py`, committed, two documents in one catalog so the
comparison is between delete paths and not between corpora. Synthetic Zipfian Chinese from
the pool `gram_index_probe.py` already commits, trigram tokenizer.

| Shape | Vocabulary | `scan` (ships in v4) | `digest` (this ADR) | Ratio |
|---|---|---|---|---|
| 50 docs × 300 chars | 5,672 grams | 5,672 lists · 0.126 s | 356 lists · 0.035 s | **15.9× fewer** |
| 500 docs × 1,200 chars | 19,478 grams | 19,478 lists · 1.079 s | 1,044 lists · 0.317 s | **18.7× fewer** |

The **decode count** is the primary figure and the wall clock is context: a count does not
move with the cache, the machine or the load, which is why the tests assert the count and
never a duration.

The digest's price, also measured, in the same artifact:

| Shape | Posting table | Digest (front-coded + zstd-9) | Stored payload | Digest vs payload |
|---|---|---|---|---|
| 50 docs | 18,595 B | 45,390 B (2.44× postings) | 42,076 B | **1.08×** |
| 500 docs | 531,313 B | 1,004,202 B (1.89× postings) | 1,131,833 B | **0.887×** |

Front-coding alone was **4.1×** the posting table — the digest is mostly not adjacent in
the vocabulary, so prefix sharing buys little. Compressed it is 1.89×, which is the number
that made this a trade rather than a gift: the whole index on that shape is ~9.6 MB, so the
digest is **~10 % of the index** for an 18.7× cheaper delete.

## Decision

`doc_gram_digest(doc_id INTEGER PRIMARY KEY, grams BLOB)` — one row per indexed document,
holding the grams that document reached, sorted, front-coded (shared prefix length, suffix
length, suffix) and stored as one zstd-9 frame. `_grams_delete` reads it and touches only
those posting lists.

It is an **accelerator, never the authority**:

- The digest is written in the same transaction as the postings it describes, so it cannot
  describe a state the posting table is not in.
- A document with **no** digest row still deletes exactly: the v4 scan is kept as
  `_grams_delete_scan`. A v4 catalog written before this table existed is backfilled in one
  pass on its next open (`_backfill_gram_digests`), and a v3 catalog gets digests from the
  rows `_repack_grams` is already walking — no blob read in either case.
- A digest that **cannot be decoded** (a flipped byte in the stored frame) is dropped and
  the scan is taken. A document must not become undeletable because an index entry rotted.
- A posting left behind by any of the above is filtered at read time, because
  `_gram_rowids` joins live documents.

**Rejected: recompute the grams from the blob on delete.** `_unindex` already decodes the
blob to delete the FTS row, so the document's own text is in hand — that would cost zero
bytes. It was rejected because the gram delete runs *first and independently*, deliberately:
a document must leave the short-query index even when its payload has already gone missing
(that is why `_grams_delete` precedes the blob read in `_unindex`). Tying the delete's
exactness to a blob that may be absent would trade a measured 10 % of the index for a
correctness condition the current order exists to avoid.

**Rejected: a hash of each gram.** The probe in ADR-0027 already showed a 32-bit hash buys
3–19 % and turns an exact answer into a candidate one; a digest of hashes cannot name the
posting list to touch at all.

## Consequences

- `stats()["gram_index"]["digested"]` reports how many documents a delete can answer for
  directly. A catalog that has not been backfilled deletes exactly but at the old cost, and
  the owner can see which state they are in.
- `SCHEMA_VERSION` stays **4**: the change is additive — a new table, no existing column or
  row reinterpreted, and an older binary reading the catalog is unaffected.
- Supersede, delete and `compact()` all leave no digest row behind for a document that is
  no longer indexed.
