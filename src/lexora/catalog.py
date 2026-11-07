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

from lexora import __version__, codec_registry
from lexora.container import (
    ContainerError,
    pack as lxz_pack,
    read_index,
    unpack as lxz_unpack,
)

SCHEMA_VERSION = 1

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
        # WAL: a reader can query while a writer appends, and a crash rolls back to
        # the last committed transaction instead of leaving a half-written index.
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        if create:
            self._create_schema()

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
                    UNIQUE(path, version)
                );
                CREATE INDEX IF NOT EXISTS documents_path ON documents(path);
                CREATE INDEX IF NOT EXISTS documents_live
                    ON documents(deleted, superseded);
                CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts
                    USING fts5(path, title, body, content='', detail=column,
                               tokenize='unicode61');
                """
            )
            self._conn.execute(
                "INSERT OR REPLACE INTO meta(key, value) VALUES ('schema_version', ?)",
                (str(SCHEMA_VERSION),),
            )
            self._conn.execute(
                "INSERT OR REPLACE INTO meta(key, value) VALUES ('lexora_version', ?)",
                (__version__,),
            )

    # -- payload store -----------------------------------------------------

    def _fts_insert(self, doc_id: int, path: str, title: str | None, body: str) -> None:
        self._conn.execute(
            "INSERT INTO documents_fts(rowid, path, title, body) VALUES (?,?,?,?)",
            (doc_id, path, title or "", body),
        )

    def _fts_delete(self, doc_id: int, path: str, title: str | None, body: str) -> None:
        """Remove one row from a contentless FTS table.

        Contentless tables cannot `DELETE`; FTS5 requires the original column values
        back, which is why the body is decoded from its blob here. Callers treat this
        as best-effort: a stale index row is harmless (search joins on live rows and
        `compact()` rebuilds the index outright), whereas failing an `add` because an
        old blob went missing would not be.
        """
        self._conn.execute(
            "INSERT INTO documents_fts(documents_fts, rowid, path, title, body)"
            " VALUES ('delete', ?, ?, ?, ?)",
            (doc_id, path, title or "", body),
        )

    def _unindex(self, doc_id: int, path: str, title: str | None, sha: str, rel: str) -> None:
        try:
            body = self._read_verified_blob(sha, rel).decode("utf-8", "replace")
            self._fts_delete(doc_id, path, title, body)
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
    ) -> Hit:
        """Append a version of `path`. Previous versions are superseded, not removed."""
        if not isinstance(canonical, bytes):
            raise CatalogError("add() expects canonical bytes, not str")
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
                "SELECT d.doc_id, d.path, d.title, d.blob_sha256, b.archive_rel"
                " FROM documents d JOIN blobs b ON b.sha256 = d.blob_sha256"
                " WHERE d.path = ? AND d.superseded = 0",
                (path,),
            ))
            for row in old:
                self._conn.execute(
                    "UPDATE documents SET superseded = 1 WHERE doc_id = ?", (row["doc_id"],)
                )
                self._unindex(row["doc_id"], row["path"], row["title"],
                              row["blob_sha256"], row["archive_rel"])
            cur = self._conn.execute(
                "INSERT INTO documents"
                "(path, version, blob_sha256, title, metadata, added_at)"
                " VALUES (?,?,?,?,?,?)",
                (path, version, sha, title, meta_json, _now()),
            )
            doc_id = int(cur.lastrowid)
            self._fts_insert(doc_id, path, title, canonical.decode("utf-8", "replace"))

        return Hit(
            doc_id=doc_id, path=path, version=version, title=title, metadata=meta,
            canonical_bytes=len(canonical), stored_bytes=stored,
            codec=info.codec_id, blob_sha256=sha,
        )

    def delete(self, path: str) -> int:
        """Tombstone every live version of `path`. Returns rows affected (0 = absent)."""
        with self._conn:
            rows = list(self._conn.execute(
                "SELECT d.doc_id, d.path, d.title, d.blob_sha256, b.archive_rel"
                " FROM documents d JOIN blobs b ON b.sha256 = d.blob_sha256"
                " WHERE d.path = ? AND d.deleted = 0",
                (path,),
            ))
            for row in rows:
                self._conn.execute(
                    "UPDATE documents SET deleted = 1 WHERE doc_id = ?", (row["doc_id"],)
                )
                self._unindex(row["doc_id"], row["path"], row["title"],
                              row["blob_sha256"], row["archive_rel"])
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
            try:
                return [
                    r["rowid"]
                    for r in self._conn.execute(
                        "SELECT rowid FROM documents_fts WHERE documents_fts MATCH ?",
                        (candidate,),
                    )
                ]
            except sqlite3.OperationalError:
                continue
        return []

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
        """
        where = ["d.deleted = 0", "d.superseded = 0"]
        params: list = []
        for key, value in (filters or {}).items():
            if not key.replace("_", "").isalnum():
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
                    self._conn.execute("DELETE FROM documents_fts WHERE rowid = ?", (doc_id,))
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
            "SELECT d.doc_id, d.path, d.title, d.blob_sha256, b.archive_rel"
            " FROM documents d JOIN blobs b ON b.sha256 = d.blob_sha256"
            " WHERE d.deleted = 0 AND d.superseded = 0"
        ))
        bodies = [
            (row["doc_id"], row["path"], row["title"],
             self._read_verified_blob(row["blob_sha256"], row["archive_rel"])
             .decode("utf-8", "replace"))
            for row in live
        ]
        with self._conn:
            # Contentless FTS5 refuses DELETE, so a rebuild is a drop + recreate.
            self._conn.execute("DROP TABLE IF EXISTS documents_fts")
            self._conn.execute(FTS_SCHEMA)
            for doc_id, path, title, body in bodies:
                self._fts_insert(doc_id, path, title, body)
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
        index_bytes = self.index_path.stat().st_size if self.index_path.exists() else 0
        canonical = live["canonical"] or 0
        stored = live["stored"] or 0
        return {
            "documents": row["docs"] or 0,
            "deleted": row["deleted"] or 0,
            "superseded": row["superseded"] or 0,
            "live_documents": live["n"] or 0,
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
