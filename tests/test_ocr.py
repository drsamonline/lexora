"""OCR as an external plugin (ADR-0019): Tesseract called as a binary, like ziptastic.

The real Tesseract is not vendored and is not installed in the environment these
tests run in, so the seam is exercised with a **stub binary** that speaks the same
contract (`tesseract --version`, `--list-langs`, `stdin stdout -l LANG`). That
proves discovery, invocation, provenance and every refusal path.

It proves **nothing about OCR accuracy** — a stub returns fixed text, so no test
here can tell good OCR from bad. Accuracy needs the real binary and a real scan;
that is stated in the ADR rather than papered over with a passing test.

The scanned-PDF fixtures are generated here from raw PDF syntax with one embedded
grayscale image, so no second library decides whether extraction "worked".
"""

from __future__ import annotations

import importlib.util
import io
import os
import stat
import zlib
from pathlib import Path

import pytest
from PIL import Image

from lexora import cli, ocr_core
from lexora.catalog import Catalog
from lexora.ingest import IngestError, extract

_HAS_PYPDF = importlib.util.find_spec("pypdf") is not None
requires_pdf = pytest.mark.skipif(not _HAS_PYPDF, reason="lexora[pdf] not installed")

STUB = '''#!{python}
"""Stand-in for tesseract: same CLI contract, fixed output."""
import sys

def main(argv):
    if "--version" in argv:
        sys.stdout.write("tesseract 0.0.0-stub\\n leptonica-0.0.0\\n")
        return 0
    if "--list-langs" in argv:
        sys.stdout.write("List of available languages in /usr/share/tessdata (2):\\neng\\nosd\\n")
        return 0
    data = sys.stdin.buffer.read()
    if not data:
        sys.stderr.write("empty image\\n")
        return 1
    lang = "eng"
    if "-l" in argv:
        lang = argv[argv.index("-l") + 1]
    sys.stdout.write(f"STUB OCR TEXT [{lang}] {len(data)} bytes of image\\n")
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv))
'''


def _scanned_pdf(pages: int = 1, w: int = 320, h: int = 120) -> bytes:
    """A PDF with no text layer: each page carries one embedded grayscale image."""
    img = Image.new("L", (w, h), 255)
    for y in range(10, h - 10, 6):
        for x in range(10, w - 10, 4):
            img.putpixel((x, y), 0)
    stream = zlib.compress(img.tobytes())

    n_page_ids = [3 + 2 * i for i in range(pages)]
    img_ids = [4 + 2 * i for i in range(pages)]
    content_ids = [3 + 2 * pages + i for i in range(pages)]

    objs: list[bytes] = []
    objs.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objs.append(("<< /Type /Pages /Kids [%s] /Count %d >>"
                 % (" ".join(f"{i} 0 R" for i in n_page_ids), pages)).encode())
    for i in range(pages):
        objs.append((f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                     f"/Resources << /XObject << /Im0 {img_ids[i]} 0 R >> >> "
                     f"/Contents {content_ids[i]} 0 R >>").encode())
        objs.append(b"<< /Type /XObject /Subtype /Image /Width %d /Height %d "
                    b"/ColorSpace /DeviceGray /BitsPerComponent 8 /Filter /FlateDecode "
                    b"/Length %d >>\nstream\n" % (w, h, len(stream)) + stream + b"\nendstream")
    for _ in range(pages):
        content = b"q 612 0 0 792 0 0 cm /Im0 Do Q"
        objs.append(b"<< /Length %d >>\nstream\n" % len(content) + content + b"\nendstream")

    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objs, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % number + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
    for off in offsets:
        out += b"%010d 00000 n \n" % off
    out += (b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n"
            % (len(objs) + 1, xref))
    return bytes(out)


