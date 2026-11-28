"""P3.9 — a delete is bounded by the document, not by the vocabulary.

Schema v4 made a gram LOOKUP cost the size of the answer and left the DELETE costing the
size of the vocabulary: `_grams_delete` could only find the posting lists a document
reached by decoding every one of them. `benchmarks/gram_delete_probe.py` measured that
(500 documents, 19,478 grams: 19,478 posting lists decoded, 1.08 s, per delete) and then
measured the fix — a per-document digest of the grams that document reached, front-coded
and compressed, which decodes 1,044 lists instead, 18.7x fewer, for 0.89x the stored
payload in bytes.

The tests here hold the implementation to the three things that measurement assumed:

* the digest is EXACT — every gram the document is in is in the digest, so a delete
  cannot miss a posting list and leave a stale id behind;
* the cost is the DOCUMENT — the same delete in a catalog ten times the vocabulary decodes
  the same number of lists (a count, not a timing, so it cannot flake);
* nothing is lost when there is no digest — a catalog written before the table existed
  still deletes exactly, and gets digests on its next open.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from lexora import catalog as cat_mod
from lexora.catalog import Catalog, _digest_pack, _digest_unpack, _pack_grams
from lexora.zstd_core import CodecError

HAN = "今天天气很好我们一起去公园散步湖边的柳树在风里轻轻摇"
MORE = "孩子们在草地上奔跑老人坐在长椅上读书猫在屋檐下打盹"
OTHER = "naïve café — ǅungla, İstanbul, an ﬃ ligature and a 😀"


@pytest.fixture()
def store(tmp_path: Path) -> Catalog:
    with Catalog(tmp_path / "catalog", create=True) as cat:
        yield cat


def _deleted_grams(store: Catalog, path: str) -> dict:
    """Delete one document, counting the `doc_grams` statements and lists decoded.

    The trace callback is the measurement: statement counts do not move with the machine,
    the cache or the load, which is why they are the figure the probe and these tests use.
    """
    stats = {"statements": 0, "lists_decoded": 0}

    def trace(sql: str) -> None:
        lowered = sql.lower()
        if "doc_grams" not in lowered:
            return
        stats["statements"] += 1
        if lowered.lstrip().startswith("select") and "postings" in lowered:
            stats["lists_decoded"] += 1

    store._conn.set_trace_callback(trace)
    try:
        stats["removed"] = store.delete(path)
    finally:
        store._conn.set_trace_callback(None)
    return stats


def _digest_grams(store: Catalog, path: str) -> list[str]:
    row = store._conn.execute(
        "SELECT g.grams FROM doc_gram_digest g JOIN documents d ON d.doc_id = g.doc_id"
        " WHERE d.path = ? AND d.deleted = 0",
        (path,),
    ).fetchone()
    return _digest_unpack(row["grams"]) if row else []


# --------------------------------------------------------------------------- #
# the encoding
# --------------------------------------------------------------------------- #

def test_a_digest_round_trips_through_front_coding_and_compression() -> None:
    grams = {"今", "今天", "今天天", "天", "天天气", "😀", "😀a", "ﬃ", "a", "aa", "ab"}
    assert sorted(_digest_unpack(_digest_pack(grams))) == sorted(grams)


def test_front_coding_pays_for_itself_on_a_shared_prefix() -> None:
    """Ten grams sharing `今` cost one prefix, not ten — the encoding's whole point."""
    grams = {"今" + "天" * i for i in range(1, 11)}
    packed = _pack_grams(grams)
    naive = sum(len(gram.encode()) for gram in grams)
    assert len(packed) < naive


def test_the_stored_digest_is_smaller_than_the_front_coded_form() -> None:
    """The compression claim, not a size guess: a real digest, compressed, is smaller."""
    grams = cat_mod.Catalog._grams(HAN) | cat_mod.Catalog._grams(MORE)
    assert len(_digest_pack(grams)) < len(_pack_grams(grams))


# --------------------------------------------------------------------------- #
# exactness — a delete must not leave a posting behind
# --------------------------------------------------------------------------- #

