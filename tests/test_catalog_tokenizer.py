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
  * a rebuild (`compact()`) that puts every document back into the prose index;
  * a short query answered by scanning when an index could answer it.

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

    The documents are made UNCOVERED on purpose (their grams are dropped, which is the
    state of a catalog the backfill has not reached): with the gram index holding them,
    the same three documents answer exactly and nothing is truncated — that is
    `test_the_index_answers_without_reading_a_blob` below. The bound is a property of
    the SCAN, so the scan has to be the thing under test.
    """
    monkeypatch.setattr(cat_mod, "SHORT_QUERY_SCAN_LIMIT", 2)
    store.add("a.txt", "今天天气很好".encode(), tokenizer="trigram")
    store.add("b.txt", "我们一起去".encode(), tokenizer="trigram")
    store.add("c.txt", "公园散步".encode(), tokenizer="trigram")
    store._conn.execute("DELETE FROM doc_grams")
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
# the gram index: the floor answered from an index, not a scan (ADR-0024)
# --------------------------------------------------------------------------- #

def test_a_short_query_is_answered_without_reading_a_blob(store, monkeypatch) -> None:
    """The scan is the fallback, not the path: it must not run when the index answers.

    The monkeypatch is the assertion. If either half of the scan is reached for a
    document the gram index holds, this test fails with the reason rather than passing
    on the same result a scan would also have produced.
    """
    store.add("han.txt", HAN.encode(), tokenizer="trigram")

    def boom(self, *args):            # pragma: no cover - it must not be reached
        raise AssertionError("the scan ran for a document the gram index holds")

    monkeypatch.setattr(Catalog, "_short_query_scan", boom)
    monkeypatch.setattr(Catalog, "_scan_rows", boom)
    assert [h.path for h in store.search(HAN_SHORT)] == ["han.txt"]
    assert [h.path for h in store.search("园")] == ["han.txt"]
    assert store.last_search_truncated is False


def test_the_index_answers_exactly_what_the_scan_would(store: Catalog) -> None:
    """Differential: the index REPLACES the scan, so the two must not disagree.

    A replacement that is subtly different — a case fold missed, the title skipped, a
    wildcard treated as a pattern — is exactly the silent wrong answer both of them
    exist to prevent. The needles include a Latin pair, a wildcard-shaped pair and a
    query longer than the floor (which neither path answers).
    """
    store.add("a.txt", "今天天气很好".encode(), tokenizer="trigram")
    store.add("b.txt", "我们一起去公园散步".encode(), tokenizer="trigram")
    store.add("c.txt", "THE QUICK BROWN FOX".encode(), tokenizer="trigram")
    store.add("prose.txt", PROSE.encode())          # unicode61: never in this answer
    for needle in ("公", "园", "公园", "天", "气", "ox", "OX", "zz", "%", "散步"):
        from_index = sorted(store._short_query(needle))
        store.last_search_truncated = False
        from_scan = sorted(store._short_query_scan(needle))
        assert from_index == from_scan, needle


def test_a_short_query_finds_every_document_that_holds_it(store: Catalog) -> None:
    store.add("a.txt", "今天公园散步".encode(), tokenizer="trigram")
    store.add("b.txt", "公园里有花".encode(), tokenizer="trigram")
    store.add("c.txt", "完全不同".encode(), tokenizer="trigram")
    assert sorted(h.path for h in store.search(HAN_SHORT)) == ["a.txt", "b.txt"]


def test_the_index_covers_the_title_and_the_path_too(store: Catalog) -> None:
    """The scan looked at path, title and text; the index must answer the same question."""
    store.add("han.txt", "no needle in this body".encode(), title="公园散步",
              tokenizer="trigram")
    assert [h.path for h in store.search(HAN_SHORT)] == ["han.txt"]


def test_a_prose_document_gets_no_grams(store: Catalog) -> None:
    """A unicode61 document is the prose index's job — grams would answer for it."""
    prose = store.add("prose.txt", b"abandoned at the gate")
    han = store.add("han.txt", HAN.encode(), tokenizer="trigram")
    holders = {
        r["doc_id"]
        for r in store._conn.execute("SELECT DISTINCT doc_id FROM doc_grams")
    }
    assert holders == {han.doc_id}
    assert prose.doc_id not in holders


def test_a_deleted_document_leaves_the_gram_index(store: Catalog) -> None:
    hit = store.add("han.txt", HAN.encode(), tokenizer="trigram")
    store.delete("han.txt")
    assert store._conn.execute(
        "SELECT COUNT(*) FROM doc_grams WHERE doc_id = ?", (hit.doc_id,)
    ).fetchone()[0] == 0
    assert store.search(HAN_SHORT) == []


