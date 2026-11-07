# ADR-0016: A queryable compressed archive — SQLite as index, lexora as payload

> **Status:** **Accepted 2026-11-07** — explicit owner direction ("used as database archive which is compressed and like sqlite it can run query and provide requested data", plus a GUI), with the two design questions answered by the owner: **documents with metadata filters *and* full-text inside them**, and **append + edit/delete + rebuild all required**.
> **Date:** 2026-11-07
> **Deciders:** Owner Dr Sohil Momin
> **Related:** [ADR-0010](ADR-0010-lxdb-direction.md) (`.lxdb` direction) · [ADR-0007](ADR-0007-container-v0-freeze.md) (`.lxz` v0) · [FORMAT_LXDB.md](../FORMAT_LXDB.md) (the G2 gate this ADR does *not* pre-empt) · [ADR-0015](ADR-0015-codec-policy.md) (codec policy) · [QUERY_ARCHIVE.md](../QUERY_ARCHIVE.md) (user guide)

## Context / Problem

The owner wants lexora to work as a compressed archive you can **query** — "like SQLite"
— returning only the data a query asks for, with a GUI on top. Two facts shaped the
design.

**The primitive already exists.** `.lxz` v0 carries a per-block index of
`(offset, compressed_size, uncompressed_size, sha256)`, per-block SHA-256, bounded decode
of a single block (`unpack --block N`), and flat-memory streaming decode. Random access
at block granularity is the one thing a compressed store must have, and lexora has it.

**But v0 has no document addressability and no index.** It is one logical stream split
into blocks, so "document 4,712" does not exist, and nothing answers "which documents
contain this word". A queryable archive needs both.

The obvious move — start writing `.lxdb` — is blocked by this project's own sequencing
rule: `FORMAT_LXDB.md` forbids any `.lxdb` byte layout until gate **G2** (a
protocol-scope benchmark run) closes, because freezing a layout before the benchmark that
would judge it is the error ADR-0007 avoided for `.lxz`. That gate is still open.

## Decision drivers

- **Ship the capability without pre-empting the format.** A query layer that writes no
  new bytes can land now; the storage optimisation can follow.
- **Queries must not decompress the world.** The index has to be queryable on its own.
- **Crash safety without inventing a WAL.** A store that can be written to needs atomic
  commit and recovery; writing that from scratch is a project, and getting it subtly
  wrong loses data.
- **The owner's mutation requirement is real** — append, edit, delete *and* rebuild.
- **No silent data loss.** The one operation that removes bytes must report what it took.
- **Measured, not assumed.** The cost of queryability is a number, and it had to be
  measured before the design was chosen.

## Options considered

- **A. One `.lxz` per document + a separate index file of our own.** Simplest storage,
  but it means writing and hardening a new index format — the thing we are least able to
  get right cheaply, and a second format to version.
- **B. One `.lxz` per document + SQLite as the index.** *(chosen)* The frozen `.lxz`
  reader is reused verbatim, and SQLite supplies querying, atomic commit and crash
  recovery from the standard library. No new byte layout, so the G2 gate is respected.
- **C. `.lxdb` block pool now.** Best eventual density (pays container overhead once,
  enables dedupe), but it *is* the frozen layout the gate forbids writing — and the
  benchmark that would judge it does not exist yet.
- **D. Store documents in SQLite as BLOBs.** One file, real transactions, but the payload
  becomes opaque to lexora's own verification path and the per-document container
  overhead problem stays. It also makes SQLite the thing holding the bulk text, which is
  exactly the job it is bad at.

## Decision

1. **SQLite is the index; lexora is the payload store.** A catalog is a directory holding
   `catalog.sqlite` and `blobs/<aa>/<sha256>.lxz`. Documents are ordinary `.lxz` v0
   archives — the frozen format, unchanged.
2. **Content-addressed blobs.** A blob is named by the SHA-256 of its canonical bytes, so
   identical content is stored once (measured: two paths with identical bytes → one blob).