def test_the_digest_names_every_posting_list_the_document_is_in(store: Catalog) -> None:
    """Checked against the table itself, not against a re-derivation of the grams."""
    store.add("a.txt", HAN.encode(), title="公园", tokenizer="trigram")
    store.add("b.txt", MORE.encode(), tokenizer="trigram")
    doc_id = store._conn.execute(
        "SELECT doc_id FROM documents WHERE path = 'a.txt'"
    ).fetchone()["doc_id"]

    in_table = {
        row["gram"]
        for row in store._conn.execute("SELECT gram, postings FROM doc_grams")
        if doc_id in cat_mod._unpack_postings(row["postings"])
    }
    assert in_table, "the fixture must actually index the document"
    assert set(_digest_grams(store, "a.txt")) == in_table


def test_a_deleted_document_leaves_no_id_in_any_posting_list(store: Catalog) -> None:
    store.add("a.txt", HAN.encode(), tokenizer="trigram")
    store.add("b.txt", MORE.encode(), tokenizer="trigram")
    doc_id = store._conn.execute(
        "SELECT doc_id FROM documents WHERE path = 'a.txt'"
    ).fetchone()["doc_id"]

    assert store.delete("a.txt") == 1
    for row in store._conn.execute("SELECT gram, postings FROM doc_grams"):
        assert doc_id not in cat_mod._unpack_postings(row["postings"]), row["gram"]
    assert store._conn.execute(
        "SELECT COUNT(*) FROM doc_gram_digest WHERE doc_id = ?", (doc_id,)
    ).fetchone()[0] == 0
    assert store._conn.execute(
        "SELECT COUNT(*) FROM doc_gram_docs WHERE doc_id = ?", (doc_id,)
    ).fetchone()[0] == 0


def test_a_gram_only_the_deleted_document_held_stops_answering(store: Catalog) -> None:
    store.add("a.txt", HAN.encode(), tokenizer="trigram")
    store.add("b.txt", MORE.encode(), tokenizer="trigram")
    assert [h.path for h in store.search("柳")] == ["a.txt"]
    store.delete("a.txt")
    assert store.search("柳") == []
    # A gram both documents held still answers for the survivor.
    assert [h.path for h in store.search("在")] == ["b.txt"]


def test_superseding_a_document_removes_its_previous_grams(store: Catalog) -> None:
    """`add` of a new version supersedes the old row, which must leave the index too."""
    store.add("a.txt", HAN.encode(), tokenizer="trigram")
    store.add("a.txt", MORE.encode(), tokenizer="trigram")
    assert store.search("柳") == []
    assert [h.path for h in store.search("草地")] == ["a.txt"]
    # And the new version's own grams are in the index, so a later delete is exact.
    assert "草" in set(_digest_grams(store, "a.txt"))


# --------------------------------------------------------------------------- #
# the cost is the document, not the vocabulary
# --------------------------------------------------------------------------- #

def test_a_delete_decodes_only_the_documents_own_posting_lists(store: Catalog) -> None:
    """The contrast is measured in one catalog: digest vs the scan it replaces."""
    for i in range(20):
        store.add(f"doc{i:02d}.txt", (HAN + MORE[: i + 1] + str(i)).encode(),
                  tokenizer="trigram")
    vocabulary = store._conn.execute("SELECT COUNT(*) FROM doc_grams").fetchone()[0]
    own = len(_digest_grams(store, "doc00.txt"))
    assert 0 < own < vocabulary, (own, vocabulary)

    digest_stats = _deleted_grams(store, "doc00.txt")
    assert digest_stats["removed"] == 1
    assert digest_stats["lists_decoded"] == own

    # The control: the same delete in the same catalog, without the digest, decodes the
    # whole vocabulary — which is what the digest exists to avoid.
    doc_id = store._conn.execute(
        "SELECT doc_id FROM documents WHERE path = 'doc01.txt'"
    ).fetchone()["doc_id"]
    store._conn.execute("DELETE FROM doc_gram_digest WHERE doc_id = ?", (doc_id,))
    store._conn.commit()
    vocabulary_now = store._conn.execute("SELECT COUNT(*) FROM doc_grams").fetchone()[0]
    scan_stats = _deleted_grams(store, "doc01.txt")
    assert scan_stats["lists_decoded"] == vocabulary_now
    assert scan_stats["lists_decoded"] > digest_stats["lists_decoded"] * 2


