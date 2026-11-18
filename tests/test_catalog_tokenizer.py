"""The tokenizer is recorded per document, and the CJK index answers what it should.

ADR-0024. The failures worth testing are the ones that return *nothing* and say nothing,
because a search index that is silently wrong looks exactly like a search index with no
matches:

  * a Chinese document indexed as `unicode61` — the whole sentence is one token, so a
    word inside it is unfindable;
  * a trigram index built at `detail=column` — every query longer than three characters
    is a phrase query, which FTS5 refuses, so the failure is an exception or a zero;
  * a tokenizer with no table, quietly indexed as the default;
  * a migration that loses the tokenizer of documents that already exist;
  * a rebuild (`compact()`) that puts every document back into the prose index.

Each of those has a test below, plus the measured behaviour of the trigram floor.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from lexora import catalog as cat_mod
from lexora.catalog import Catalog, CatalogError

HAN = "今天天气很好，我们一起去公园散步。"       # 今天天气… a sentence with no spaces
HAN_WORD = "天气很"                               # three characters, findable under trigram
HAN_SHORT = "公园"                                # two characters — the trigram floor
PROSE = "It was the best of times, it was the worst of times. " * 20


@pytest.fixture()
def store(tmp_path: Path) -> Catalog:
    with Catalog(tmp_path / "db", create=True) as c:
        yield c


# --------------------------------------------------------------------------- #
# recording
# --------------------------------------------------------------------------- #

def test_the_default_tokenizer_is_unicode61_and_is_recorded(store: Catalog) -> None:
    hit = store.add("prose.txt", PROSE.encode())
    row = store._conn.execute(
        "SELECT tokenizer, canonicalizer_version FROM documents WHERE doc_id = ?",
        (hit.doc_id,),
    ).fetchone()
    assert row["tokenizer"] == "unicode61"
    assert row["canonicalizer_version"] is None      # NULL = the frozen default label


def test_a_trigram_document_records_its_tokenizer_and_provenance(store: Catalog) -> None:
    hit = store.add("han.txt", HAN.encode(), tokenizer="trigram",
                    canonicalizer_version="zh-1")
    row = store._conn.execute(
        "SELECT tokenizer, canonicalizer_version FROM documents WHERE doc_id = ?",
        (hit.doc_id,),
    ).fetchone()
    assert row["tokenizer"] == "trigram"
    assert row["canonicalizer_version"] == "zh-1"


def test_an_unknown_tokenizer_is_refused_before_anything_is_written(
    store: Catalog, tmp_path: Path
) -> None:
    with pytest.raises(CatalogError) as excinfo:
        store.add("x.txt", b"hello\n", tokenizer="porter")
    message = str(excinfo.value)
    assert "porter" in message
    assert "trigram" in message and "unicode61" in message
    # nothing was stored: the refusal comes before the blob is written
    assert store.stats()["documents"] == 0
    assert store.search("hello") == []


# --------------------------------------------------------------------------- #
# the index that makes the tokenizer worth recording
# --------------------------------------------------------------------------- #

def test_trigram_finds_a_word_inside_an_unspaced_sentence(store: Catalog) -> None:
    store.add("han.txt", HAN.encode(), tokenizer="trigram")
    hits = store.search(HAN_WORD)
    assert [h.path for h in hits] == ["han.txt"]


def test_unicode61_cannot_find_the_same_word_and_that_is_the_whole_reason(
    store: Catalog
) -> None:
    """The control. Without this, the test above proves nothing about the index."""
    store.add("han.txt", HAN.encode(), tokenizer="unicode61")
    assert store.search(HAN_WORD) == []


def test_a_query_longer_than_three_characters_works_under_trigram(store: Catalog) -> None:
    """This is what `detail=full` buys: `detail=column` refuses it as a phrase query."""
    store.add("han.txt", HAN.encode(), tokenizer="trigram")
    assert [h.path for h in store.search("今天天气")] == ["han.txt"]


def test_the_trigram_floor_is_pinned_not_hidden(store: Catalog) -> None:
    """A two-character query matches nothing. It is a floor of the tokenizer.

    ADR-0024 records it as open work (bigram pre-segmentation, or a short-query scan).
    Pinning it here means the floor is a decision someone made, not an accident a user
    discovers as a silent zero.
    """
    store.add("han.txt", HAN.encode(), tokenizer="trigram")
    assert store.search(HAN_SHORT) == []


def test_a_short_query_still_answers_from_the_prose_index(store: Catalog) -> None:
    """A trigram refusal must not swallow the other index's answer."""
    store.add("prose.txt", PROSE.encode())
    store.add("han.txt", HAN.encode(), tokenizer="trigram")
    # `it` is shorter than three characters; trigram refuses it, unicode61 answers it
    assert [h.path for h in store.search("it")] == ["prose.txt"]


