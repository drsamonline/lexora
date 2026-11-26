# ADR-0027: Schema v4 — `doc_grams` becomes one posting list per gram

- **Status:** Accepted 2026-11-26, under the owner's standing delegation recorded in
  [ADR-0004](ADR-0004-cleaning-error-metric.md) ("decide ADRs yourself", revocable). It
  supersedes the *layout* half of [ADR-0025](ADR-0025-gram-index-layout.md), which kept
  `doc_grams(gram, doc_id)` on the finding that packing bought 11–19 %.
- **Date:** 2026-11-26
- **Extends:** [ADR-0024](ADR-0024-tokenizer-recording.md) (the short-query path),
  [ADR-0025](ADR-0025-gram-index-layout.md) (the measured cost)
- **Evidence:** `benchmarks/gram_index_probe.py` → `benchmarks/results-gram-index.json`;
  `tests/test_gram_postings.py` (17 tests)

## Context

ADR-0025 measured five layouts and concluded that the cost of `doc_grams` is **row
count**, not gram width, and that the inverted layouts it measured (`d_posting32`,
`e_posting_text`) only win where bigrams recur across documents — 0.76× on a single
document, 2.24× on fifty. It ended with a standing invitation: *"Revisit it when P0
gives a real corpus and the recurrence ratio is measurable, with this probe as the
baseline."*

Two things changed the answer without changing the corpus.

**1. Every layout ADR-0025 measured stored the document ids at a fixed width.** Four
bytes per id, whether the ids were 3, 300 or 30,000 apart. A posting list is a *sorted*
set of ids, so the obvious encoding — store the deltas — was simply not in the table. It
is now, as `f_posting_varint`, using the encoder schema v4 ships rather than a proxy for
it.

**2. The single-document case is degenerate and was treated as the conservative one.**
A catalog with one document is a catalog with nothing to search across. The shape a real
archive has is many documents sharing a vocabulary — which is the regime where an
inverted index wins, and ADR-0025 already said so.

## What was measured (re-run 2026-11-26, same probe, one variant added)

| Shape | Stored payload | `a_current` (v3, ships until now) | `f_posting_varint` (v4) | v4 vs v3 |
|---|---|---|---|---|
| 1 doc × 20,000 chars | 24,668 B | 77,824 B — **3.15×** | 81,920 B — 3.32× | **5 % larger** |
| 50 docs × 4,000 chars | 223,804 B | 1,490,944 B — **6.66×** | 327,680 B — **1.46×** | **4.55× smaller** |
| 500 docs × 400 chars | 223,679 B | 2,998,272 B — **13.4×** | 471,040 B — **2.11×** | **6.37× smaller** |

The delta coding is also what makes the posting list beat the fixed-width one it replaces:
`f_posting_varint` is **2.2×–3.5× smaller than `d_posting32`** on the two multi-document
shapes, because a run of consecutive document ids costs one byte each instead of four.

**Exactness was not spent.** No hash is involved. The key is the gram itself, so a
lookup is exact by construction — unlike `b_hash32`/`c_hash4`, which the probe shows
would have needed a verification pass for a saving of 3–19 %.

## Decision

`doc_grams` holds **one row per gram**, with its document ids delta-coded as LEB128
varints, plus a `doc_gram_docs` row per indexed document so "is this document indexed"
is a primary-key lookup:

```sql
CREATE TABLE doc_grams (gram TEXT PRIMARY KEY, postings BLOB NOT NULL) WITHOUT ROWID;
CREATE TABLE doc_gram_docs (doc_id INTEGER PRIMARY KEY);
```

- **Query cost is unchanged in kind.** A short query is still one primary-key lookup and
  a decode, so its cost is the size of the answer, not the size of the corpus.
- **v3 catalogs are repacked on open**, from the grams they already hold: no blob is
  read and nothing is re-ingested. A v3 catalog that was half backfilled stays half
  backfilled — its coverage markers are written from the rows it actually had — so the
  scan still answers for the documents the index never covered.
- **A posting naming a document that is no longer live is filtered at read time.** The
  FTS row is best-effort on unindex; this is not.

## Consequences

- (+) The index costs 1.46×–2.11× the payload it indexes instead of 6.66×–13.4×, on the
  multi-document shapes an archive actually has.
- (+) Exact: no collision, no verification pass, no new failure mode.
- (−) **5 % more expensive on a one-document catalog** — the degenerate case ADR-0025
  weighted, now a rounding error rather than a 24 % loss.
- (−) Unindexing a document now walks the gram table instead of deleting by `doc_id`,
  because a posting list is keyed by gram. A delete is rare and the walk is bounded by
  the vocabulary (15,000 rows in the probe's largest shape).
- The v3 shape can be rebuilt from v4 by the same transform in reverse; nothing was
  removed from the archive that could not be derived again.