def test_a_superseded_document_leaves_the_gram_index(store: Catalog) -> None:
    old = store.add("han.txt", HAN.encode(), tokenizer="trigram")
    store.add("han.txt", "完全不同的一句话".encode(), tokenizer="trigram")
    assert store._conn.execute(
        "SELECT COUNT(*) FROM doc_grams WHERE doc_id = ?", (old.doc_id,)
    ).fetchone()[0] == 0
    assert store.search(HAN_SHORT) == []


def test_compact_leaves_only_live_grams(store: Catalog) -> None:
    """Compaction must not leave a gram that answers for a document that is gone.

    It does not need to rebuild the table to achieve that — `_unindex` deletes a
    document's grams exactly when it is superseded — so this asserts the invariant
    after a compaction, not that the compaction did the work.
    """
    store.add("han.txt", HAN.encode(), tokenizer="trigram")
    store.add("han.txt", (HAN + HAN).encode(), tokenizer="trigram")   # one superseded row
    store.add("other.txt", "公园".encode(), tokenizer="trigram")
    store.compact()
    live = {
        r["doc_id"]
        for r in store._conn.execute(
            "SELECT doc_id FROM documents WHERE deleted = 0 AND superseded = 0")
    }
    holders = {
        r["doc_id"]
        for r in store._conn.execute("SELECT DISTINCT doc_id FROM doc_grams")
    }
    assert holders == live
    assert sorted(h.path for h in store.search(HAN_SHORT)) == ["han.txt", "other.txt"]


def test_a_scan_under_the_bound_is_not_reported_as_partial(
    store: Catalog, monkeypatch,
) -> None:
    """The flag is about the bound, not about the scan having happened at all.

    One uncovered document and a bound of ten: the scan ran, found the needle, and the
    answer is complete — so `last_search_truncated` must stay False. A flag raised
    whenever any document is scanned would cry wolf on every older catalog.
    """
    monkeypatch.setattr(cat_mod, "SHORT_QUERY_SCAN_LIMIT", 10)
    store.add("han.txt", HAN.encode(), tokenizer="trigram")
    store._conn.execute("DELETE FROM doc_grams")
    assert [h.path for h in store.search(HAN_SHORT)] == ["han.txt"]
    assert store.last_search_truncated is False


def test_the_stats_report_gram_coverage(store: Catalog) -> None:
    store.add("han.txt", HAN.encode(), tokenizer="trigram")
    store.add("prose.txt", PROSE.encode())
    grams = store.stats()["gram_index"]
    assert grams["documents"] == 1
    assert grams["uncovered"] == 0
    # every unigram and bigram of the PATH and the BODY, and no more: the count is the
    # index, so a title or a path left out of it shows up here as a smaller number.
    expected = len(Catalog._grams("han.txt") | Catalog._grams(HAN))
    assert grams["grams"] == expected > 20


def test_a_folded_needle_longer_than_two_characters_falls_back_to_the_scan(
    store: Catalog, monkeypatch,
) -> None:
    """`ﬃ` folds to `ffi`: no unigram or bigram can represent it, so the scan answers."""
    store.add("lig.txt", b"an ffi ligature", tokenizer="trigram")
    calls: list[str] = []
    real = Catalog._short_query_scan
    monkeypatch.setattr(
        Catalog, "_short_query_scan",
        lambda self, q: (calls.append(q), real(self, q))[1],
    )
    assert [h.path for h in store.search("ﬃ")] == ["lig.txt"]
    assert calls == ["ﬃ"]


def test_a_v2_catalog_gains_the_gram_index_on_open(
    tmp_path: Path, monkeypatch,
) -> None:
    """The index is BACKFILLED on open, not only built for documents added after it."""
    root = tmp_path / "v2"
    with Catalog(root, create=True) as cat:
        cat.add("han.txt", HAN.encode(), tokenizer="trigram")
        cat._conn.execute("DROP TABLE doc_grams")          # exactly a v2 catalog
        cat._conn.execute("UPDATE meta SET value = '2' WHERE key = 'schema_version'")
        cat._conn.commit()
    with Catalog(root) as cat:                              # opening is the migration
        grams = cat.stats()["gram_index"]
        assert grams["documents"] == 1
        assert grams["uncovered"] == 0
        assert grams["grams"] > 0

        def boom(self, *args):        # pragma: no cover - it must not be reached
            raise AssertionError("the scan ran on a backfilled catalog")

        monkeypatch.setattr(Catalog, "_short_query_scan", boom)
        monkeypatch.setattr(Catalog, "_scan_rows", boom)
        assert [h.path for h in cat.search(HAN_SHORT)] == ["han.txt"]


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
        assert "doc_grams" in tables
        assert cat._conn.execute(
            "SELECT value FROM meta WHERE key = 'schema_version'").fetchone()["value"] == "3"


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
