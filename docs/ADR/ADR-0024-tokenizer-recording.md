# ADR-0024: The tokenizer is recorded per document, and CJK gets its own index

- **Status:** Accepted
- **Date:** 2026-11-18
- **Supersedes:** nothing. Extends [ADR-0022](ADR-0022-language-plugins.md) and
  [ADR-0023](ADR-0023-plugin-provenance.md).
- **Decided by:** Forge cycle, on evidence measured in this sandbox (SQLite 3.40.1).

## Context

ADR-0022 gives a language plugin four declared capabilities and says which one matters
most: *"a search tokenizer — which FTS5 tokenizer the index should use (this is the one
that matters most for Chinese/Japanese, which have no spaces to split on)"*.

By 2026-11-18 that sentence was decoration. `doctor` printed `plugin.tokenizer` and
nothing else read it; `catalog.py` created one FTS5 table with `tokenize='unicode61'`
hard-coded, in two places, and `Catalog.add()` had no way to say otherwise. Two
space-separated scripts (`en`, `hi`) both declare `unicode61`, so nothing failed and
nothing could have failed: the declaration was untested because it was never used.

`docs/PATH_TO_V1.md` P3.7 says the third language "forces P3.6's tokenizer recording".
This ADR is that recording.

## The measurements

Four facts, taken before designing anything, because three of them changed the design:

| Question | Measurement |
|---|---|
| Does `unicode61` find a word inside unspaced Chinese? | **No.** `中文分词 测试` matched nothing for `中文`; the sentence is one token |
| Does `trigram` find it? | **Yes, from three characters up.** `天气很` (3) matched; `很好`/`公园`/`散步` (2) matched nothing |
| Does `trigram` work under the catalog's `detail=column`? | **No.** `今天天气` (4) raised `fts5: phrase queries are not supported (detail!=full)` — a query longer than three characters is a phrase query |
| Does `detail=full` fix it? | **Yes.** `今天天气` matched. `detail=none` behaves like `column` |

So a trigram index is not a drop-in variant of the existing one: it needs a different
`detail` level, and it cannot answer a two-character query at all.

## Decision

1. **The tokenizer is recorded per document**, in `documents.tokenizer`, taken from the
   plugin at add time (`Catalog.add(..., tokenizer=...)`, default `unicode61`). It is
   not put in the container header: ADR-0007 froze `.lxz` v0, and a header field would
   change every archive's bytes for an index-side fact.
2. **Two FTS5 tables, one per tokenizer.** `documents_fts` is unchanged
   (`unicode61`, `detail=column` — the 6.4 % index cost measured for prose still
   applies). `documents_fts_trigram` is `trigram`, `detail=full`. A document is indexed
   into the table its tokenizer names; `search()` unions the rowids.
3. **Schema v2, migrated in place.** `documents` gains `tokenizer` (default
   `unicode61`) and `canonicalizer_version` (NULL = the frozen default label). An
   existing v1 catalog is opened and altered, not refused — a migration that makes a
   user re-ingest is not a migration.
4. **The plugin's provenance is recorded on the document row**, not only in the blob
   header. Blobs are content-addressed and deduplicated by SHA-256, so two documents
   cleaned by different plugins can legitimately share one blob; the header cannot hold
   both labels, and the row can.

## Consequences

- `zh-1` ships as `packages/lexora-lang-zh` with **no core change to discovery or to
  the canonicaliser**: the plugin registers through the entry point exactly as `hi`
  does, and the core still ships English only. The core change is the index, which is
  what the tokenizer *is*.
- `db add --language zh` canonicalises through the plugin, records `zh-1` on the row,
  and indexes the text into the trigram table.
- **Open work, stated rather than hidden:** a one- or two-character Chinese query
  returns nothing. The options are a bigram pre-segmentation of the body (so
  `unicode61` indexes characters), or a `LIKE '%…%'` fallback over live documents for
  short queries. Neither is built. A test pins the current behaviour so the floor is a
  decision rather than an accident.
- A tokenizer the catalog has no table for is **refused with an error naming the two it
  has**, not silently indexed as `unicode61`. A wrong index is a silent zero-result
  search, which is worse than a refusal.
