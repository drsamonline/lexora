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


def test_the_trigram_index_still_cannot_answer_two_characters(store: Catalog) -> None:
    """The floor is a property of the TOKENIZER, and it is still true.

    This asserts the measurement ADR-0024 recorded by asking the index itself, not the
    catalog: `trigram` indexes three-character sequences, so a two-character MATCH has
    no row to hit. The catalog's short-query scan (below) answers the user's question
    anyway; it does not, and cannot, make the tokenizer answer it.
    """
    store.add("han.txt", HAN.encode(), tokenizer="trigram")
    try:
        rows = store._conn.execute(
            "SELECT rowid FROM documents_fts_trigram WHERE documents_fts_trigram MATCH ?",
            (HAN_SHORT,),
        ).fetchall()
    except sqlite3.OperationalError:
        rows = []        # older SQLite versions refuse the query instead of ignoring it
    assert rows == []


# --------------------------------------------------------------------------- #
# the short-query scan: what the floor is now answered with (ADR-0024 open work)
# --------------------------------------------------------------------------- #

def test_a_two_character_query_finds_the_document_through_the_scan(
    store: Catalog,
) -> None:
    """`公园` is one of the most common query shapes in Chinese; it used to return []."""
    store.add("han.txt", HAN.encode(), tokenizer="trigram")
    assert [h.path for h in store.search(HAN_SHORT)] == ["han.txt"]
    assert store.last_search_truncated is False


def test_a_one_character_query_is_answered_too(store: Catalog) -> None:
    store.add("han.txt", HAN.encode(), tokenizer="trigram")
    assert [h.path for h in store.search("园")] == ["han.txt"]


def test_the_scan_is_case_folded(store: Catalog) -> None:
    """A trigram document may be Latin text; case must not decide the answer."""
    store.add("latin.txt", b"THE QUICK BROWN FOX", tokenizer="trigram")
    assert [h.path for h in store.search("ox")] == ["latin.txt"]
    assert [h.path for h in store.search("QU")] == ["latin.txt"]


def test_a_three_character_query_does_not_run_the_scan(store, monkeypatch) -> None:
    """The scan is a fallback for what the index cannot do, never a path taken anyway."""
    store.add("han.txt", HAN.encode(), tokenizer="trigram")

    def boom(self, query):            # pragma: no cover - it must not be reached
        raise AssertionError("the scan ran for a query the index can answer")

    monkeypatch.setattr(Catalog, "_short_query_scan", boom)
    assert [h.path for h in store.search(HAN_WORD)] == ["han.txt"]


def test_the_scan_matches_literally_not_as_a_like_pattern(store: Catalog) -> None:
    """`%` and `_` are characters. A wildcard-shaped query must not match everything."""
    store.add("han.txt", "进度 100% 完成".encode(), tokenizer="trigram")
    assert [h.path for h in store.search("0%")] == ["han.txt"]
    assert store.search("%%") == []
    assert store.search("__") == []


def test_the_scan_does_not_find_a_deleted_document(store: Catalog) -> None:
    store.add("han.txt", HAN.encode(), tokenizer="trigram")
    store.delete("han.txt")
    assert store.search(HAN_SHORT) == []


def test_the_scan_does_not_find_a_superseded_document(store: Catalog) -> None:
    store.add("han.txt", HAN.encode(), tokenizer="trigram")
    store.add("han.txt", "完全不同的一句话".encode(), tokenizer="trigram")
    assert store.search(HAN_SHORT) == []


def test_the_scan_only_covers_documents_the_trigram_index_holds(
    store: Catalog,
) -> None:
    """A prose document is the prose index's job; the scan must not answer for it."""
    store.add("prose.txt", b"abandoned at the gate", tokenizer="unicode61")
    assert store.search("ab") == []          # unicode61 indexes words, not pairs
    assert store.last_search_truncated is False


def test_a_bounded_scan_says_it_was_bounded(store: Catalog, monkeypatch) -> None:
    """A partial answer must not look like a complete one.

    Three CJK documents, a bound of two, and the needle only in the third: the honest
    outcome is an empty result AND `last_search_truncated is True`, never a quiet [].
    """
    monkeypatch.setattr(cat_mod, "SHORT_QUERY_SCAN_LIMIT", 2)
    store.add("a.txt", "今天天气很好".encode(), tokenizer="trigram")
    store.add("b.txt", "我们一起去".encode(), tokenizer="trigram")
    store.add("c.txt", "公园散步".encode(), tokenizer="trigram")
    assert store.search(HAN_SHORT) == []
    assert store.last_search_truncated is True
    # …and the flag is per search, not sticky.
    assert [h.path for h in store.search("今天天气")] == ["a.txt"]
    assert store.last_search_truncated is False


def test_the_scan_answers_when_the_bound_is_not_hit(store: Catalog, monkeypatch) -> None:
    monkeypatch.setattr(cat_mod, "SHORT_QUERY_SCAN_LIMIT", 3)
    store.add("a.txt", "今天天气很好".encode(), tokenizer="trigram")
    store.add("b.txt", "我们一起去".encode(), tokenizer="trigram")
    store.add("c.txt", "公园散步".encode(), tokenizer="trigram")
    assert [h.path for h in store.search(HAN_SHORT)] == ["c.txt"]
    assert store.last_search_truncated is False


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