def test_the_same_delete_costs_the_same_in_a_bigger_vocabulary(tmp_path: Path) -> None:
    """The count, not a clock: a timing would pass on a warm cache and fail in CI."""
    small = tmp_path / "small"
    with Catalog(small, create=True) as cat:
        cat.add("target.txt", HAN.encode(), tokenizer="trigram")
        cat.add("other.txt", MORE.encode(), tokenizer="trigram")
        small_vocab = cat._conn.execute("SELECT COUNT(*) FROM doc_grams").fetchone()[0]
        small_stats = _deleted_grams(cat, "target.txt")

    big = tmp_path / "big"
    with Catalog(big, create=True) as cat:
        cat.add("target.txt", HAN.encode(), tokenizer="trigram")
        for i in range(40):
            cat.add(f"other{i:02d}.txt", (MORE + OTHER[: i + 1] + str(i)).encode(),
                    tokenizer="trigram")
        big_vocab = cat._conn.execute("SELECT COUNT(*) FROM doc_grams").fetchone()[0]
        big_stats = _deleted_grams(cat, "target.txt")

    assert big_vocab > small_vocab * 2
    assert big_stats["lists_decoded"] == small_stats["lists_decoded"]


# --------------------------------------------------------------------------- #
# nothing is lost without a digest
# --------------------------------------------------------------------------- #

def test_a_document_without_a_digest_still_deletes_exactly(store: Catalog) -> None:
    """The state of a catalog written by v4 before the digest table existed."""
    store.add("a.txt", HAN.encode(), tokenizer="trigram")
    store.add("b.txt", MORE.encode(), tokenizer="trigram")
    doc_id = store._conn.execute(
        "SELECT doc_id FROM documents WHERE path = 'a.txt'"
    ).fetchone()["doc_id"]
    store._conn.execute("DELETE FROM doc_gram_digest WHERE doc_id = ?", (doc_id,))
    store._conn.commit()

    assert store.delete("a.txt") == 1
    for row in store._conn.execute("SELECT gram, postings FROM doc_grams"):
        assert doc_id not in cat_mod._unpack_postings(row["postings"]), row["gram"]
    assert store.search("柳") == []
    assert [h.path for h in store.search("在")] == ["b.txt"]


def test_a_v4_catalog_without_digests_gets_them_on_the_next_open(tmp_path: Path) -> None:
    root = tmp_path / "v4nodigest"
    with Catalog(root, create=True) as cat:
        cat.add("a.txt", HAN.encode(), tokenizer="trigram")
        cat.add("b.txt", MORE.encode(), tokenizer="trigram")
        expected = {
            path: sorted(_digest_grams(cat, path)) for path in ("a.txt", "b.txt")
        }
        cat._conn.execute("DROP TABLE doc_gram_digest")
        cat._conn.commit()
        assert cat.stats()["gram_index"]["digested"] == 0

    with Catalog(root) as cat:                    # opening is the migration
        assert cat.stats()["gram_index"]["digested"] == 2
        for path, grams in expected.items():
            assert sorted(_digest_grams(cat, path)) == grams
        stats = _deleted_grams(cat, "a.txt")
        assert stats["lists_decoded"] == len(expected["a.txt"])
        assert [h.path for h in cat.search("在")] == ["b.txt"]


