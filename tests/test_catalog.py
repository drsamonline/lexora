"""Tests for the queryable compressed archive (`lexora.catalog`).

The interesting failures here are not "does a row come back" — they are the ones that
make a queryable store untrustworthy:

  * a query returning a document that was deleted or superseded (stale reads);
  * a query returning bytes the container never verified;
  * `compact()` silently destroying a blob that a live document still needs;
  * an FTS query that a user can type (`C++`, an unbalanced quote) crashing the CLI.

Each of those has a test below, plus the plain round trip and the dedupe claim.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from lexora import catalog as cat_mod
from lexora import cli
from lexora.catalog import Catalog, CatalogError

PROSE = (
    "It was the best of times, it was the worst of times, it was the age of "
    "wisdom, it was the age of foolishness. "
) * 40


@pytest.fixture()
def store(tmp_path: Path) -> Catalog:
    with Catalog(tmp_path / "db", create=True) as c:
        yield c


def test_init_creates_index_and_blob_root(tmp_path: Path) -> None:
    root = tmp_path / "db"
    Catalog(root, create=True).close()
    assert (root / cat_mod.INDEX_NAME).is_file()
    assert (root / cat_mod.BLOB_DIR).is_dir()


def test_opening_a_missing_catalog_refuses_with_the_command_to_run(tmp_path: Path) -> None:
    with pytest.raises(CatalogError) as excinfo:
        Catalog(tmp_path / "nope")
    assert "db init" in str(excinfo.value)


def test_add_get_round_trip_preserves_bytes(store: Catalog) -> None:
    payload = PROSE.encode()
    hit = store.add("book1.txt", payload, title="A Tale", metadata={"author": "Dickens"})
    assert hit.version == 1 and hit.canonical_bytes == len(payload)

    got = store.get("book1.txt")
    assert got is not None
    assert got.text.encode() == payload
    assert got.title == "A Tale" and got.metadata["author"] == "Dickens"


def test_stored_blob_is_smaller_than_the_text(store: Catalog) -> None:
    hit = store.add("book1.txt", PROSE.encode())
    assert hit.stored_bytes < hit.canonical_bytes


def test_identical_content_is_stored_once(store: Catalog) -> None:
    """Dedupe by content hash — two paths with the same bytes share one blob."""
    store.add("a.txt", PROSE.encode())
    store.add("b.txt", PROSE.encode())
    st = store.stats()
    assert st["documents"] == 2
    assert st["blobs"] == 1, "identical content must not be stored twice"


def test_new_version_supersedes_the_old_one(store: Catalog) -> None:
    store.add("doc.txt", b"first revision about aardvarks\n")
    store.add("doc.txt", b"second revision about badgers\n")

    got = store.get("doc.txt")
    assert got is not None and got.version == 2
    assert b"badgers" in got.text.encode()

    # the superseded text must not be findable — a stale read is the bug that matters
    assert [h.path for h in store.search("aardvarks")] == []
    assert [h.path for h in store.search("badgers")] == ["doc.txt"]
    assert store.stats()["superseded"] == 1


def test_delete_tombstones_and_hides_from_search_and_get(store: Catalog) -> None:
    store.add("gone.txt", b"ephemeral content about wombats\n")
    assert store.delete("gone.txt") == 1

    assert store.get("gone.txt") is None
    assert store.search("wombats") == []
    assert store.stats()["deleted"] == 1
    # deleting twice reports nothing left to tombstone
    assert store.delete("gone.txt") == 0


def test_metadata_filter_and_full_text_combine(store: Catalog) -> None:
    store.add("a.txt", b"content mentioning elephants\n", metadata={"year": "1927"})
    store.add("b.txt", b"content mentioning elephants\n", metadata={"year": "1900"})
    store.add("c.txt", b"content mentioning giraffes\n", metadata={"year": "1927"})

    by_year = store.search(filters={"year": "1927"})
    assert sorted(h.path for h in by_year) == ["a.txt", "c.txt"]

    both = store.search("elephants", filters={"year": "1927"})
    assert [h.path for h in both] == ["a.txt"]


def test_filter_key_is_validated(store: Catalog) -> None:
    store.add("a.txt", b"x\n")
    with pytest.raises(CatalogError):
        store.search(filters={"year'; DROP TABLE documents; --": "1927"})


def test_unparseable_fts_query_returns_no_matches_instead_of_raising(store: Catalog) -> None:
    """A user typing `C++` or an unbalanced quote must not get a stack trace."""
    store.add("a.txt", b"a document about C++ and other things\n")
    for query in ['C++', '"unbalanced', "AND", "(((("]:
        assert isinstance(store.search(query), list)


def test_search_with_text_decodes_only_what_it_returns(store: Catalog) -> None:
    store.add("a.txt", b"the quick brown fox\n")
    hits = store.search("brown", with_text=True)
    assert hits and "quick brown" in hits[0].text


def test_corrupted_blob_is_refused_not_returned(store: Catalog) -> None:
    """The store must never hand back bytes the container did not verify."""
    hit = store.add("a.txt", PROSE.encode())
    blob = store.root / f"{cat_mod.BLOB_DIR}/{hit.blob_sha256[:2]}/{hit.blob_sha256}.lxz"
    data = bytearray(blob.read_bytes())
    data[-8] ^= 0xFF  # damage the trailer
    blob.write_bytes(bytes(data))

    with pytest.raises(CatalogError):
        store.get("a.txt")


def test_missing_blob_is_reported_not_ignored(store: Catalog) -> None:
    hit = store.add("a.txt", PROSE.encode())
    (store.root / f"{cat_mod.BLOB_DIR}/{hit.blob_sha256[:2]}/{hit.blob_sha256}.lxz").unlink()
    with pytest.raises(CatalogError) as excinfo:
        store.get("a.txt")
    assert "missing" in str(excinfo.value)


def test_compact_reclaims_superseded_and_deleted_but_spares_live_blobs(store: Catalog) -> None:
    store.add("keep.txt", b"live content about otters\n")
    store.add("drop.txt", b"dead content about martens\n")
    store.delete("drop.txt")
    store.add("keep.txt", b"updated content about otters and voles\n")  # supersedes v1

    dry = store.compact(dry_run=True)
    assert dry["dry_run"] is True and dry["documents_removed"] == 2
    assert store.stats()["documents"] == 3, "dry run must not remove anything"

    report = store.compact()
    assert report["documents_removed"] == 2
    assert report["bytes_freed"] > 0

    st = store.stats()
    assert st["documents"] == 1 and st["superseded"] == 0 and st["deleted"] == 0
    # the live document still decodes — compact must never take a needed blob
    assert b"voles" in store.get("keep.txt").text.encode()


def test_compact_never_removes_a_blob_shared_by_a_live_document(store: Catalog) -> None:
    """Two live documents sharing one blob: removing the third must not free it."""
    store.add("a.txt", PROSE.encode())
    store.add("b.txt", PROSE.encode())
    store.add("c.txt", PROSE.encode())
    store.delete("c.txt")
    store.compact()
    assert b"best of times" in store.get("a.txt").text.encode()
    assert store.stats()["blobs"] == 1


def test_stats_reports_index_overhead(store: Catalog) -> None:
    store.add("a.txt", PROSE.encode())
    st = store.stats()
    assert st["ratio"] < 1.0
    # The index is stored uncompressed on purpose; the number has to be visible.
    assert "index_overhead_pct" in st and st["index_bytes"] > 0


def test_metadata_must_be_json_serialisable(store: Catalog) -> None:
    with pytest.raises(CatalogError):
        store.add("a.txt", b"x\n", metadata={"bad": {1, 2, 3}})


def test_add_rejects_str(store: Catalog) -> None:
    with pytest.raises(CatalogError):
        store.add("a.txt", "text")  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# CLI surface — this is also the GUI's backend (ADR-0011 process separation)
# --------------------------------------------------------------------------- #

def test_cli_end_to_end(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root = str(tmp_path / "db")
    src = tmp_path / "doc.txt"
    src.write_bytes(b"The Canonical Text mentions pangolins.\r\nSecond line.\r\n")

    assert cli.main(["db", "init", "--root", root]) == cli.EXIT_OK
    assert cli.main(["db", "add", "--root", root, "--in", str(src),
                     "--path", "doc.txt", "--title", "Doc",
                     "--meta", "lang=en", "--json"]) == cli.EXIT_OK

    capsys.readouterr()
    assert cli.main(["db", "search", "--root", root, "--query", "pangolins"]) == cli.EXIT_OK
    assert "doc.txt" in capsys.readouterr().out

    assert cli.main(["db", "search", "--root", root, "--filter", "lang=en"]) == cli.EXIT_OK
    assert "doc.txt" in capsys.readouterr().out

    out = tmp_path / "back.txt"
    assert cli.main(["db", "get", "--root", root, "doc.txt", "--out", str(out)]) == cli.EXIT_OK
    # canonicalisation is the default: CRLF became LF
    assert out.read_bytes() == b"The Canonical Text mentions pangolins.\nSecond line.\n"

    assert cli.main(["db", "delete", "--root", root, "doc.txt"]) == cli.EXIT_OK
    assert cli.main(["db", "get", "--root", root, "doc.txt"]) == cli.EXIT_FILE
    assert cli.main(["db", "compact", "--root", root]) == cli.EXIT_OK
    compact_report = json.loads(capsys.readouterr().out)  # one JSON doc per command
    assert compact_report["documents_removed"] == 1
    assert cli.main(["db", "stats", "--root", root]) == cli.EXIT_OK
    assert json.loads(capsys.readouterr().out)["documents"] == 0


def test_cli_refuses_a_bad_meta_pair(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root = str(tmp_path / "db")
    src = tmp_path / "d.txt"
    src.write_bytes(b"x\n")
    cli.main(["db", "init", "--root", root])
    assert cli.main(["db", "add", "--root", root, "--in", str(src),
                     "--meta", "noequals"]) == cli.EXIT_FILE
    assert "key=value" in capsys.readouterr().err


def test_cli_get_by_id(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root = str(tmp_path / "db")
    src = tmp_path / "d.txt"
    src.write_bytes(b"identifiable content\n")
    cli.main(["db", "init", "--root", root])
    cli.main(["db", "add", "--root", root, "--in", str(src), "--path", "d.txt"])
    capsys.readouterr()
    assert cli.main(["db", "get", "--root", root, "--id", "1"]) == cli.EXIT_OK
    assert "identifiable" in capsys.readouterr().out
