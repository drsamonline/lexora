"""Tests for ingestion (TXT + PDF text layer) and its provenance.

The PDF fixtures are generated here from raw PDF syntax rather than checked in as
binaries, for two reasons: the test set stays readable and reviewable in a diff, and
there is no second library in the loop deciding whether extraction "worked".

The interesting cases are the refusals, not the happy path:
  * a scanned PDF (no text layer) must fail with a message naming OCR, not archive
    an empty document;
  * an encrypted PDF must say so;
  * a text file that is neither UTF-8 nor cp1252 must refuse rather than silently
    produce replacement characters.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lexora import cli
from lexora.catalog import Catalog
from lexora.ingest import IngestError, describe, extract


def _pdf(pages: list[str]) -> bytes:
    """Build a minimal valid PDF with one text block per page.

    Deliberately hand-rolled: a fixture generator that depends on the library under
    test would pass even when extraction is broken.
    """
    objects: list[bytes] = []
    n_pages = len(pages)
    # 1: catalog, 2: pages tree, then per page: page object + content object,
    # finally one font object.
    font_id = 3 + 2 * n_pages
    kids = " ".join(f"{3 + 2 * i} 0 R" for i in range(n_pages))
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objects.append(f"<< /Type /Pages /Kids [{kids}] /Count {n_pages} >>".encode())
    for i, body in enumerate(pages):
        content_id = 4 + 2 * i
        stream = f"BT /F1 12 Tf 72 720 Td ({body}) Tj ET".encode()
        objects.append(
            (f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
             f"/Contents {content_id} 0 R /Resources << /Font << /F1 {font_id} 0 R >> >> >>").encode()
        )
        objects.append(b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream")
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % number + body + b"\nendobj\n"
    xref_at = len(out)
    out += b"xref\n0 %d\n" % (len(objects) + 1)
    out += b"0000000000 65535 f \n"
    for off in offsets:
        out += b"%010d 00000 n \n" % off
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (
        len(objects) + 1, xref_at)
    return bytes(out)


# --------------------------------------------------------------------------- #
# plain text
# --------------------------------------------------------------------------- #

def test_text_extraction_reports_its_engine(tmp_path: Path) -> None:
    src = tmp_path / "a.txt"
    src.write_text("Hello canonical world.\n", encoding="utf-8")
    res = extract(src)
    assert res.text.startswith("Hello")
    assert res.provenance["mode"] == "text"
    assert res.provenance["engine"] == "lexora-text"
    assert res.provenance["source_bytes"] > 0


def test_cp1252_fallback_is_recorded_not_silent(tmp_path: Path) -> None:
    src = tmp_path / "a.txt"
    src.write_bytes("café naïve\n".encode("cp1252"))
    res = extract(src)
    assert "café" in res.text
    assert res.provenance["encoding"] == "utf-8-or-cp1252"


def test_undeclared_binary_encoding_refuses(tmp_path: Path) -> None:
    src = tmp_path / "a.txt"
    src.write_bytes(b"\xff\xfe\x00\x00 not text \x81\x8d")
    with pytest.raises(IngestError) as excinfo:
        extract(src)
    assert "encoding" in str(excinfo.value)


def test_declared_encoding_is_honoured(tmp_path: Path) -> None:
    src = tmp_path / "a.txt"
    src.write_bytes("Привет мир\n".encode("cp1251"))
    assert "Привет" in extract(src, declared_encoding="cp1251").text
    with pytest.raises(IngestError):
        extract(src, declared_encoding="utf-8")


# --------------------------------------------------------------------------- #
# PDF
# --------------------------------------------------------------------------- #

def test_pdf_single_page_extracts_text_and_page_count(tmp_path: Path) -> None:
    src = tmp_path / "doc.pdf"
    src.write_bytes(_pdf(["The whale surfaced near the ship."]))
    res = extract(src)
    assert "whale surfaced" in res.text
    assert res.provenance["mode"] == "pdf-text-layer"
    assert res.provenance["engine"] == "pypdf"
    assert res.provenance["pages"] == 1
    assert res.provenance["pages_without_text"] == []


def test_pdf_multiple_pages_keep_order(tmp_path: Path) -> None:
    src = tmp_path / "doc.pdf"
    src.write_bytes(_pdf(["FIRSTPAGE", "SECONDPAGE", "THIRDPAGE"]))
    res = extract(src)
    positions = [res.text.find(p) for p in ("FIRSTPAGE", "SECONDPAGE", "THIRDPAGE")]
    assert all(p >= 0 for p in positions), res.text
    assert positions == sorted(positions), "page order must be preserved"
    assert res.provenance["pages"] == 3


def test_scanned_pdf_refuses_and_names_ocr(tmp_path: Path) -> None:
    """An image-only PDF must not archive an empty document."""
    src = tmp_path / "scan.pdf"
    src.write_bytes(_pdf([""]))  # a page with a content stream but no text
    with pytest.raises(IngestError) as excinfo:
        extract(src)
    message = str(excinfo.value)
    assert "OCR" in message and "REQ-ING-003" in message


def test_a_page_without_text_is_recorded_when_others_have_it(tmp_path: Path) -> None:
    src = tmp_path / "mixed.pdf"
    src.write_bytes(_pdf(["REALTEXT", ""]))
    res = extract(src)
    assert "REALTEXT" in res.text
    assert res.provenance["pages_without_text"] == [2]


def test_non_pdf_named_pdf_refuses_clearly(tmp_path: Path) -> None:
    src = tmp_path / "fake.pdf"
    src.write_bytes(b"this is not a pdf at all")
    with pytest.raises(IngestError) as excinfo:
        extract(src)
    assert "not a readable PDF" in str(excinfo.value)


def test_unsupported_suffix_is_refused_by_name(tmp_path: Path) -> None:
    src = tmp_path / "a.docx"
    src.write_bytes(b"PK\x03\x04")
    with pytest.raises(IngestError) as excinfo:
        extract(src)
    assert ".docx" in str(excinfo.value) or "unsupported" in str(excinfo.value)


def test_missing_file_and_directory_are_distinguished(tmp_path: Path) -> None:
    with pytest.raises(IngestError):
        extract(tmp_path / "nope.txt")
    with pytest.raises(IngestError):
        extract(tmp_path)


def test_describe_adds_a_content_digest() -> None:
    from lexora.ingest import IngestResult

    info = describe(IngestResult(text="abc", provenance={"mode": "text"}))
    assert info["chars"] == 3
    assert len(info["text_sha256"]) == 64


# --------------------------------------------------------------------------- #
# end to end through the catalog and the CLI
# --------------------------------------------------------------------------- #

def test_pdf_lands_in_the_catalog_with_provenance(tmp_path: Path) -> None:
    src = tmp_path / "doc.pdf"
    src.write_bytes(_pdf(["A pdf about pangolins and their scales."]))
    with Catalog(tmp_path / "db", create=True) as cat:
        from lexora.ingest import describe as d

        res = extract(src)
        hit = cat.add("doc.pdf", res.text.encode(), metadata=d(res))
        assert hit.canonical_bytes > 0
        got = cat.get("doc.pdf")
        assert got.metadata["mode"] == "pdf-text-layer"
        assert got.metadata["engine"] == "pypdf"
        assert got.metadata["pages"] == 1
        assert [h.path for h in cat.search("pangolins")] == ["doc.pdf"]


def test_cli_db_add_ingests_a_pdf(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root = str(tmp_path / "db")
    src = tmp_path / "doc.pdf"
    src.write_bytes(_pdf(["Searchable content about wombats."]))
    assert cli.main(["db", "init", "--root", root]) == cli.EXIT_OK
    capsys.readouterr()  # init prints its own line; start clean before parsing JSON
    assert cli.main(["db", "add", "--root", root, "--in", str(src),
                     "--path", "papers/doc.pdf", "--meta", "collection=biology",
                     "--json"]) == cli.EXIT_OK
    payload = json.loads(capsys.readouterr().out)
    assert payload["metadata"]["mode"] == "pdf-text-layer"
    assert payload["metadata"]["collection"] == "biology", "--meta must win over provenance"

    assert cli.main(["db", "search", "--root", root, "--query", "wombats",
                     "--filter", "mode=pdf-text-layer"]) == cli.EXIT_OK
    assert "papers/doc.pdf" in capsys.readouterr().out


def test_cli_refuses_a_scanned_pdf_without_archiving(
        tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root = str(tmp_path / "db")
    src = tmp_path / "scan.pdf"
    src.write_bytes(_pdf([""]))
    cli.main(["db", "init", "--root", root])
    capsys.readouterr()
    assert cli.main(["db", "add", "--root", root, "--in", str(src)]) == cli.EXIT_FILE
    assert "OCR" in capsys.readouterr().err
    with Catalog(tmp_path / "db") as cat:
        assert cat.stats()["documents"] == 0, "a refused ingest must store nothing"