def test_a_v3_catalog_repacks_and_gains_digests_in_the_same_open(tmp_path: Path) -> None:
    root = tmp_path / "v3"
    with Catalog(root, create=True) as cat:
        cat.add("a.txt", HAN.encode(), tokenizer="trigram")
        cat.add("b.txt", MORE.encode(), tokenizer="trigram")
        rows = []
        expected: dict[str, set[str]] = {}
        for row in cat._conn.execute(
            "SELECT d.doc_id, d.path, d.title, d.tokenizer, b.archive_rel, b.sha256"
            " FROM documents d JOIN blobs b ON b.sha256 = d.blob_sha256"
            " WHERE d.deleted = 0 AND d.superseded = 0 AND d.tokenizer = 'trigram'"
        ):
            body = cat._read_verified_blob(row["sha256"], row["archive_rel"]).decode()
            grams = (cat._grams(row["path"]) | cat._grams(row["title"] or "")
                     | cat._grams(body))
            rows.extend((gram, row["doc_id"]) for gram in grams)
            expected[row["path"]] = grams
        cat._conn.execute("DROP TABLE doc_grams")
        cat._conn.execute("DROP TABLE doc_gram_docs")
        cat._conn.execute("DROP TABLE doc_gram_digest")
        cat._conn.execute(
            "CREATE TABLE doc_grams (gram TEXT NOT NULL, doc_id INTEGER NOT NULL,"
            " PRIMARY KEY (gram, doc_id)) WITHOUT ROWID"
        )
        cat._conn.executemany("INSERT INTO doc_grams(gram, doc_id) VALUES (?, ?)", rows)
        cat._conn.execute("UPDATE meta SET value = '3' WHERE key = 'schema_version'")
        cat._conn.commit()

    with Catalog(root) as cat:
        assert cat.stats()["gram_index"]["digested"] == 2
        # The digests must be the v3 rows inverted, not merely a row per document: an
        # empty digest would still delete "successfully" and leave every posting behind.
        for path, grams in expected.items():
            assert set(_digest_grams(cat, path)) == grams, path
        assert [h.path for h in cat.search("柳")] == ["a.txt"]
        stats = _deleted_grams(cat, "a.txt")
        assert stats["lists_decoded"] == len(expected["a.txt"])
        assert cat.search("柳") == []
        assert [h.path for h in cat.search("在")] == ["b.txt"]


# --------------------------------------------------------------------------- #
# observability — the owner can see which state a catalog is in
# --------------------------------------------------------------------------- #

def test_stats_reports_how_many_documents_a_delete_can_answer_for_directly(
    store: Catalog,
) -> None:
    assert store.stats()["gram_index"]["digested"] == 0
    store.add("a.txt", HAN.encode(), tokenizer="trigram")
    assert store.stats()["gram_index"]["digested"] == 1
    store.add("prose.txt", b"plain prose is the other index", tokenizer="unicode61")
    assert store.stats()["gram_index"]["digested"] == 1, "prose documents carry no grams"
    store.delete("a.txt")
    assert store.stats()["gram_index"]["digested"] == 0


def test_a_prose_document_is_never_given_a_digest(store: Catalog) -> None:
    """A `unicode61` document is the word index's job (ADR-0024), digest included."""
    store.add("prose.txt", b"plain prose", tokenizer="unicode61")
    assert store._conn.execute(
        "SELECT COUNT(*) FROM doc_gram_digest"
    ).fetchone()[0] == 0


def test_the_index_still_opens_when_the_digest_table_is_corrupt(store: Catalog) -> None:
    """A digest that cannot be decoded must not make the catalog unusable.

    This is the failure mode the digest adds: a byte flipped in a stored blob. The
    catalog is the documents' home, so the row is dropped and the delete falls back to
    the scan — the answer stays right, only the cost changes.
    """
    store.add("a.txt", HAN.encode(), tokenizer="trigram")
    store.add("b.txt", MORE.encode(), tokenizer="trigram")
    store._conn.execute("UPDATE doc_gram_digest SET grams = X'000102'")
    store._conn.commit()

    doc_id = store._conn.execute(
        "SELECT doc_id FROM documents WHERE path = 'a.txt'"
    ).fetchone()["doc_id"]
    with pytest.raises(CodecError):
        _digest_unpack(b"\x00\x01\x02")
    # ...and the delete does not raise, and leaves nothing behind.
    assert store.delete("a.txt") == 1
    for row in store._conn.execute("SELECT gram, postings FROM doc_grams"):
        assert doc_id not in cat_mod._unpack_postings(row["postings"]), row["gram"]
