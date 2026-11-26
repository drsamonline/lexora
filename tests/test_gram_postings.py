"""Schema v4 — the gram index is one posting list per gram, not one row per pair.

The shape change is a storage decision and it must not buy that with exactness. So the
tests here are mostly one question asked several ways: does the packed index answer
*exactly* what a substring test over the same documents would answer, for every one- and
two-character query, including the awkward ones (a non-BMP code point, a needle that is
only in the title, a document that has been superseded, a v3 catalog migrated in place)?

`benchmarks/gram_index_probe.py` measured the layouts; `tests/test_gram_postings.py`
holds the implementation to the property the measurement assumed — that a delta-coded
posting list is an exact answer and not a candidate one.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from lexora import catalog as cat_mod
from lexora.catalog import Catalog, _pack_postings, _unpack_postings

HAN = "今天天气很好我们一起去公园散步"
PROSE = "The Self-Attention mechanism, and a note on ﬃ ligatures."


@pytest.fixture()
def store(tmp_path: Path) -> Catalog:
    with Catalog(tmp_path / "catalog", create=True) as cat:
        yield cat


def _live_trigram_docs(store: Catalog) -> list[int]:
    return [
        row["doc_id"]
        for row in store._conn.execute(
            "SELECT doc_id FROM documents"
            " WHERE deleted = 0 AND superseded = 0 AND tokenizer = 'trigram'"
        )
    ]


# --------------------------------------------------------------------------- #
# the encoding itself
# --------------------------------------------------------------------------- #

def test_a_varint_round_trips_across_every_width_boundary() -> None:
    """1 byte to 127, 2 to 16383, and so on — the boundary is where an encoder lies."""
    for value in (0, 1, 126, 127, 128, 129, 16383, 16384, 2 ** 21 - 1, 2 ** 28, 2 ** 35):
        assert cat_mod._varint_decode(cat_mod._varint_encode(value)) == [value]


def test_postings_round_trip_and_come_back_sorted() -> None:
    ids = [7, 1, 128, 129, 130, 4000, 4001]
    assert _unpack_postings(_pack_postings(ids)) == sorted(ids)


def test_postings_are_delta_coded_so_a_run_costs_one_byte_each() -> None:
    """A dense run of consecutive ids is the common case and must not cost 4 bytes each."""
    packed = _pack_postings(range(1, 101))
    assert len(packed) == 101 - 1, len(packed)   # 100 ids: one 2-byte first delta, rest 1


def test_a_repeated_id_is_written_once() -> None:
    assert _unpack_postings(_pack_postings([3, 3, 3, 9])) == [3, 9]


# --------------------------------------------------------------------------- #
# exactness — the property the packing must not spend
# --------------------------------------------------------------------------- #

def test_the_index_answers_exactly_what_a_substring_test_would(store: Catalog) -> None:
    """Every one- and two-character needle, against a reference built from the documents."""
    docs = {
        "han.txt": ("", HAN),
        "titled.txt": ("公园散步", "no needle in this body"),
        "mixed.txt": ("", "naïve café — ǅungla, İstanbul"),
        "emoji.txt": ("", "a 😀 in the middle"),
        "ligature.txt": ("", "an ﬃ ligature and ß"),
        "prose.txt": ("", PROSE),
    }
    for path, (title, body) in docs.items():
        store.add(path, body.encode(), title=title or None, tokenizer="trigram")

    # the index covers the path as well as the title and the body (a short query has
    # always answered for all three), so the reference has to as well
    reference = {
        path: (path.casefold(), title.casefold(), body.casefold())
        for path, (title, body) in docs.items()
    }
    needles = set()
    for path, (title, body) in docs.items():
        folded = (path + title + body).casefold()
        needles.update(folded[i:i + 1] for i in range(len(folded)))
        needles.update(folded[i:i + 2] for i in range(len(folded) - 1))

    for needle in sorted(needles):
        if not needle or len(needle) > 2:
            continue
        expected = {
            store._conn.execute(
                "SELECT doc_id FROM documents WHERE path = ? AND superseded = 0"
                " AND deleted = 0", (path,)
            ).fetchone()["doc_id"]
            for path, (path_, title, body) in reference.items()
            if needle in path_ or needle in title or needle in body
        }
        assert store._gram_rowids(needle) == expected, needle


def test_a_non_bmp_character_is_indexed_and_found(store: Catalog) -> None:
    """A gram is a code point, not a UTF-16 unit: the emoji must not be a surrogate half."""
    store.add("emoji.txt", "a 😀 here".encode(), tokenizer="trigram")
    assert [h.path for h in store.search("😀")] == ["emoji.txt"]


def test_a_needle_that_is_only_in_the_title_is_found(store: Catalog) -> None:
    store.add("titled.txt", b"nothing here", title="公园散步", tokenizer="trigram")
    assert [h.path for h in store.search("公园")] == ["titled.txt"]


def test_a_gram_no_document_holds_answers_empty_without_an_error(store: Catalog) -> None:
    store.add("han.txt", HAN.encode(), tokenizer="trigram")
    assert store._gram_rowids("zz") == set()
    assert store.search("zz") == []


# --------------------------------------------------------------------------- #
# the answer is filtered, never trusted
# --------------------------------------------------------------------------- #

def test_a_posting_naming_a_superseded_document_is_not_returned(store: Catalog) -> None:
    """A stale posting is filtered at read time — the index must not inherit `_unindex`'s
    best-effort treatment of the FTS row."""
    old = store.add("han.txt", HAN.encode(), tokenizer="trigram")
    store.add("han.txt", "完全不同的一句话".encode(), tokenizer="trigram")
    # put the superseded id back into a posting list by hand: exactly the state a crash
    # between the two writes would leave
    store._conn.execute(
        "INSERT INTO doc_grams(gram, postings) VALUES ('公', ?)"
        " ON CONFLICT(gram) DO UPDATE SET postings = excluded.postings",
        (_pack_postings([old.doc_id]),),
    )
    store._conn.commit()
    assert old.doc_id not in store._gram_rowids("公")


def test_deleting_a_document_strips_it_from_every_posting_list(store: Catalog) -> None:
    hit = store.add("han.txt", HAN.encode(), tokenizer="trigram")
    store.add("other.txt", "公园里有花".encode(), tokenizer="trigram")
    store.delete("han.txt")
    for row in store._conn.execute("SELECT gram, postings FROM doc_grams"):
        assert hit.doc_id not in _unpack_postings(row["postings"]), row["gram"]
    # and a gram only that document held is gone rather than left empty
    assert store._conn.execute(
        "SELECT COUNT(*) FROM doc_grams WHERE gram = '天'"
    ).fetchone()[0] == 0
    assert store._conn.execute(
        "SELECT COUNT(*) FROM doc_gram_docs WHERE doc_id = ?", (hit.doc_id,)
    ).fetchone()[0] == 0


def test_a_gram_shared_by_two_documents_survives_one_of_them_going(store: Catalog) -> None:
    store.add("a.txt", "公园散步".encode(), tokenizer="trigram")
    keep = store.add("b.txt", "公园里有花".encode(), tokenizer="trigram")
    store.delete("a.txt")
    assert store._gram_rowids("公") == {keep.doc_id}
    assert [h.path for h in store.search("公")] == ["b.txt"]


# --------------------------------------------------------------------------- #
# storage — what the shape change buys, measured on the shipped code
# --------------------------------------------------------------------------- #

def test_a_posting_costs_less_than_a_byte_per_document(store: Catalog) -> None:
    """The v3 row cost ~14 bytes per (gram, document); this must be far below one.

    Twenty documents that share a body is the case the probe measured at 13.3x the
    stored payload for v3 and 1.8x for this shape — the shape only pays off where grams
    recur, so the test uses recurrence rather than a single document.
    """
    for i in range(20):
        store.add(f"doc{i}.txt", (HAN + " 公园散步").encode(), tokenizer="trigram")
    pairs = sum(
        len(_unpack_postings(row["postings"]))
        for row in store._conn.execute("SELECT postings FROM doc_grams")
    )
    bytes_ = store._conn.execute(
        "SELECT COALESCE(SUM(LENGTH(postings)), 0) FROM doc_grams"
    ).fetchone()[0]
    assert pairs > 500, pairs
    per_pair = bytes_ / pairs
    # a dense run of consecutive ids is one byte per document, first delta included
    assert per_pair <= 1.0, (bytes_, pairs)
    # the v3 row this replaces cost ~14 bytes per pair (benchmarks/results-gram-index.json)
    assert per_pair < 14 / 4, per_pair


def test_a_prose_document_is_not_indexed_and_says_so(store: Catalog) -> None:
    prose = store.add("prose.txt", PROSE.encode())
    han = store.add("han.txt", HAN.encode(), tokenizer="trigram")
    marked = {
        row["doc_id"] for row in store._conn.execute("SELECT doc_id FROM doc_gram_docs")
    }
    assert marked == {han.doc_id}
    assert prose.doc_id not in marked


# --------------------------------------------------------------------------- #
# migration — v3 in place, no re-ingestion
# --------------------------------------------------------------------------- #

def _make_v3_gram_table(cat: Catalog, drop_for: list[str]) -> None:
    """Turn a v4 catalog's gram index back into the v3 shape it migrated from.

    Every gram of every document except `drop_for`'s is written as its own row, which
    is exactly what schema v3 stored; the documents in `drop_for` are the ones a v3
    catalog never backfilled.
    """
    rows = []
    keep_docs = []
    for row in cat._conn.execute(
        "SELECT d.doc_id, d.path, d.title, d.tokenizer, b.archive_rel, b.sha256"
        " FROM documents d JOIN blobs b ON b.sha256 = d.blob_sha256"
        " WHERE d.deleted = 0 AND d.superseded = 0 AND d.tokenizer = 'trigram'"
    ):
        if row["path"] in drop_for:
            continue
        body = cat._read_verified_blob(row["sha256"], row["archive_rel"]).decode()
        grams = (cat._grams(row["path"]) | cat._grams(row["title"] or "")
                 | cat._grams(body))
        rows.extend((gram, row["doc_id"]) for gram in grams)
        keep_docs.append(row["doc_id"])
    cat._conn.execute("DROP TABLE doc_grams")
    cat._conn.execute("DROP TABLE doc_gram_docs")
    cat._conn.execute(
        "CREATE TABLE doc_grams (gram TEXT NOT NULL, doc_id INTEGER NOT NULL,"
        " PRIMARY KEY (gram, doc_id)) WITHOUT ROWID"
    )
    cat._conn.executemany("INSERT INTO doc_grams(gram, doc_id) VALUES (?, ?)", rows)
    cat._conn.execute("UPDATE meta SET value = '3' WHERE key = 'schema_version'")
    cat._conn.commit()
    return keep_docs


def test_a_v3_gram_table_is_repacked_in_place_on_open(tmp_path: Path) -> None:
    root = tmp_path / "v3"
    with Catalog(root, create=True) as cat:
        cat.add("a.txt", "公园散步".encode(), tokenizer="trigram")
        cat.add("b.txt", "公园里有花".encode(), tokenizer="trigram")
        before = sorted(h.path for h in cat.search("公"))
        keep = _make_v3_gram_table(cat, drop_for=[])
    assert before == ["a.txt", "b.txt"]

    with Catalog(root) as cat:                     # opening is the migration
        columns = {
            r["name"] for r in cat._conn.execute("PRAGMA table_info(doc_grams)")
        }
        assert "postings" in columns and "doc_id" not in columns
        assert cat._conn.execute(
            "SELECT value FROM meta WHERE key = 'schema_version'").fetchone()["value"] == "4"
        assert sorted(h.path for h in cat.search("公")) == ["a.txt", "b.txt"]
        grams = cat.stats()["gram_index"]
        assert grams["documents"] == len(keep) == 2
        assert grams["uncovered"] == 0
        assert grams["grams"] == len(cat._grams("a.txt") | cat._grams("公园散步")) + len(
            cat._grams("b.txt") | cat._grams("公园里有花")
        ) - len(
            (cat._grams("a.txt") | cat._grams("公园散步"))
            & (cat._grams("b.txt") | cat._grams("公园里有花"))
        )


def test_a_v3_catalog_that_was_half_backfilled_stays_half_backfilled(tmp_path: Path) -> None:
    """Migration must not claim a document the v3 rows never covered — the scan is what
    answers for that one, and a coverage marker would silently stop it being asked."""
    root = tmp_path / "v3half"
    with Catalog(root, create=True) as cat:
        cat.add("a.txt", "公园散步".encode(), tokenizer="trigram")
        cat.add("b.txt", "公园里有花".encode(), tokenizer="trigram")
        _make_v3_gram_table(cat, drop_for=["b.txt"])
    with Catalog(root) as cat:
        grams = cat.stats()["gram_index"]
        assert grams["uncovered"] == 1
        # both documents are still found: the index answers for a.txt, the scan for b.txt
        assert sorted(h.path for h in cat.search("公")) == ["a.txt", "b.txt"]
        assert cat.last_search_truncated is False


def test_repacking_twice_changes_nothing(tmp_path: Path) -> None:
    root = tmp_path / "twice"
    with Catalog(root, create=True) as cat:
        cat.add("a.txt", "公园散步".encode(), tokenizer="trigram")
    first = None
    for _ in range(2):
        with Catalog(root) as cat:
            snapshot = sorted(
                (row["gram"], row["postings"])
                for row in cat._conn.execute("SELECT gram, postings FROM doc_grams")
            )
        if first is None:
            first = snapshot
        else:
            assert snapshot == first


def test_the_stats_grams_are_distinct_grams_not_pairs(store: Catalog) -> None:
    """One row per gram means the count is the vocabulary, not the posting count."""
    store.add("a.txt", "公园散步".encode(), tokenizer="trigram")
    store.add("b.txt", "公园里有花".encode(), tokenizer="trigram")
    grams = store.stats()["gram_index"]
    distinct = len(
        store._grams("a.txt") | store._grams("公园散步")
        | store._grams("b.txt") | store._grams("公园里有花")
    )
    pairs = sum(
        len(_unpack_postings(row["postings"]))
        for row in store._conn.execute("SELECT postings FROM doc_grams")
    )
    assert grams["grams"] == distinct < pairs
    assert grams["documents"] == 2
