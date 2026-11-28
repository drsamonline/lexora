"""A queryable compressed archive: SQLite as the index, lexora as the payload store.

What this is, and what it deliberately is not
----------------------------------------------
This is the "compressed database archive" in its first, format-clean form. Documents
are stored as ordinary `.lxz` v0 archives (the frozen format, ADR-0007) in a
content-addressed blob store, and a SQLite database next to them holds the index:
metadata columns you can filter with SQL, an FTS5 table you can full-text search, and
the mapping from each document to its blob.

Why not a new format: `FORMAT_LXDB.md` forbids writing `.lxdb` bytes until the
protocol-scope benchmark closes gate G2, and it is right to — freezing a layout before
the benchmark that would judge it is the sequencing error ADR-0007 avoided for `.lxz`.
Nothing here writes a new byte layout, so the feature ships without pre-empting
ADR-0013. When `.lxdb` lands, it replaces the *storage* under this same index; the
query surface does not change.

Why SQLite for the index rather than our own: the index must be queryable *without*
decompressing the payload, and it must be crash-safe when a process dies mid-write.
SQLite gives both (WAL, atomic commit) in the standard library. The irony is worth
stating plainly: the thing being built is "SQLite-like", and the fastest correct way
to get there is to let SQLite be the index and let lexora be the part SQLite is bad
at — storing the bulk text small.

The invariant that matters
--------------------------
Every byte returned by `get()` is decoded from a `.lxz` archive and then checked
against the blob's SHA-256 before it is handed back. A query never returns bytes that
the container has not verified, for the same reason `unpack` never writes unverified
output (REQ-SEC-004).

Mutation model
--------------
Append-only underneath, mutable on top: a new version of a document is a new row and
a new blob; the previous version is marked superseded; a delete is a tombstone. Nothing
is overwritten in place, so a crash mid-write loses at most the row that was in flight,
and `compact()` is the only operation that removes bytes — which makes it the only
operation that can lose data, and therefore the only one that reports what it removed.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from lexora import __version__, codec_registry, zstd_core
from lexora.container import (
    ContainerError,
    pack as lxz_pack,
    read_index,
    unpack as lxz_unpack,
)

SCHEMA_VERSION = 4

# Contentless (`content=''`): FTS5 stores the inverted index only, never a second
# uncompressed copy of the text. Measured on 18.2 MiB of Gutenberg prose this costs
# 6.4 % of the text at detail=column, against 140 % when the body is stored inline.
# detail=column keeps per-column scoping and gives up phrase/NEAR search — positions
# are what the other 32 % buys, and they are not worth it here.
# Contentless tables cannot be DELETEd from, so `compact()` drops and recreates this.
FTS_SCHEMA = (
    "CREATE VIRTUAL TABLE documents_fts USING fts5("
    "path, title, body, content='', detail=column, tokenize='unicode61')"
)

# The CJK index (ADR-0024). Same shape, two deliberate differences:
#
# * `trigram`, because Chinese and Japanese have no spaces and `unicode61` indexes a
#   whole sentence as one token — measured: `中文分词 测试` matched nothing for `中文`.
# * `detail=full`, because under `detail=column` every query longer than three
#   characters is a phrase query and FTS5 REFUSES those outright ("phrase queries are
#   not supported (detail!=full)"). `detail=none` behaves the same way. So the CJK
#   index cannot share the prose index's detail level; it is not a tuning choice.
#
# The cost is real and stated: positions are the other 32 % of the index, and a trigram
# index is larger again. It is paid only by documents whose plugin declares `trigram`.
FTS_TRIGRAM_SCHEMA = (
    "CREATE VIRTUAL TABLE documents_fts_trigram USING fts5("
    "path, title, body, content='', detail=full, tokenize='trigram')"
)

#: Which table a document is indexed into, by the tokenizer its plugin declares. A
#: tokenizer with no table is refused rather than quietly indexed as `unicode61`: a
#: wrong index is a silent zero-result search, which is worse than an error.
TOKENIZER_TABLES: dict[str, str] = {
    "unicode61": "documents_fts",
    "trigram": "documents_fts_trigram",
}
FTS_TABLES: tuple[str, ...] = tuple(TOKENIZER_TABLES.values())
DEFAULT_TOKENIZER = "unicode61"

#: The trigram floor (ADR-0024): the tokenizer indexes three-character sequences, so a
#: query of one or two characters cannot match ANY row of the trigram index. That is a
#: property of the tokenizer and it is measured, not assumed — the test suite queries
#: the FTS table directly to keep it true.
TRIGRAM_FLOOR = 3

#: The fallback of last resort for a short query: a substring scan over the live
#: documents that the trigram index holds. It is a scan, not an index, so it is bounded
#: in documents — and when the bound bites, `Catalog.last_search_truncated` says so
#: rather than letting a partial answer look like a complete one. Since schema v3 the
#: scan only covers documents the gram index below does not hold yet (a catalog built
#: before v3 that has not been backfilled, or a blob that failed verification).
SHORT_QUERY_SCAN_LIMIT = 1000

#: The longest query the gram index can answer: the trigram floor minus one. A gram is
#: one character (a unigram) or two (a bigram) of the case-folded path, title or text,
#: so a query of length 1 or 2 matches a gram EXACTLY — the same answer a substring test
#: would give, and the same answer the scan gave, without reading a single blob.
SHORT_QUERY_GRAM_MAX = TRIGRAM_FLOOR - 1

#: One row per GRAM, holding the packed ids of every document that holds it. Schema v4.
#:
#: v3 stored one row per (gram, document), and `benchmarks/gram_index_probe.py` measured
#: what that costs: on a 50-document corpus the v3 table is 6.6x the stored payload it
#: answers for, and 13.3x where bigrams recur across documents — against 2.2x and 1.8x
#: for this inverted shape, which is why the shape changed and the probe is committed
#: beside it. The ids are delta-coded LEB128 varints, so a posting list costs about one
#: byte per document instead of the ~14 bytes a v3 row cost. Unigrams and bigrams share
#: the table: a query says its own length, so the two cannot be confused.
#:
#: No hash is involved, deliberately. The probe found a 32-bit hash of the gram would
#: save nothing worth the risk (1.06x-1.19x against this shape's 2-3x) while turning an
#: exact answer into a candidate answer that has to be verified against the document.
GRAM_SCHEMA = (
    "CREATE TABLE IF NOT EXISTS doc_grams ("
    " gram TEXT PRIMARY KEY,"
    " postings BLOB NOT NULL) WITHOUT ROWID"
)

#: Which documents carry gram rows at all. One row per document, so "is this document
#: indexed" is a primary-key lookup rather than a scan of every posting list — and a
#: document whose blob failed verification is simply absent, which is what leaves it
#: uncovered for the scan to answer.
GRAM_DOC_SCHEMA = (
    "CREATE TABLE IF NOT EXISTS doc_gram_docs (doc_id INTEGER PRIMARY KEY)"
)

#: One row per document, holding the grams THAT document reached, front-coded.
#:
#: v4 made a delete a scan of every posting list in the table: `_grams_delete` could
#: only find the grams a document touched by decoding all of them, which is bounded by
#: the VOCABULARY (~15k rows on a 500-document catalog) rather than by the document.
#: `benchmarks/gram_delete_probe.py` measures what that costs and what this buys. The
#: digest is the v3 rows, per document, front-coded: grams are sorted and each is
#: written as the shared prefix length with its predecessor, then its remaining bytes,
#: so a run of bigrams sharing a first character costs ~1 byte of prefix each.
#:
#: It is a lookup table, never an authority: a posting left behind by a stale digest is
#: filtered by `_gram_rowids` at read time, and a document with no digest row (a v4
#: catalog written before this table existed) still deletes exactly, by the scan.
GRAM_DIGEST_SCHEMA = (
    "CREATE TABLE IF NOT EXISTS doc_gram_digest ("
    " doc_id INTEGER PRIMARY KEY,"
    " grams BLOB NOT NULL)"
)


def _varint_encode(value: int) -> bytes:
    """LEB128: 0-127 in one byte, 128-16383 in two, and so on."""
    out = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        out.append(byte | (0x80 if value else 0))
        if not value:
            return bytes(out)


def _varint_decode(blob: bytes) -> list[int]:
    values: list[int] = []
    shift = 0
    acc = 0
    for byte in blob:
        acc |= (byte & 0x7F) << shift
        if byte & 0x80:
            shift += 7
        else:
            values.append(acc)
            shift = 0
            acc = 0
    return values


def _pack_postings(doc_ids) -> bytes:
    """Sorted document ids, delta-coded: a run of consecutive ids costs one byte each."""
    out = bytearray()
    previous = 0
    for doc_id in sorted(set(doc_ids)):
        out += _varint_encode(doc_id - previous)
        previous = doc_id
    return bytes(out)


def _unpack_postings(blob: bytes) -> list[int]:
    """The ids `_pack_postings` wrote, in ascending order."""
    ids: list[int] = []
    previous = 0
    for delta in _varint_decode(blob):
        previous += delta
        ids.append(previous)
    return ids


def _varint_at(blob: bytes, pos: int) -> tuple[int, int]:
    """One LEB128 value from `blob` at `pos`, and where the next one starts."""
    value = 0
    shift = 0
    while True:
        byte = blob[pos]
        pos += 1
        value |= (byte & 0x7F) << shift
        if not byte & 0x80:
            return value, pos
        shift += 7


def _pack_grams(grams) -> bytes:
    """A document's grams, sorted and front-coded: prefix length, suffix, next.

    Sorted by code point, which for UTF-8 is sorted by byte, so neighbouring grams
    really do share a prefix (`今天`, `今天天`, ...). Nothing is hashed: the digest is a
    list of the exact keys the posting table is keyed by, so a delete that follows it
    cannot miss a gram it recorded.
    """
    out = bytearray()
    previous = b""
    for gram in sorted(grams):
        raw = gram.encode("utf-8")
        shared = 0
        limit = min(len(previous), len(raw))
        while shared < limit and previous[shared] == raw[shared]:
            shared += 1
        out += _varint_encode(shared)
        out += _varint_encode(len(raw) - shared)
        out += raw[shared:]
        previous = raw
    return bytes(out)


def _unpack_grams(blob: bytes) -> list[str]:
    """The grams `_pack_grams` wrote, in the order it wrote them."""
    grams: list[str] = []
    previous = b""
    pos = 0
    end = len(blob)
    while pos < end:
        shared, pos = _varint_at(blob, pos)
        suffix_len, pos = _varint_at(blob, pos)
        raw = previous[:shared] + blob[pos:pos + suffix_len]
        pos += suffix_len
        grams.append(raw.decode("utf-8"))
        previous = raw
    return grams


#: The zstd level the digest is stored at — the same level `add()` stores payloads at,
#: so the index does not carry a second, unexplained tuning knob.
DIGEST_LEVEL = 9


def _digest_pack(grams) -> bytes:
    """The stored form of a document's gram digest: front-coded, then one zstd frame.

    Front-coding alone leaves the digest at 4.1x the posting table it exists to save
    (`benchmarks/gram_delete_probe.py`), because a document's grams are mostly not
    adjacent in the vocabulary. Compressed, it is 0.86x the stored payload and 1.8x the
    posting table — 10 % of the whole index for a delete that touches the document
    instead of the vocabulary.
    """
    return zstd_core.compress(_pack_grams(grams), level=DIGEST_LEVEL)


def _digest_unpack(blob: bytes) -> list[str]:
    """The grams `_digest_pack` wrote."""
    return _unpack_grams(zstd_core.decompress(blob))
INDEX_NAME = "catalog.sqlite"
BLOB_DIR = "blobs"


class CatalogError(Exception):
    """Index or store failure. Distinct from ContainerError (payload) on purpose."""


@dataclass(frozen=True)
class Hit:
    """One search result. `text` is None unless the caller asked for the payload."""

    doc_id: int
    path: str
    version: int
    title: str | None
    metadata: dict
    canonical_bytes: int
    stored_bytes: int
    codec: str
    blob_sha256: str
    text: str | None = None

    def as_dict(self) -> dict:
        out = {
            "doc_id": self.doc_id,
            "path": self.path,
            "version": self.version,
            "title": self.title,
            "metadata": self.metadata,
            "canonical_bytes": self.canonical_bytes,
            "stored_bytes": self.stored_bytes,
            "codec": self.codec,
            "blob_sha256": self.blob_sha256,
        }
        if self.text is not None:
            out["text"] = self.text
        return out


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Catalog:
    """A directory holding `catalog.sqlite` plus a `blobs/` tree of `.lxz` archives."""

    def __init__(self, root: str | os.PathLike, *, create: bool = False) -> None:
        self.root = Path(root)
        self.index_path = self.root / INDEX_NAME
        self.blob_root = self.root / BLOB_DIR
        if not self.index_path.exists():
            if not create:
                raise CatalogError(
                    f"no catalog at {self.root} (run `lexora db init --root {self.root}`)"
                )
            self.root.mkdir(parents=True, exist_ok=True)
            self.blob_root.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.index_path))
        self._conn.row_factory = sqlite3.Row
        # Set by `_short_query_scan`: True when the last search could only look at part
        # of the CJK documents. Reset at the start of every `search()`.
        self.last_search_truncated = False
        # WAL: a reader can query while a writer appends, and a crash rolls back to
        # the last committed transaction instead of leaving a half-written index.
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        if create:
            self._create_schema()
        else:
            # An existing catalog is brought forward on OPEN, not only on create: the
            # verbs that matter (`add`, `search`) never call `_create_schema()`, so a
            # migration that lived there would only ever run on a brand-new directory.
            self._migrate()

    # -- lifecycle ---------------------------------------------------------

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> Catalog:
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def _create_schema(self) -> None:
        with self._conn:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS meta (
                    key   TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS blobs (
                    sha256          TEXT PRIMARY KEY,
                    archive_rel     TEXT NOT NULL,
                    archive_sha256  TEXT NOT NULL,
                    canonical_bytes INTEGER NOT NULL,
                    stored_bytes    INTEGER NOT NULL,
                    codec           TEXT NOT NULL,
                    created_at      TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS documents (
                    doc_id      INTEGER PRIMARY KEY AUTOINCREMENT,
                    path        TEXT NOT NULL,
                    version     INTEGER NOT NULL,
                    deleted     INTEGER NOT NULL DEFAULT 0,
                    superseded  INTEGER NOT NULL DEFAULT 0,
                    blob_sha256 TEXT NOT NULL REFERENCES blobs(sha256),
                    title       TEXT,
                    metadata    TEXT NOT NULL DEFAULT '{}',
                    added_at    TEXT NOT NULL,
                    tokenizer   TEXT NOT NULL DEFAULT 'unicode61',
                    canonicalizer_version TEXT,
                    UNIQUE(path, version)
                );
                CREATE INDEX IF NOT EXISTS documents_path ON documents(path);
                CREATE INDEX IF NOT EXISTS documents_live
                    ON documents(deleted, superseded);
                CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts
                    USING fts5(path, title, body, content='', detail=column,
                               tokenize='unicode61');
                CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts_trigram
                    USING fts5(path, title, body, content='', detail=full,
                               tokenize='trigram');
                """
            )
            self._conn.execute(GRAM_SCHEMA)
            self._conn.execute(GRAM_DOC_SCHEMA)
            self._conn.execute(GRAM_DIGEST_SCHEMA)
            self._migrate()
            self._conn.execute(
                "INSERT OR REPLACE INTO meta(key, value) VALUES ('schema_version', ?)",
                (str(SCHEMA_VERSION),),
            )
            self._conn.execute(
                "INSERT OR REPLACE INTO meta(key, value) VALUES ('lexora_version', ?)",
                (__version__,),
            )

    def _migrate(self) -> None:
        """Bring a schema-v1 catalog forward in place (ADR-0024).

        `CREATE TABLE IF NOT EXISTS` above does nothing to a table that already exists,
        so the two new columns arrive by `ALTER TABLE`. A migration that made a user
        re-ingest their documents would not be a migration, and the tokenizer of an
        existing document is not unknown: every one of them was indexed with
        `unicode61`, which is exactly the column default.
        """
        columns = {
            row["name"] for row in self._conn.execute("PRAGMA table_info(documents)")
        }
        if not columns:
            return  # no catalog here yet; `_create_schema()` builds the v2 shape
        tables = {
            row["name"]
            for row in self._conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        with self._conn:
            if "tokenizer" not in columns:
                self._conn.execute(
                    "ALTER TABLE documents ADD COLUMN tokenizer TEXT NOT NULL"
                    " DEFAULT 'unicode61'"
                )
            if "canonicalizer_version" not in columns:
                self._conn.execute(
                    "ALTER TABLE documents ADD COLUMN canonicalizer_version TEXT"
                )
            if "documents_fts_trigram" not in tables:
                self._conn.execute(FTS_TRIGRAM_SCHEMA)
            if "doc_grams" not in tables:
                # v3: the short-query gram index (ADR-0024's bigram pre-segmentation).
                # A catalog that already holds CJK documents gets it BACKFILLED here,
                # on open — the same rule the tokenizer column follows: a migration
                # that made a user re-ingest their documents would not be a migration.
                self._conn.execute(GRAM_SCHEMA)
                self._conn.execute(GRAM_DOC_SCHEMA)
                self._conn.execute(GRAM_DIGEST_SCHEMA)
                # A catalog with no posting table cannot have indexed documents, so a
                # coverage marker left behind by one (a table dropped, a restore of the
                # wrong file) is cleared rather than trusted: it would otherwise say
                # "indexed" for documents the index cannot answer for, and the scan
                # would never be asked.
                self._conn.execute("DELETE FROM doc_gram_docs")
                self._backfill_grams()
            else:
                self._conn.execute(GRAM_DOC_SCHEMA)
                # The digest table arrives for a catalog written by v4 before it existed.
                # It is created BEFORE the repack below, because `_repack_grams` writes
                # the digests it can derive from the v3 rows it is already walking.
                digest_missing = "doc_gram_digest" not in tables
                if digest_missing:
                    self._conn.execute(GRAM_DIGEST_SCHEMA)
                gram_columns = {
                    row["name"]
                    for row in self._conn.execute("PRAGMA table_info(doc_grams)")
                }
                repacked = False
                if {"gram", "doc_id"} <= gram_columns:
                    # v3 -> v4: one row per (gram, document) becomes one posting list
                    # per gram. A pure in-database transform: no blob is read, because
                    # the v3 table already holds every gram.
                    self._repack_grams()
                    repacked = True
                # v4 -> v4 + digest: a catalog written before the digest table existed
                # has posting lists but no per-document list of the grams they name, so
                # a delete would have to walk the vocabulary. One scan here inverts the
                # postings into digests, and every later delete is bounded by the
                # document instead. A v3 table was repacked above and has its digests
                # written by `_repack_grams`, so this only runs on a pre-digest v4.
                if digest_missing and not repacked:
                    self._backfill_gram_digests()
            # The version is part of the migration, not a cosmetic stamp: a catalog
            # that has the v2 shape and says v1 is a catalog nobody can reason about.
            self._conn.execute(
                "INSERT OR REPLACE INTO meta(key, value) VALUES ('schema_version', ?)",
                (str(SCHEMA_VERSION),),
            )

    @staticmethod
    def _table_for(tokenizer: str) -> str:
        """The FTS table for `tokenizer`, or a refusal naming the ones there are."""
        try:
            return TOKENIZER_TABLES[tokenizer]
        except KeyError:
            raise CatalogError(
                f"no index for tokenizer {tokenizer!r}; this catalog can index "
                f"{', '.join(sorted(TOKENIZER_TABLES))} (ADR-0024). Indexing it as "
                "`unicode61` would return nothing and say nothing."
            ) from None

    # -- payload store -----------------------------------------------------

    def _fts_insert(
        self, doc_id: int, path: str, title: str | None, body: str,
        tokenizer: str = DEFAULT_TOKENIZER,
    ) -> None:
        table = self._table_for(tokenizer)
        self._conn.execute(
            f"INSERT INTO {table}(rowid, path, title, body) VALUES (?,?,?,?)",
            (doc_id, path, title or "", body),
        )

    def _fts_delete(self, doc_id: int, path: str, title: str | None, body: str,
                    tokenizer: str = DEFAULT_TOKENIZER) -> None:
        """Remove one row from a contentless FTS table.

        Contentless tables cannot `DELETE`; FTS5 requires the original column values
        back, which is why the body is decoded from its blob here. Callers treat this
        as best-effort: a stale index row is harmless (search joins on live rows and
        `compact()` rebuilds the index outright), whereas failing an `add` because an
        old blob went missing would not be.
        """
        table = self._table_for(tokenizer)
        self._conn.execute(
            f"INSERT INTO {table}({table}, rowid, path, title, body)"
            " VALUES ('delete', ?, ?, ?, ?)",
            (doc_id, path, title or "", body),
        )

    # -- the short-query gram index (ADR-0024) ------------------------------

    @staticmethod
    def _grams(text: str) -> set[str]:
        """Every one- and two-character sequence of `text`, case-folded.

        Folding first is what makes an index lookup the same question the scan asked:
        the scan compares `needle.casefold()` against `haystack.casefold()`, so a gram
        is a slice of the FOLDED text, not of the text.
        """
        folded = text.casefold()
        grams = set(folded)
        grams.update(folded[i:i + 2] for i in range(len(folded) - 1))
        return grams

    def _grams_insert(self, doc_id: int, path: str, title: str | None, body: str,
                      tokenizer: str = DEFAULT_TOKENIZER) -> None:
        """Record a document's grams — only for documents the trigram index holds.

        A `unicode61` document is the prose index's job: it indexes whole words, so a
        one- or two-character query against it is a word query the index answers, and
        giving it grams would answer for a document the short-query path never asked
        about.
        """
        if tokenizer != "trigram":
            return
        grams = self._grams(path) | self._grams(title or "") | self._grams(body)
        self._grams_write(doc_id, grams)

    def _grams_write(self, doc_id: int, grams: set[str]) -> None:
        """Merge one document's id into every posting list it belongs in.

        The coverage marker is written last and only when there is a gram to write, so
        `doc_gram_docs` never claims a document the posting lists cannot answer for.
        """
        for gram in grams:
            row = self._conn.execute(
                "SELECT postings FROM doc_grams WHERE gram = ?", (gram,)
            ).fetchone()
            ids = _unpack_postings(row["postings"]) if row else []
            if doc_id in ids:
                continue  # already recorded: a re-add of the same document is a no-op
            ids.append(doc_id)
            self._conn.execute(
                "INSERT INTO doc_grams(gram, postings) VALUES (?, ?)"
                " ON CONFLICT(gram) DO UPDATE SET postings = excluded.postings",
                (gram, _pack_postings(ids)),
            )
        if grams:
            # The digest is written in the same transaction as the postings it
            # describes, so a delete can follow it without re-deriving it — and it is
            # replaced rather than merged: it is this document's grams, not a history.
            self._conn.execute(
                "INSERT OR REPLACE INTO doc_gram_digest(doc_id, grams) VALUES (?, ?)",
                (doc_id, _digest_pack(grams)),
            )
            self._conn.execute(
                "INSERT OR IGNORE INTO doc_gram_docs(doc_id) VALUES (?)", (doc_id,)
            )

    def _grams_delete(self, doc_id: int) -> None:
        """Remove one document's id from every posting list it reached.

        A posting list that loses its last id is dropped rather than left empty: an
        empty list would answer "no documents" for a gram no document holds, which is
        the same answer a missing row gives — but it would also make the gram count in
        `stats()` claim an index larger than the one that is there.

        WHICH POSTING LISTS are the document's is answered by its digest row, so the
        cost of a delete is the size of the DOCUMENT, not the size of the vocabulary.
        Without a digest row the old path is taken: a scan of every posting list, which
        is exact but bounded by the vocabulary. That is not a legacy branch kept for
        sentiment — a v4 catalog written before the digest table existed has posting
        lists and no digests, and it must still delete correctly.
        """
        digest = self._conn.execute(
            "SELECT grams FROM doc_gram_digest WHERE doc_id = ?", (doc_id,)
        ).fetchone()
        if digest is None:
            self._grams_delete_scan(doc_id)
        else:
            try:
                grams = _digest_unpack(digest["grams"])
            except (zstd_core.CodecError, UnicodeDecodeError):
                # A digest is an accelerator, never the authority: a byte flipped in the
                # stored blob must not make a document undeletable. Drop the unreadable
                # row and take the exact-but-slower path.
                grams = None
                self._conn.execute(
                    "DELETE FROM doc_gram_digest WHERE doc_id = ?", (doc_id,)
                )
            if grams is None:
                self._grams_delete_scan(doc_id)
            else:
                for gram in grams:
                    self._grams_delete_from(gram, doc_id)
                self._conn.execute(
                    "DELETE FROM doc_gram_digest WHERE doc_id = ?", (doc_id,)
                )
        self._conn.execute("DELETE FROM doc_gram_docs WHERE doc_id = ?", (doc_id,))

    def _grams_delete_from(self, gram: str, doc_id: int) -> None:
        """Drop one id from one posting list, removing the list when it empties."""
        row = self._conn.execute(
            "SELECT postings FROM doc_grams WHERE gram = ?", (gram,)
        ).fetchone()
        if row is None:
            return
        ids = _unpack_postings(row["postings"])
        if doc_id not in ids:
            return
        rest = [other for other in ids if other != doc_id]
        if rest:
            self._conn.execute(
                "UPDATE doc_grams SET postings = ? WHERE gram = ?",
                (_pack_postings(rest), gram),
            )
        else:
            self._conn.execute("DELETE FROM doc_grams WHERE gram = ?", (gram,))

    def _grams_delete_scan(self, doc_id: int) -> None:
        """The digestless delete: every posting list is decoded to find the document.

        Exact, and bounded by the vocabulary rather than by the document. Kept because
        a catalog can legitimately have postings and no digests (written by v4 before
        this table existed, or restored from such a file), and `_backfill_gram_digests`
        turns that case into the fast one on the next open.
        """
        for row in list(self._conn.execute("SELECT gram FROM doc_grams")):
            self._grams_delete_from(row["gram"], doc_id)

    def _gram_rowids(self, folded: str) -> set[int]:
        """Documents holding `folded` as a gram. Exact for a needle of length 1 or 2.

        One primary-key lookup and one decode: the cost is the size of the ANSWER, not
        the size of the corpus, which is the property v3 had and this keeps. A posting
        that names a document that is no longer live is filtered here rather than
        trusted — `_unindex` is best-effort for the FTS row and this must not inherit
        that.
        """
        row = self._conn.execute(
            "SELECT postings FROM doc_grams WHERE gram = ?", (folded,)
        ).fetchone()
        if row is None:
            return set()
        live = {
            r["doc_id"]
            for r in self._conn.execute(
                "SELECT doc_id FROM documents WHERE deleted = 0 AND superseded = 0"
            )
        }
        return {doc_id for doc_id in _unpack_postings(row["postings"]) if doc_id in live}

    #: The live trigram documents, and how many there are. Shared by the gram index's
    #: backfill and the scan so the two can never disagree about which documents the
    #: short-query path is responsible for.
    _LIVE_TRIGRAM_WHERE = (
        " FROM documents d JOIN blobs b ON b.sha256 = d.blob_sha256"
        " WHERE d.deleted = 0 AND d.superseded = 0 AND d.tokenizer = 'trigram'"
    )

    def _live_trigram_rows(self, limit: int | None = None) -> tuple[list, int]:
        total = self._conn.execute(
            "SELECT COUNT(*)" + self._LIVE_TRIGRAM_WHERE
        ).fetchone()[0]
        sql = (
            "SELECT d.doc_id, d.path, d.title, d.blob_sha256, b.archive_rel"
            + self._LIVE_TRIGRAM_WHERE
            + " ORDER BY d.doc_id"
        )
        if limit is None:
            return list(self._conn.execute(sql)), total
        return list(self._conn.execute(sql + " LIMIT ?", (limit,))), total

    def _gram_uncovered(self) -> tuple[list, int]:
        """Live trigram documents with no grams yet, and how many there are.

        This is the honest definition of "what the index cannot answer": a document
        with no row in `doc_gram_docs`. Every document has a path, so a gram-indexed
        document always has at least one gram — a missing marker means "not indexed",
        never "indexed and empty".
        """
        where = (
            self._LIVE_TRIGRAM_WHERE
            + " AND NOT EXISTS (SELECT 1 FROM doc_gram_docs x WHERE x.doc_id = d.doc_id)"
        )
        total = self._conn.execute("SELECT COUNT(*)" + where).fetchone()[0]
        rows = self._conn.execute(
            "SELECT d.doc_id, d.path, d.title, d.blob_sha256, b.archive_rel" + where
            + " ORDER BY d.doc_id LIMIT ?",
            (SHORT_QUERY_SCAN_LIMIT,),
        ).fetchall()
        return list(rows), total

    def _backfill_grams(self) -> None:
        """Build the gram index for documents that predate it (schema v2 -> v3).

        Called from `_migrate`, so it runs on OPEN of an older catalog: the same rule
        the tokenizer column follows — a migration that made the owner re-ingest their
        documents would not be a migration. One pass, unbounded, and a blob that fails
        verification is left uncovered rather than failing the open: the scan still
        answers for it.
        """
        rows, _ = self._live_trigram_rows()
        missing = [r for r in rows if not self._conn.execute(
            "SELECT 1 FROM doc_gram_docs WHERE doc_id = ? LIMIT 1", (r["doc_id"],)
        ).fetchone()]
        with self._conn:
            for row in missing:
                try:
                    body = self._read_verified_blob(
                        row["blob_sha256"], row["archive_rel"]
                    ).decode("utf-8", "replace")
                except CatalogError:
                    continue
                self._grams_insert(row["doc_id"], row["path"], row["title"], body,
                                   "trigram")

    def _repack_grams(self) -> None:
        """v3 -> v4: one row per (gram, document) becomes one posting list per gram.

        No blob is read — the v3 table already holds every gram, so this is a pure
        in-database transform. The coverage marker is written from the documents the v3
        rows actually named, so a v3 catalog that was half backfilled stays half
        backfilled instead of being declared indexed.
        """
        by_gram: dict[str, list[int]] = {}
        docs: set[int] = set()
        # The v3 rows are the only authority here: a digest left over from a previous
        # v4 shape describes documents this table no longer holds.
        self._conn.execute("DELETE FROM doc_gram_digest")
        for row in self._conn.execute("SELECT gram, doc_id FROM doc_grams"):
            by_gram.setdefault(row["gram"], []).append(row["doc_id"])
            docs.add(row["doc_id"])
        self._conn.execute("DROP TABLE doc_grams")
        self._conn.execute(GRAM_SCHEMA)
        self._conn.executemany(
            "INSERT INTO doc_grams(gram, postings) VALUES (?, ?)",
            ((gram, _pack_postings(ids)) for gram, ids in by_gram.items()),
        )
        self._conn.executemany(
            "INSERT OR IGNORE INTO doc_gram_docs(doc_id) VALUES (?)",
            ((doc_id,) for doc_id in sorted(docs)),
        )
        # The v3 rows are also the digests, inverted: each document's own grams. Taken
        # from the rows that were there, so a half-backfilled v3 gets digests for
        # exactly the documents it had grams for.
        by_doc: dict[int, set[str]] = {}
        for gram, ids in by_gram.items():
            for doc_id in ids:
                by_doc.setdefault(doc_id, set()).add(gram)
        self._conn.executemany(
            "INSERT OR REPLACE INTO doc_gram_digest(doc_id, grams) VALUES (?, ?)",
            ((doc_id, _digest_pack(grams)) for doc_id, grams in sorted(by_doc.items())),
        )

    def _backfill_gram_digests(self) -> None:
        """Invert the posting lists into per-document digests, once, on open.

        Called from `_migrate` only when the digest table was absent — a catalog
        written by v4 before the table existed. No blob is read: the postings already
        name every (gram, document) pair. The one scan this costs is paid at open, once,
        and it is the same scan every delete used to pay.
        """
        by_doc: dict[int, set[str]] = {}
        for row in self._conn.execute("SELECT gram, postings FROM doc_grams"):
            for doc_id in _unpack_postings(row["postings"]):
                by_doc.setdefault(doc_id, set()).add(row["gram"])
        self._conn.executemany(
            "INSERT OR REPLACE INTO doc_gram_digest(doc_id, grams) VALUES (?, ?)",
            ((doc_id, _digest_pack(grams)) for doc_id, grams in sorted(by_doc.items())),
        )

    def _unindex(self, doc_id: int, path: str, title: str | None, sha: str, rel: str,
                 tokenizer: str = DEFAULT_TOKENIZER) -> None:
        # The grams need no blob and cannot fail, so they go first: a document that is
        # no longer live must leave the short-query index even when its payload has
        # already gone missing.
        self._grams_delete(doc_id)
        try:
            body = self._read_verified_blob(sha, rel).decode("utf-8", "replace")
            self._fts_delete(doc_id, path, title, body, tokenizer)
        except (CatalogError, sqlite3.Error):
            # Leave the row; `compact()` rebuilds the index from live documents.
            pass

    def _blob_path(self, sha: str) -> Path:
        return self.blob_root / sha[:2] / f"{sha}.lxz"

    def _store_blob(self, canonical: bytes, *, codec: str, level: int) -> tuple[str, str]:
        """Write canonical bytes as one `.lxz`, content-addressed. Returns (sha, rel)."""
        sha = hashlib.sha256(canonical).hexdigest()
        existing = self._conn.execute(
            "SELECT archive_rel FROM blobs WHERE sha256 = ?", (sha,)
        ).fetchone()
        if existing:
            return sha, existing["archive_rel"]  # dedupe: identical content stored once

        archive = lxz_pack(canonical, level=level, codec=codec)
        rel = f"{BLOB_DIR}/{sha[:2]}/{sha}.lxz"
        target = self.root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix(".lxz.tmp")
        tmp.write_bytes(archive)
        os.replace(tmp, target)  # atomic: a reader never sees a partial blob
        return sha, rel

    # -- mutation ----------------------------------------------------------

    def add(
        self,
        path: str,
        canonical: bytes,
        *,
        title: str | None = None,
        metadata: dict | None = None,
        codec: str = codec_registry.DEFAULT_CODEC,
        level: int = 9,
        tokenizer: str = DEFAULT_TOKENIZER,
        canonicalizer_version: str | None = None,
    ) -> Hit:
        """Append a version of `path`. Previous versions are superseded, not removed.

        `tokenizer` is the one the document's language plugin declares (ADR-0024); it
        decides which FTS table the text is indexed into, and is recorded on the row so
        a later rebuild knows without re-reading the plugin. `canonicalizer_version`
        records which plugin's rules produced `canonical` — the row is the only place
        that can hold it, because blobs are deduplicated by SHA-256 and two plugins can
        legitimately produce the same bytes.
        """
        if not isinstance(canonical, bytes):
            raise CatalogError("add() expects canonical bytes, not str")
        self._table_for(tokenizer)  # refuse an unindexable tokenizer before writing
        meta = metadata or {}
        try:
            meta_json = json.dumps(meta, sort_keys=True)
        except TypeError as exc:
            raise CatalogError(f"metadata must be JSON-serialisable: {exc}") from exc

        sha, rel = self._store_blob(canonical, codec=codec, level=level)
        info, _, _ = read_index((self.root / rel).read_bytes())
        stored = (self.root / rel).stat().st_size
        archive_sha = hashlib.sha256((self.root / rel).read_bytes()).hexdigest()

        with self._conn:
            self._conn.execute(
                "INSERT OR IGNORE INTO blobs"
                "(sha256, archive_rel, archive_sha256, canonical_bytes, stored_bytes,"
                " codec, created_at) VALUES (?,?,?,?,?,?,?)",
                (sha, rel, archive_sha, len(canonical), stored, info.codec_id, _now()),
            )
            row = self._conn.execute(
                "SELECT COALESCE(MAX(version), 0) AS v FROM documents WHERE path = ?",
                (path,),
            ).fetchone()
            version = row["v"] + 1
            # supersede every live version of this path, and drop its FTS rows so a
            # search can never return text that is no longer current
            old = list(self._conn.execute(
                "SELECT d.doc_id, d.path, d.title, d.blob_sha256, d.tokenizer,"
                " b.archive_rel"
                " FROM documents d JOIN blobs b ON b.sha256 = d.blob_sha256"
                " WHERE d.path = ? AND d.superseded = 0",
                (path,),
            ))
            for row in old:
                self._conn.execute(
                    "UPDATE documents SET superseded = 1 WHERE doc_id = ?", (row["doc_id"],)
                )
                self._unindex(row["doc_id"], row["path"], row["title"],
                              row["blob_sha256"], row["archive_rel"],
                              row["tokenizer"])
            cur = self._conn.execute(
                "INSERT INTO documents"
                "(path, version, blob_sha256, title, metadata, added_at, tokenizer,"
                " canonicalizer_version)"
                " VALUES (?,?,?,?,?,?,?,?)",
                (path, version, sha, title, meta_json, _now(), tokenizer,
                 canonicalizer_version),
            )
            doc_id = int(cur.lastrowid)
            self._fts_insert(doc_id, path, title,
                             canonical.decode("utf-8", "replace"), tokenizer)
            self._grams_insert(doc_id, path, title,
                               canonical.decode("utf-8", "replace"), tokenizer)

        return Hit(
            doc_id=doc_id, path=path, version=version, title=title, metadata=meta,
            canonical_bytes=len(canonical), stored_bytes=stored,
            codec=info.codec_id, blob_sha256=sha,
        )

    def delete(self, path: str) -> int:
        """Tombstone every live version of `path`. Returns rows affected (0 = absent)."""
        with self._conn:
            rows = list(self._conn.execute(
                "SELECT d.doc_id, d.path, d.title, d.blob_sha256, d.tokenizer,"
                " b.archive_rel"
                " FROM documents d JOIN blobs b ON b.sha256 = d.blob_sha256"
                " WHERE d.path = ? AND d.deleted = 0",
                (path,),
            ))
            for row in rows:
                self._conn.execute(
                    "UPDATE documents SET deleted = 1 WHERE doc_id = ?", (row["doc_id"],)
                )
                self._unindex(row["doc_id"], row["path"], row["title"],
                              row["blob_sha256"], row["archive_rel"],
                              row["tokenizer"])
        return len(rows)

    # -- query -------------------------------------------------------------

    def get(self, path_or_id: str | int, *, text: bool = True) -> Hit | None:
        """Fetch one live document by path or doc_id, decoding and verifying it."""
        if isinstance(path_or_id, int):
            row = self._conn.execute(
                "SELECT d.*, b.canonical_bytes, b.stored_bytes, b.codec, b.archive_rel"
                " FROM documents d JOIN blobs b ON b.sha256 = d.blob_sha256"
                " WHERE d.doc_id = ? AND d.deleted = 0 AND d.superseded = 0",
                (path_or_id,),
            ).fetchone()
        else:
            row = self._conn.execute(
                "SELECT d.*, b.canonical_bytes, b.stored_bytes, b.codec, b.archive_rel"
                " FROM documents d JOIN blobs b ON b.sha256 = d.blob_sha256"
                " WHERE d.path = ? AND d.deleted = 0 AND d.superseded = 0",
                (path_or_id,),
            ).fetchone()
        if row is None:
            return None
        body = None
        if text:
            raw = self._read_verified_blob(row["blob_sha256"], row["archive_rel"])
            body = raw.decode("utf-8", "replace")
        return Hit(
            doc_id=row["doc_id"], path=row["path"], version=row["version"],
            title=row["title"], metadata=json.loads(row["metadata"]),
            canonical_bytes=row["canonical_bytes"], stored_bytes=row["stored_bytes"],
            codec=row["codec"], blob_sha256=row["blob_sha256"], text=body,
        )

    def _read_verified_blob(self, sha: str, rel: str) -> bytes:
        """Decode a blob and check it against the index hash before trusting it."""
        target = self.root / rel
        if not target.exists():
            raise CatalogError(f"blob missing from store: {rel}")
        try:
            payload = lxz_unpack(target.read_bytes())
        except ContainerError as exc:
            raise CatalogError(f"blob {sha[:12]}… failed container verification: {exc}") from exc
        if hashlib.sha256(payload).hexdigest() != sha:
            raise CatalogError(
                f"blob {sha[:12]}… decoded to content with a different SHA-256 — "
                "refusing to return it"
            )
        return payload

    def _fts_rowids(self, query: str) -> list[int]:
        """Rowids matching `query`, degrading gracefully instead of raising.

        FTS5 raises on syntax it does not understand, and users type things like
        `self-attention`, `C++`, `AND`, or an unbalanced quote. Three attempts, in
        order of how much they preserve the user's intent:

        1. the query as given, so real FTS syntax (`a OR b`, `title:x`, `foo*`) works;
        2. the query **reduced to its word tokens, ANDed** — this is what rescues
           `self-attention`, which FTS5 reads as a syntax error rather than as two
           words;
        3. a single quoted token, for a one-word query that FTS5 still objects to.

        A quoted *phrase* is deliberately not an attempt: this index is built with
        `detail=column`, which stores no positions, so a multi-word phrase matches
        nothing at all — a silent zero-result failure, which is worse than an error.
        """
        for candidate in (query, self._and_of_tokens(query), self._single_token(query)):
            if not candidate:
                continue
            found: set[int] = set()
            raised = False
            for table in FTS_TABLES:
                try:
                    found.update(
                        r["rowid"]
                        for r in self._conn.execute(
                            f"SELECT rowid FROM {table} WHERE {table} MATCH ?",
                            (candidate,),
                        )
                    )
                except sqlite3.OperationalError:
                    # One index rejecting the query must not hide the other's answer:
                    # `trigram` refuses anything shorter than three characters, and a
                    # mixed catalog is the normal case now (ADR-0024).
                    raised = True
            if found:
                return sorted(found)
            if not raised:
                # The index understood the query and had no match. That is an answer,
                # so the next candidate (a looser reading of the same text) is not
                # tried — exactly as before.
                break
        # Nothing matched, and the trigram index has now said why it could not help: a
        # query shorter than three characters has no trigram to match. Answer it from
        # the gram index instead of returning the silent zero this fallback exists to
        # remove, and from the documents themselves only for what the index lacks.
        return self._short_query(query)

    def _short_query(self, query: str) -> list[int]:
        """Rowids for a query below `TRIGRAM_FLOOR` — from the gram index, first.

        ADR-0024 named two ways off the trigram floor. The scan was built first
        (2026-11-21) because it needs no re-ingestion and so works on catalogs that
        already exist; this is the second — the bigram pre-segmentation the ADR left
        open — and it is now the path a short query takes. A one- or two-character
        query is a gram lookup, so its cost is the size of the ANSWER rather than the
        size of the corpus, and it cannot be truncated.

        The scan is kept for the two cases an index genuinely cannot answer:

        * a document the gram index does not hold yet — one written by a catalog that
          was never backfilled, or a blob that failed verification;
        * a needle whose *folded* form is longer than two characters (`ß` folds to
          `ss`, `ﬃ` to `ffi`), which no unigram or bigram can represent.

        `last_search_truncated` is about the part that was SCANNED, not about the
        answer: an index hit is complete, so a bounded scan alongside it must not make
        a complete result look partial — the failure this flag exists to prevent is the
        opposite one.
        """
        needle = query.strip()
        if not needle or len(needle) >= TRIGRAM_FLOOR:
            return []
        folded = needle.casefold()
        if len(folded) > SHORT_QUERY_GRAM_MAX:
            return self._short_query_scan(query)
        found = self._gram_rowids(folded)
        missing, total_missing = self._gram_uncovered()
        if missing:
            found |= set(self._scan_rows(missing, folded))
            self.last_search_truncated = total_missing > len(missing)
        return sorted(found)

    def _scan_rows(self, rows: list, folded: str) -> list[int]:
        """Rowids among `rows` whose path, title or text contains `folded`.

        The match is **literal**, not FTS syntax: `%` and `_` are characters, not
        wildcards, because this is a substring test in Python rather than a `LIKE`
        pattern built out of user text. A blob that fails verification is skipped, not
        fatal: one damaged document must not turn every short query into an error.
        """
        found: list[int] = []
        for row in rows:
            haystacks = [row["path"] or "", row["title"] or ""]
            try:
                haystacks.append(
                    self._read_verified_blob(row["blob_sha256"], row["archive_rel"])
                    .decode("utf-8", "replace")
                )
            except CatalogError:
                continue
            if any(folded in h.casefold() for h in haystacks):
                found.append(row["doc_id"])
        return found

    def _short_query_scan(self, query: str) -> list[int]:
        """Rowids of live CJK documents whose text contains `query` literally.

        ADR-0024 recorded the trigram floor as open work and named two ways off it: a
        bigram pre-segmentation of the body, or a short-query scan over live documents.
        This is the scan — the one that needs no re-ingestion of anything already
        stored, so it works on catalogs built before it existed.

        What it is and is not:

        * It answers only queries the index genuinely cannot: the needle is the whole
          query, stripped, and nothing shorter than `TRIGRAM_FLOOR` is scanned.
        * It is **literal**, not FTS syntax. `%` and `_` are characters, not wildcards,
          because the match is a substring test in Python rather than a `LIKE` pattern
          built out of user text — a query of `%` finds documents containing `%` and
          nothing else.
        * It is **bounded** in documents (`SHORT_QUERY_SCAN_LIMIT`), and it says when
          the bound bit. A bounded scan that stayed quiet would be the same silent
          partial answer as the zero it replaces.
        * A blob that fails verification is skipped, not fatal: one damaged document
          must not turn every short query into an error.
        """
        needle = query.strip()
        if not needle or len(needle) >= TRIGRAM_FLOOR:
            return []
        rows, total = self._live_trigram_rows(SHORT_QUERY_SCAN_LIMIT)
        self.last_search_truncated = total > len(rows)
        return self._scan_rows(rows, needle.casefold())

    @staticmethod
    def _and_of_tokens(query: str) -> str | None:
        """`self-attention` -> `self AND attention`; None when there are no words."""
        tokens = [t for t in re.split(r"\W+", query, flags=re.UNICODE) if t]
        if len(tokens) < 2:
            return None
        return " AND ".join(f'"{t}"' for t in tokens)

    @staticmethod
    def _single_token(query: str) -> str | None:
        tokens = [t for t in re.split(r"\W+", query, flags=re.UNICODE) if t]
        if len(tokens) != 1:
            return None
        return f'"{tokens[0]}"'

    def search(
        self,
        query: str | None = None,
        *,
        filters: dict | None = None,
        limit: int = 20,
        with_text: bool = False,
    ) -> list[Hit]:
        """Full-text + metadata query over live documents.

        `query` uses FTS5 syntax. A query that FTS5 cannot parse is retried as a
        quoted phrase rather than raising — a user typing `C++` or an unbalanced
        quote should get no results, not a stack trace.

        A query shorter than `TRIGRAM_FLOOR` that no index can answer is answered from
        the per-document gram index (ADR-0024's bigram pre-segmentation), and only for
        documents that index does not hold yet by a bounded literal scan of them.
        Check `last_search_truncated` afterwards: True means the scan hit its document
        bound and the answer is partial.
        """
        self.last_search_truncated = False
        where = ["d.deleted = 0", "d.superseded = 0"]
        params: list = []
        for key, value in (filters or {}).items():
            # ASCII word chars only. `isalnum()` alone accepts Unicode letters,
            # which would put arbitrary codepoints inside a JSON path expression —
            # not exploitable today, but the guard should be as narrow as the job.
            if not re.fullmatch(r"[A-Za-z0-9_]+", key):
                raise CatalogError(f"unsafe filter key: {key!r}")
            where.append(f"json_extract(d.metadata, '$.{key}') = ?")
            params.append(value)

        if query:
            ids = self._fts_rowids(query)
            if not ids:
                return []
            where.append(f"d.doc_id IN ({','.join('?' * len(ids))})")
            params.extend(ids)

        sql = (
            "SELECT d.*, b.canonical_bytes, b.stored_bytes, b.codec, b.archive_rel"
            " FROM documents d JOIN blobs b ON b.sha256 = d.blob_sha256"
            f" WHERE {' AND '.join(where)} ORDER BY d.path LIMIT ?"
        )
        params.append(int(limit))
        hits: list[Hit] = []
        for row in self._conn.execute(sql, params):
            body = None
            if with_text:
                raw = self._read_verified_blob(row["blob_sha256"], row["archive_rel"])
                body = raw.decode("utf-8", "replace")
            hits.append(Hit(
                doc_id=row["doc_id"], path=row["path"], version=row["version"],
                title=row["title"], metadata=json.loads(row["metadata"]),
                canonical_bytes=row["canonical_bytes"], stored_bytes=row["stored_bytes"],
                codec=row["codec"], blob_sha256=row["blob_sha256"], text=body,
            ))
        return hits

    # -- maintenance -------------------------------------------------------

    def compact(self, *, dry_run: bool = False) -> dict:
        """Remove superseded/deleted rows and orphan blobs. The only lossy operation.

        Reports exactly what it removed, because this is the one call that can destroy
        bytes a user might still want.
        """
        dead = [
            r["doc_id"]
            for r in self._conn.execute(
                "SELECT doc_id FROM documents WHERE deleted = 1 OR superseded = 1"
            )
        ]
        live_blobs = {
            r["sha256"] for r in self._conn.execute("SELECT sha256 FROM blobs")
        }
        # Only LIVE rows keep a blob alive. Counting dead rows here was a real bug
        # (found by test_compact_reclaims...): every blob still had a referencing
        # tombstone, so nothing was ever orphaned and bytes_freed was always 0.
        referenced = {
            r["blob_sha256"]
            for r in self._conn.execute(
                "SELECT blob_sha256 FROM documents WHERE deleted = 0 AND superseded = 0"
            )
        }
        orphans = sorted(live_blobs - referenced)
        freed = 0
        for sha in orphans:
            rel = self._conn.execute(
                "SELECT archive_rel FROM blobs WHERE sha256 = ?", (sha,)
            ).fetchone()["archive_rel"]
            path = self.root / rel
            if path.exists():
                freed += path.stat().st_size

        if not dry_run:
            with self._conn:
                for doc_id in dead:
                    for table in FTS_TABLES:
                        try:
                            self._conn.execute(
                                f"DELETE FROM {table} WHERE rowid = ?", (doc_id,)
                            )
                        except sqlite3.OperationalError:
                            # Contentless FTS5 refuses DELETE; `_rebuild_index()` below
                            # drops and recreates both tables anyway, so the row is
                            # removed a moment later by the rebuild.
                            pass
                    self._conn.execute("DELETE FROM documents WHERE doc_id = ?", (doc_id,))
                for sha in orphans:
                    self._conn.execute("DELETE FROM blobs WHERE sha256 = ?", (sha,))
            for sha in orphans:
                rel = f"{BLOB_DIR}/{sha[:2]}/{sha}.lxz"
                try:
                    (self.root / rel).unlink()
                except FileNotFoundError:
                    pass
            self._conn.execute("VACUUM")
            self._rebuild_index()

        return {
            "documents_removed": len(dead),
            "blobs_removed": len(orphans),
            "bytes_freed": freed,
            "dry_run": dry_run,
        }

    def _rebuild_index(self) -> dict:
        """Recreate the FTS table from live documents. The "rebuild" mode.

        Also re-verifies every live blob on the way through, so a compaction that
        succeeds is evidence the store is intact — and a compaction that raises is
        evidence it is not.
        """
        live = list(self._conn.execute(
            "SELECT d.doc_id, d.path, d.title, d.blob_sha256, d.tokenizer,"
            " b.archive_rel"
            " FROM documents d JOIN blobs b ON b.sha256 = d.blob_sha256"
            " WHERE d.deleted = 0 AND d.superseded = 0"
        ))
        bodies = [
            (row["doc_id"], row["path"], row["title"], row["tokenizer"],
             self._read_verified_blob(row["blob_sha256"], row["archive_rel"])
             .decode("utf-8", "replace"))
            for row in live
        ]
        with self._conn:
            # Contentless FTS5 refuses DELETE, so a rebuild is a drop + recreate.
            for table in FTS_TABLES:
                self._conn.execute(f"DROP TABLE IF EXISTS {table}")
            self._conn.execute(FTS_SCHEMA)
            self._conn.execute(FTS_TRIGRAM_SCHEMA)
            # The gram index is deliberately NOT rebuilt here. It is dropped and
            # recreated for the FTS tables only because a contentless FTS5 table cannot
            # be DELETEd from, so its rows are best-effort and a rebuild is the repair.
            # `doc_grams` has neither problem: `_unindex` deletes a document's grams
            # exactly, before it touches the blob, so the table holds only live
            # documents and a rebuild here would be code no input could tell from its
            # own removal (a mutation sweep found exactly that).
            for doc_id, path, title, tokenizer, body in bodies:
                self._fts_insert(doc_id, path, title, body, tokenizer)
        return {"indexed": len(bodies)}

    def stats(self) -> dict:
        """What is in here, and how much the container + index cost."""
        row = self._conn.execute(
            "SELECT COUNT(*) AS docs,"
            " SUM(CASE WHEN deleted = 1 THEN 1 ELSE 0 END) AS deleted,"
            " SUM(CASE WHEN superseded = 1 THEN 1 ELSE 0 END) AS superseded"
            " FROM documents"
        ).fetchone()
        live = self._conn.execute(
            "SELECT COUNT(*) AS n, COALESCE(SUM(b.canonical_bytes),0) AS canonical,"
            " COALESCE(SUM(b.stored_bytes),0) AS stored"
            " FROM documents d JOIN blobs b ON b.sha256 = d.blob_sha256"
            " WHERE d.deleted = 0 AND d.superseded = 0"
        ).fetchone()
        blobs = self._conn.execute(
            "SELECT COUNT(*) AS n, COALESCE(SUM(stored_bytes),0) AS stored FROM blobs"
        ).fetchone()
        # Which index each live document sits in (ADR-0024). Reported rather than
        # inferred: a catalog that is mostly `trigram` pays for positions on every one
        # of those documents, and the owner should be able to see that in one number.
        by_tokenizer = {
            r["tokenizer"]: r["n"]
            for r in self._conn.execute(
                "SELECT tokenizer, COUNT(*) AS n FROM documents"
                " WHERE deleted = 0 AND superseded = 0 GROUP BY tokenizer"
            )
        }
        # The gram index is the other side of the same trade: it is what answers a
        # short query without reading a blob, and it is stored per document, so the
        # owner should be able to see how many documents carry one and how many are
        # still waiting for the backfill.
        gram_rows = self._conn.execute("SELECT COUNT(*) AS n FROM doc_grams").fetchone()["n"]
        gram_docs = self._conn.execute(
            "SELECT COUNT(*) AS n FROM doc_gram_docs"
        ).fetchone()["n"]
        gram_uncovered = self._conn.execute(
            "SELECT COUNT(*)" + self._LIVE_TRIGRAM_WHERE
            + " AND NOT EXISTS (SELECT 1 FROM doc_gram_docs x WHERE x.doc_id = d.doc_id)"
        ).fetchone()[0]
        # How many documents a delete can find its own grams for without walking the
        # table. Reported rather than assumed: a catalog whose digests were never
        # backfilled deletes exactly, but at the vocabulary's cost.
        # Guarded, because a report must not be the thing that raises: a catalog whose
        # digest table was dropped (or restored from a file without it) still answers.
        gram_digested = 0
        if self._conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'doc_gram_digest'"
        ).fetchone():
            gram_digested = self._conn.execute(
                "SELECT COUNT(*) AS n FROM doc_gram_digest"
            ).fetchone()["n"]
        index_bytes = self.index_path.stat().st_size if self.index_path.exists() else 0
        canonical = live["canonical"] or 0
        stored = live["stored"] or 0
        return {
            "documents": row["docs"] or 0,
            "deleted": row["deleted"] or 0,
            "superseded": row["superseded"] or 0,
            "live_documents": live["n"] or 0,
            "by_tokenizer": by_tokenizer,
            "gram_index": {
                "documents": gram_docs,
                "grams": gram_rows,
                "digested": gram_digested,
                "uncovered": gram_uncovered,
            },
            "blobs": blobs["n"] or 0,
            "canonical_bytes": canonical,
            "stored_bytes": stored,
            "ratio": (stored / canonical) if canonical else 1.0,
            "index_bytes": index_bytes,
            # The number that decides whether this design is worth it: index overhead
            # is a percentage of the payload, and it is stored uncompressed on purpose.
            "index_overhead_pct": (index_bytes / stored * 100) if stored else 0.0,
            # The same number against uncompressed text — the figure that says whether
            # queryability is cheap (measured ~6 % at detail=column) or not.
            "index_vs_canonical_pct": (index_bytes / canonical * 100) if canonical else 0.0,
        }
