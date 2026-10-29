"""Offline tests for catalog-driven corpus selection.

No network: the selection rule is exercised against a synthetic CSV fixture that
mimics the real catalog's shape (including rows that must be filtered out), so
the tests stay honest and fast. The rule itself is the contract: Type=Text,
Language contains the requested code, ordered by PG id ascending, capped by
limit, minus exclusions.
"""

from __future__ import annotations

import pathlib

from benchmarks import corpus

HEADER = "Text#,Type,Issued,Title,Language,Authors,Subjects,LoCC,Bookshelves\r\n"

ROWS = [
    '11,Text,2000-01-01,"Third book",en,"A. Author",,"PS",\r\n',
    '5,Text,1999-01-01,"First book",en,"B. Author",,"PS",\r\n',
    '7,Text,1999-06-01,"Second book",en,"C. Author",,"PS",\r\n',
    '9,Sound,2001-01-01,"An audiobook",en,"D. Author",,,\r\n',
    '13,Text,2002-01-01,"Un livre",fr,"E. Author",,"PQ",\r\n',
    '15,Text,2003-01-01,"Devanagari text",hi,"F. Author",,,\r\n',
    '17,Image,2004-01-01,"A plate",en,"G. Author",,,\r\n',
    '19,Text,2005-01-01,"Mixed language edition",en;fr,"H. Author",,"PS",\r\n',
]


def _catalog(tmp_path: pathlib.Path) -> pathlib.Path:
    path = tmp_path / "pg_catalog.csv"
    path.write_text(HEADER + "".join(ROWS), encoding="utf-8")
    return path


def test_selection_filters_orders_and_caps(tmp_path) -> None:
    ids = [r["id"] for r in corpus.select_ids_from_catalog(_catalog(tmp_path), limit=100)]
    # Text + en only (Sound/Image/fr/hi dropped), id ascending; the "en;fr" row
    # qualifies because the Language field merely has to contain "en"
    assert ids == [5, 7, 11, 19]


def test_limit_takes_the_lowest_ids_first(tmp_path) -> None:
    assert [r["id"] for r in corpus.select_ids_from_catalog(_catalog(tmp_path), limit=2)] == [5, 7]


def test_exclusions_are_honoured(tmp_path) -> None:
    ids = [r["id"] for r in corpus.select_ids_from_catalog(_catalog(tmp_path), limit=100,
                                                           exclude=(5, 19))]
    assert ids == [7, 11]


def test_selection_is_deterministic(tmp_path) -> None:
    cat = _catalog(tmp_path)
    a = [r["id"] for r in corpus.select_ids_from_catalog(cat, limit=3)]
    b = [r["id"] for r in corpus.select_ids_from_catalog(cat, limit=3)]
    assert a == b


def test_row_metadata_is_carried_for_the_record(tmp_path) -> None:
    row = corpus.select_ids_from_catalog(_catalog(tmp_path), limit=1)[0]
    assert row["id"] == 5
    assert row["title"] == "First book"
    assert row["issued"] == "1999-01-01"


def test_language_other_than_english(tmp_path) -> None:
    ids = [r["id"] for r in corpus.select_ids_from_catalog(_catalog(tmp_path), language="hi", limit=10)]
    assert ids == [15]


def test_fetch_catalog_reuses_a_cached_copy(tmp_path) -> None:
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / "pg_catalog.csv").write_bytes(b"x" * 1_500_000)  # over the 1 MB sanity floor
    info = corpus.fetch_catalog(cache)  # must not hit the network
    assert info["reused"] is True
    assert info["bytes"] == 1_500_000
    assert info["url"] == corpus.GUTENBERG_CATALOG_URL