def test_a_mixed_catalog_finds_both(store: Catalog) -> None:
    store.add("prose.txt", PROSE.encode())
    store.add("han.txt", HAN.encode(), tokenizer="trigram")
    assert [h.path for h in store.search("best")] == ["prose.txt"]
    assert [h.path for h in store.search(HAN_WORD)] == ["han.txt"]
    assert store.stats()["by_tokenizer"] == {"unicode61": 1, "trigram": 1}


# --------------------------------------------------------------------------- #
# lifecycle: supersede, delete, rebuild
# --------------------------------------------------------------------------- #

def test_a_superseded_trigram_document_is_unfindable(store: Catalog) -> None:
    store.add("han.txt", HAN.encode(), tokenizer="trigram")
    store.add("han.txt", (HAN + HAN).encode(), tokenizer="trigram")
    hits = store.search(HAN_WORD)
    assert len(hits) == 1 and hits[0].version == 2


def test_a_deleted_trigram_document_is_unfindable(store: Catalog) -> None:
    store.add("han.txt", HAN.encode(), tokenizer="trigram")
    assert store.delete("han.txt") == 1
    assert store.search(HAN_WORD) == []


def test_compact_rebuilds_both_indexes_and_keeps_the_tokenizer(store: Catalog) -> None:
    store.add("prose.txt", PROSE.encode())
    store.add("han.txt", HAN.encode(), tokenizer="trigram")
    store.add("han.txt", (HAN + HAN).encode(), tokenizer="trigram")   # leaves a superseded row
    report = store.compact()
    assert report["documents_removed"] == 1
    assert [h.path for h in store.search(HAN_WORD)] == ["han.txt"]
    assert [h.path for h in store.search("best")] == ["prose.txt"]
    assert store.stats()["by_tokenizer"] == {"unicode61": 1, "trigram": 1}


# --------------------------------------------------------------------------- #
# migration
# --------------------------------------------------------------------------- #

def _make_v1_catalog(root: Path) -> None:
    """A catalog exactly as schema v1 wrote it: no tokenizer column, no trigram table."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "blobs").mkdir(exist_ok=True)
    conn = sqlite3.connect(str(root / cat_mod.INDEX_NAME))
    conn.executescript(
        """
        CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE blobs (
            sha256 TEXT PRIMARY KEY, archive_rel TEXT NOT NULL,
            archive_sha256 TEXT NOT NULL, canonical_bytes INTEGER NOT NULL,
            stored_bytes INTEGER NOT NULL, codec TEXT NOT NULL, created_at TEXT NOT NULL
        );
        CREATE TABLE documents (
            doc_id INTEGER PRIMARY KEY AUTOINCREMENT, path TEXT NOT NULL,
            version INTEGER NOT NULL, deleted INTEGER NOT NULL DEFAULT 0,
            superseded INTEGER NOT NULL DEFAULT 0, blob_sha256 TEXT NOT NULL,
            title TEXT, metadata TEXT NOT NULL DEFAULT '{}', added_at TEXT NOT NULL,
            UNIQUE(path, version)
        );
        CREATE VIRTUAL TABLE documents_fts USING fts5(
            path, title, body, content='', detail=column, tokenize='unicode61');
        """
    )
    conn.execute("INSERT INTO meta(key, value) VALUES ('schema_version', '1')")
    conn.commit()
    conn.close()


def test_a_v1_catalog_is_migrated_in_place(tmp_path: Path) -> None:
    root = tmp_path / "old"
    _make_v1_catalog(root)
    # opening it — not creating it — is what has to migrate
    with Catalog(root) as cat:
        columns = {r["name"] for r in cat._conn.execute("PRAGMA table_info(documents)")}
        assert {"tokenizer", "canonicalizer_version"} <= columns
        tables = {r["name"] for r in cat._conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'")}
        assert "documents_fts_trigram" in tables
        assert cat._conn.execute(
            "SELECT value FROM meta WHERE key = 'schema_version'").fetchone()["value"] == "2"


def test_a_document_written_after_migration_defaults_to_unicode61(tmp_path: Path) -> None:
    root = tmp_path / "old"
    _make_v1_catalog(root)
    with Catalog(root) as cat:
        hit = cat.add("prose.txt", PROSE.encode())
        row = cat._conn.execute(
            "SELECT tokenizer FROM documents WHERE doc_id = ?", (hit.doc_id,)
        ).fetchone()
        assert row["tokenizer"] == "unicode61"
        # and the migrated catalog can index a CJK document immediately
        cat.add("han.txt", HAN.encode(), tokenizer="trigram")
        assert [h.path for h in cat.search(HAN_WORD)] == ["han.txt"]