3. **The index is contentless FTS5 + a metadata table.** `documents` holds path, version,
   title, a JSON metadata column and the blob reference; `documents_fts` is
   `content=''`, `detail=column`. **Measured cost: 6.4 % of the text** (1.17 MiB index for
   18.2 MiB of Gutenberg prose), against **140 %** when FTS5 stores the body inline. The
   rejected middle option — `detail=full`, which buys phrase/NEAR search — costs **38 %**
   and was judged not worth 32 points of text.
4. **Append-only underneath, mutable on top.** A new version is a new row and a new blob;
   the old row is marked superseded; a delete is a tombstone. Nothing is rewritten in
   place, so a crash loses at most the row in flight.
5. **`compact()` is the only lossy operation, and it reports.** It removes superseded and
   deleted rows, deletes orphaned blobs, and then **rebuilds the FTS index from live
   documents** — which doubles as the owner's "rebuild" mode and re-verifies every live
   blob on the way through.
6. **Every byte returned is verified.** `get()` decodes the `.lxz` and checks the result
   against the blob's SHA-256 before returning it, so a query can never hand back bytes
   the container did not verify.
7. **No new format bytes.** When `.lxdb` lands (ADR-0013), it replaces the *storage* under
   this index; the query surface and the CLI/GUI contract do not change.

## Consequences & trade-offs

**Positive.** The capability ships now, on a frozen format, with SQLite's crash safety
rather than a hand-rolled one. Dedupe is free from content addressing. Compaction
re-verifies the store as a side effect. And the `.lxdb` design gets to be an optimisation
with a working reference implementation to compare against, instead of a guess.

**Negative / accepted risks.**

- **The index is not free, and it is not compressed.** 6–8 % of text (≈23 % of the
  compressed payload at zstd-9). That is the price of queryability and it is reported by
  `db stats` rather than hidden.
- **No phrase or NEAR search.** `detail=column` keeps per-column scoping and drops
  positions, so `"captain ahab"` behaves as `captain AND ahab`. Buying phrases back costs
  ~32 % of the text in index size.
- **Compaction decodes every live document.** On a large archive that is slow — it is
  O(archive) work, and it is the operation you schedule, not the one you run casually.
- **One file per document.** The 91 %-overhead problem for tiny documents that ADR-0010
  measured is *unchanged* here; only `.lxdb` fixes it. A catalog of 10,000 one-line
  documents is still the wrong shape for this design.
- **CHCE makes writes slower, not faster.** At 0.5 MB/s the payload store is an ingest-
  overnight, query-all-day archive, not a transactional database.

## Impact analysis

| Dimension | Impact |
|---|---|
| Security | Positive: every returned byte is container-verified and hash-checked; filter keys are validated (no SQL injection through metadata keys); payload stays in a format with an existing fuzz suite |
| Performance | Query 0.34 s and retrieval 0.47 s on a 19-document / 19 MB catalog (index-only query; the decode is the retrieval cost) |
| Compatibility | None — writes only `.lxz` v0 archives, which every existing reader already handles |
| Operations | New verbs `db init/add/search/get/delete/compact/stats`; the GUI is a client of these (ADR-0011) |

## Implementation & test implications

`src/lexora/catalog.py` + `tests/test_catalog.py` (21 tests) + seven `db` verbs in
`src/lexora/cli.py`. The tests target the failures that make such a store untrustworthy
rather than the happy path: stale reads (superseded/deleted rows must never come back),
returning unverified bytes (a corrupted blob must be refused), `compact()` destroying a
blob a live document still needs (including a blob shared by two live documents), and FTS
queries a user can actually type (`C++`, `AND`, an unbalanced quote) returning no matches
instead of a traceback. Two of those tests caught real bugs during development — orphan
detection counting dead rows as references, so `bytes_freed` was always 0.
