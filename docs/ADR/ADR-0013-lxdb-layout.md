# ADR-0013: `.lxdb` — single-file layout, and how a write commits

> **Status:** **PROPOSED — no byte layout, no code.** This ADR records the *shape* and the
> *mutation model* only. It deliberately contains no magic, no field widths, no offsets and
> no ordering, because [FORMAT_LXDB.md](../FORMAT_LXDB.md)'s gate **G2** is still open and
> the owner explicitly chose to respect it rather than override it (2026-11-07): *"run the
> protocol-scope benchmark first, then build `.lxdb` on measured ground."*
> **Date:** 2026-11-07
> **Deciders:** Owner Dr Sohil Momin (direction + mutation model delegated to this record)
> **Related:** [ADR-0010](ADR-0010-lxdb-direction.md) (block pool chosen as the successor) · [ADR-0016](ADR-0016-queryable-archive.md) (the working reference implementation this generalises) · [FORMAT_LXDB.md](../FORMAT_LXDB.md) (the gate) · [R6_PROTOCOL_SHAPED_2026-11-07.md](../R6_PROTOCOL_SHAPED_2026-11-07.md) (what is left to close G2) · [QUERY_ARCHIVE.md](../QUERY_ARCHIVE.md)

## Context / Problem

The owner's question was whether `.lxdb` could **replace SQLite** — one directly queryable
archive file instead of a directory of `.lxz` blobs plus a SQLite sidecar. ADR-0016 shipped
the sidecar design as the format-clean interim. This ADR records what the single-file
version should be, so that when G2 closes the work is a build rather than a design debate.

Two measurements shape it.

**The index can live inside the file, compressed.** A SQLite database serialises to a byte
image (`Connection.serialize()`). For the 19-document reference catalog: **1,437,696 bytes
of image → 389,352 bytes at zstd-9 (27 %)**, and opening from the compressed image plus
running a full-text query took **10 ms**. SQLite never compresses its own files, so this is
size the current design pays on disk for nothing.

**`deserialize()` is not available in this build** (it raises "unable to open database
file"), so opening means materialising the image to an unlinked temp file. At 10 ms that is
not a reason to avoid the design, but it is a reason not to depend on an API that is
present-but-nonfunctional.

## Decision drivers

- **One file.** A sidecar index can drift out of sync with the payload; a single file cannot.
- **Reproducible bytes.** Two runs over the same input must produce the same archive
  (REQ-CMP-003). A SQLite file with a WAL does not give that; a serialised, deterministic
  image does.
- **Density.** A shared block pool pays the 168-byte container overhead once instead of per
  document — the 91 %-overhead problem ADR-0010 measured on small documents.
- **Writes must not cost a rewrite of everything.** CHCE encodes at 0.4–0.5 MB/s; a
  full-file rewrite of a 1 GiB archive is ~35–40 minutes *per edit*.
- **Crash safety without inventing a journal.** The recovery story has to be small enough to
  be obviously correct.
- **Do not hand-roll a query engine.** SQL, query planning and BM25 are solved; the storage
  format is what is missing.

## Decision — the shape

1. **`.lxdb` is one file** holding: a superblock, a **compressed index image**, an
   **append-only payload area** of compressed blocks, and a segment directory.
2. **SQLite remains the query engine, embedded — not the file format.** The index image is
   a serialised SQLite database (documents table + contentless FTS5 at `detail=column`,
   per ADR-0016's measurement of 6.4 % of text). Opening an `.lxdb` materialises that image
   and queries run as real SQL. Reimplementing the query layer was rejected: it is months of
   work to arrive somewhere worse than the standard library.
3. **Payload blocks stay ordinary `.lxz` frames** with per-block SHA-256, so the existing
   reader, refusal classes and fuzz suite apply unchanged.
4. **No field widths in this ADR.** When G2 closes, the layout becomes a follow-up revision
   of this ADR with magic, widths, ordering and test vectors.

## Decision — how a write commits

**Recommended: append the payload, rewrite the index, commit by superblock flip.**

A write proceeds in three steps:

1. **Append** the new document's blocks to the payload area (append-only, never overwritten
   in place), with the segment's own hash recorded.
2. **Rewrite the index image** in full — the new version's row, the superseded marker on the
   old row — and compress it.
3. **Commit** by writing a new superblock that points at the new index image and the new
   payload high-water mark, with a generation counter and a SHA-256 over the index section.
   The superblock write is the only atomic step, and it is last.

**Why the index is rewritten while the payload is not.** The two have opposite cost
profiles. The payload is the bulk (a gigabyte) and rewriting it is minutes-to-hours at CHCE
speed. The index is ~7 % of the text and compresses to ~27 % of that, so rewriting it is a
sub-second operation even at 1 GiB — and it keeps the index a *single* contiguous object,
which removes an entire class of bug (two indexes to reconcile, as the ADR-0010 Option A
review warned).

**Rejected alternatives, and why:**

- **Rewrite the whole file atomically.** Simplest and fully crash-safe, but O(size) per
  write: 35–40 minutes to add one document to a 1 GiB archive at CHCE speed. Unusable.
- **In-place page updates** (free-list, page allocator, journal). This is reimplementing
  SQLite's B-tree layer by hand — the one part of this problem that is already solved, and
  the part most likely to lose data if got subtly wrong.
- **Append-only with no compaction.** File grows without bound and superseded documents are
  never reclaimed.

**Compaction** merges segments and drops dead versions when the dead ratio crosses a
threshold; it is the only lossy operation, it reports what it removed (as ADR-0016's
`compact()` does), and it is O(archive) because it must rewrite the payload.

## Consequences & trade-offs

**Positive.** One file; a compressed index (~73 % smaller than SQLite's on-disk form); a
block pool that fixes per-document overhead; byte-reproducible archives; and a crash-recovery
story that is one superblock flip rather than a journal.

**Negative / accepted risks.**

- **The index lives in RAM while open.** ~7 % of text uncompressed → ~70 MB for a gigabyte of
  text. Fine on the 4 GiB target, not free, and it must be stated in the resource limits.
- **Every commit rewrites the index.** Fine at 1 GiB, less fine at 50 GiB; the segment
  directory gives a future escape hatch, but the v1 story is "index in one piece".
- **Single writer, no concurrency.** Unchanged from ADR-0016; this is not a multi-user
  database and must never claim to be.
- **A new format to freeze and harden**, with new refusal classes (bad superblock, index
  image failing its hash, payload high-water mark beyond EOF, segment gaps). This is why the
  gate exists and why it is being respected.

## Impact analysis

| Dimension | Impact |
|---|---|
| Security | New parse surface (superblock, index image, segment directory) — needs the same validate-before-allocate discipline as `.lxz`, and the index image must be hash-checked before it is materialised |
| Performance | Open ~10 ms per 1.4 MB index image; queries unchanged; writes O(index) not O(payload) |
| Compatibility | New format; `.lxz` members remain readable and are embedded unchanged |
| Operations | One file to copy, back up and ship; `db compact` semantics carry over |

## Implementation & test implications

**Nothing may be implemented from this ADR** — it is direction, and FORMAT_LXDB's gate
forbids code. When G2 closes, the build order is: superblock + payload append with a
read-only reader; then index image serialisation and hash-checked materialisation; then
commit-by-flip with a crash-injection test (kill between append and flip, assert recovery to
the previous generation); then compaction. ADR-0016's `catalog.py` is the reference
implementation to generalise, and its test suite — stale reads, corrupted blobs, orphan
retention — is the floor the new format must also pass.