@pytest.fixture()
def stub_tesseract(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    path = tmp_path / "tesseract"
    # .replace, not .format: the stub contains its own f-string braces
    path.write_text(STUB.replace("{python}", os.sys.executable))
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    monkeypatch.setenv(ocr_core.BINARY_ENV, str(path))
    ocr_core._version_cached.cache_clear()
    ocr_core._langs_cached.cache_clear()
    return str(path)


@pytest.fixture()
def no_tesseract(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(ocr_core.BINARY_ENV, raising=False)
    monkeypatch.setattr(ocr_core.shutil, "which", lambda _n: None)


# --------------------------------------------------------------------------- #
# discovery and refusal
# --------------------------------------------------------------------------- #

def test_missing_binary_refuses_with_install_guidance(no_tesseract) -> None:
    assert ocr_core.available() is False
    with pytest.raises(ocr_core.OcrError) as excinfo:
        ocr_core.ocr_image(b"\x89PNG fake")
    message = str(excinfo.value)
    assert ocr_core.BINARY_ENV in message and "not vendored" in message


def test_version_and_languages_are_reported(stub_tesseract) -> None:
    assert ocr_core.version().startswith("tesseract 0.0.0-stub")
    assert "eng" in ocr_core.languages()


def test_absent_binary_reports_no_languages(no_tesseract) -> None:
    assert ocr_core.languages() == frozenset()
    assert ocr_core.version() is None


# --------------------------------------------------------------------------- #
# the seam
# --------------------------------------------------------------------------- #

def test_ocr_image_pipes_through_stdin_stdout(stub_tesseract) -> None:
    payload = b"fake-image-bytes"
    text = ocr_core.ocr_image(payload)
    # the stub echoes the byte count it received: proves the image reached it
    assert "STUB OCR TEXT" in text and f"{len(payload)} bytes" in text


def test_language_reaches_the_binary(stub_tesseract) -> None:
    assert "[eng+chi_sim]" in ocr_core.ocr_image(b"x", lang="eng+chi_sim")


def test_empty_image_is_refused_before_spawning(stub_tesseract) -> None:
    with pytest.raises(ocr_core.OcrError):
        ocr_core.ocr_image(b"")


def test_nonzero_exit_surfaces_stderr(tmp_path: Path, monkeypatch) -> None:
    failing = tmp_path / "tesseract"
    failing.write_text(f"#!{os.sys.executable}\nimport sys\n"
                       "sys.stdin.buffer.read()\nsys.stderr.write('bad tessdata\\n')\nsys.exit(4)\n")
    failing.chmod(0o755)
    monkeypatch.setenv(ocr_core.BINARY_ENV, str(failing))
    with pytest.raises(ocr_core.OcrError) as excinfo:
        ocr_core.ocr_image(b"x")
    assert "exited 4" in str(excinfo.value) and "bad tessdata" in str(excinfo.value)


# --------------------------------------------------------------------------- #
# page images without a PDF renderer
# --------------------------------------------------------------------------- #

@requires_pdf
def test_scan_pages_extracts_embedded_images_without_poppler(tmp_path: Path) -> None:
    pdf = tmp_path / "scan.pdf"
    pdf.write_bytes(_scanned_pdf(pages=3))
    images, failed = ocr_core.scan_pages(str(pdf))
    assert len(images) == 3 and failed == []
    assert images[0][:4] == b"\x89PNG"      # tesseract-readable, lossless


@requires_pdf
def test_scan_pages_reports_pages_it_cannot_handle(tmp_path: Path) -> None:
    """A page with no embedded image must be reported, not silently skipped."""
    from test_ingest import _pdf as text_pdf  # a text-layer PDF: no images

    pdf = tmp_path / "text.pdf"
    pdf.write_bytes(text_pdf(["just text, no scan"]))
    images, failed = ocr_core.scan_pages(str(pdf))
    assert images == [] and failed == [1]


@requires_pdf
def test_ocr_pdf_returns_provenance_worthy_facts(tmp_path: Path, stub_tesseract) -> None:
    pdf = tmp_path / "scan.pdf"
    pdf.write_bytes(_scanned_pdf(pages=2))
    result = ocr_core.ocr_pdf(str(pdf), lang="eng")
    assert result.pages_ocrd == 2
    assert "STUB OCR TEXT" in result.text
    assert result.engine_version.startswith("tesseract")
    assert result.renderer == "embedded-image"


# --------------------------------------------------------------------------- #
# ingestion: the two paths a scanned PDF can take
# --------------------------------------------------------------------------- #

@requires_pdf
def test_scanned_pdf_without_ocr_is_refused_and_names_the_flag(tmp_path: Path) -> None:
    pdf = tmp_path / "scan.pdf"
    pdf.write_bytes(_scanned_pdf())
    with pytest.raises(IngestError) as excinfo:
        extract(pdf)
    assert "--ocr" in str(excinfo.value)


@requires_pdf
def test_scanned_pdf_with_ocr_disabled_but_no_binary_says_so(tmp_path: Path,
                                                             no_tesseract) -> None:
    pdf = tmp_path / "scan.pdf"
    pdf.write_bytes(_scanned_pdf())
    with pytest.raises(IngestError) as excinfo:
        extract(pdf, ocr=True)
    assert "tesseract" in str(excinfo.value)


@requires_pdf
def test_scanned_pdf_through_ocr_records_its_provenance(tmp_path: Path,
                                                        stub_tesseract) -> None:
    pdf = tmp_path / "scan.pdf"
    pdf.write_bytes(_scanned_pdf(pages=2))
    result = extract(pdf, ocr=True, ocr_lang="eng")
    assert "STUB OCR TEXT" in result.text
    prov = result.provenance
    assert prov["mode"] == "ocr"
    assert prov["engine"] == "tesseract"
    assert prov["pages_ocrd"] == 2
    assert prov["languages"] == "eng"
    assert prov["renderer"] == "embedded-image"
    assert prov["pages"] == 2


@requires_pdf
def test_cli_ocr_end_to_end_lands_in_the_catalog(tmp_path: Path, stub_tesseract,
                                                 capsys) -> None:
    root = str(tmp_path / "db")
    pdf = tmp_path / "scan.pdf"
    pdf.write_bytes(_scanned_pdf())
    assert cli.main(["db", "init", "--root", root]) == cli.EXIT_OK
    capsys.readouterr()
    assert cli.main(["db", "add", "--root", root, "--in", str(pdf),
                     "--path", "scans/one.pdf", "--ocr", "--json"]) == cli.EXIT_OK
    import json
    payload = json.loads(capsys.readouterr().out)
    assert payload["metadata"]["mode"] == "ocr"
    with Catalog(tmp_path / "db") as cat:
        hits = cat.search(filters={"mode": "ocr"})
        assert [h.path for h in hits] == ["scans/one.pdf"]


@requires_pdf
def test_cli_refuses_a_scan_without_ocr_and_stores_nothing(tmp_path: Path, capsys) -> None:
    root = str(tmp_path / "db")
    pdf = tmp_path / "scan.pdf"
    pdf.write_bytes(_scanned_pdf())
    cli.main(["db", "init", "--root", root])
    capsys.readouterr()
    assert cli.main(["db", "add", "--root", root, "--in", str(pdf)]) == cli.EXIT_FILE
    assert "--ocr" in capsys.readouterr().err
    with Catalog(tmp_path / "db") as cat:
        assert cat.stats()["documents"] == 0
