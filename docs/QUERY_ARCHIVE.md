# The queryable archive — how to use it

`lexora db` turns a tree of documents into a **compressed archive you can query**: SQL
over metadata fields, full-text search inside the documents, and retrieval of only what
you asked for. Design and its trade-offs: [ADR-0016](ADR/ADR-0016-queryable-archive.md).

A catalog is a directory holding `catalog.sqlite` (the index) and `blobs/` (the documents,
as ordinary `.lxz` archives). Nothing new is invented in the storage format — see
[ADR-0016](ADR/ADR-0016-queryable-archive.md) for why that matters.

## Quick start

```bash
lexora db init  --root myarchive
lexora db add   --root myarchive --in book.txt --path "books/book.txt" \
                --title "Moby Dick" --meta lang=en --meta year=1851
lexora db search --root myarchive --query whale
lexora db search --root myarchive --filter lang=en --filter year=1851
lexora db get    --root myarchive "books/book.txt" --out moby.txt
lexora db stats  --root myarchive
```

`add` **canonicalises by default** (CAN-R01/R02/R05), so what is stored is the canonical
text — the same bytes `canon` would produce. Use `--no-canon` to store bytes as given.

## What it costs

Measured on 19 Project Gutenberg books (19.4 MB canonical):

| | |
|---|---|
| payload | 6.5 MB (ratio **0.335** at the zstd-9 default; ≈0.24 with `--codec ziptastic`) |
| index | 1.48 MB — **7.6 % of the text**, 22.7 % of the compressed payload |
| query (index only) | **0.34 s** |
| retrieve one document (decode + verify) | **0.47 s** |

The index is the price of queryability, and it is stored uncompressed on purpose: you
cannot search a compressed index without decompressing it, which defeats the point.
`db stats` reports it rather than hiding it.

## Searching

`--query` takes FTS5 syntax. **Phrase and NEAR search are not available** — the index is
built with `detail=column`, so `"captain ahab"` behaves as `captain AND ahab`. That is a
deliberate trade: positions would cost roughly 32 % of the text in index size.

Queries a user can actually type are safe: `C++`, `AND`, or an unbalanced quote return no
matches instead of an error.

`--filter key=value` matches a metadata field exactly (repeatable, ANDed with `--query`).
Metadata is stored as JSON per document, so any field you pass to `--meta` is filterable.

## Changing the archive

| Need | Command | What happens |
|---|---|---|
| add a document | `db add` | new blob + new row |
| edit a document | `db add` again with the same `--path` | **new version**; the old row is marked superseded and drops out of every query immediately |
| remove a document | `db delete --root DIR PATH` | tombstone; it disappears from `get` and `search`, bytes still on disk |
| reclaim space | `db compact --root DIR` | removes superseded/deleted rows and orphaned blobs, then **rebuilds the index** |
| check before reclaiming | `db compact --dry-run` | reports what *would* be removed, changes nothing |

`compact` is the only operation that destroys bytes, so it reports exactly what it
removed (`documents_removed`, `blobs_removed`, `bytes_freed`). It also re-verifies every
live document as it rebuilds the index — a compaction that succeeds is evidence the
archive is intact.

## Guarantees

- **Every returned byte is verified.** `get` decodes the `.lxz` and checks the result
  against the blob's SHA-256 before printing it. A damaged blob is refused, not served.
- **No stale reads.** Superseded and deleted documents never appear in `search` or `get`,
  even before `compact` runs.
- **Deduplication.** Identical content is stored once, whatever path it arrives under.
- **Crash safety.** The index is SQLite in WAL mode; a process killed mid-write rolls
  back to the last committed transaction. Blobs are written to a temp file and renamed.

## Known limits

- **One `.lxz` per document**, so each pays 168 bytes of container overhead plus 56 bytes
  per block. For a catalog of thousands of tiny documents that overhead dominates — the
  fix is `.lxdb` (ADR-0010/ADR-0013), not a tuning knob.
- **Compaction is O(archive)**: it decodes every live document to rebuild the index.
  Schedule it, do not run it casually.
- **Not a transactional database.** No concurrent writers, no row-level locking, no
  isolation levels. Single process, one writer, many readers.
- **Write speed follows the codec.** With `--codec ziptastic` (≈0.5 MB/s) this is an
  ingest-overnight archive, not an interactive one.

## GUI

The GUI is a client of these commands, per [ADR-0011](ADR/ADR-0011-gui-process-separation.md):
the search box, result list and preview pane all shell out to `lexora db`, and the
preview decodes only the selected document. The CLI surface above is therefore the
GUI's backend contract — it is complete and tested here, and the panel is the remaining
work.
