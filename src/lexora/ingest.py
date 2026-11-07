"""Ingestion: turn a source file into canonical text, with provenance.

Scope
-----
This is REQ-ING-001 (TXT), REQ-ING-002 (PDF text layer) and REQ-ING-004
(provenance), and the *graceful-skip* half of REQ-ING-003 (OCR): a scanned page
with no text layer produces a clear refusal naming OCR as the missing piece,
rather than an empty document that silently archives nothing.

Why pypdf and not PyMuPDF
-------------------------
ADR-0009 left one dependency question open: PyMuPDF is AGPL-3.0, and PolyForm
Noncommercial does not satisfy AGPL's copyleft, so it "requires its own ADR
before it can become a dependency". Rather than write that ADR, this module
uses **pypdf (BSD-3-Clause)**, which is permissive and carries no copyleft
obligation at all — see ADR-0017. pypdf is slower than MuPDF on large files and
has no OCR of its own; both are acceptable because ingestion is a one-time cost
and OCR is optional by requirement.

What this deliberately does not do
----------------------------------
No layout reconstruction, no column detection, no table extraction, no
de-hyphenation. Those change the text in ways that are hard to prove, and this
project's rule is that cleaning must be conservative and versioned
(REQ-CAN-003). The PDF layer gives us characters in reading order per page; the
canonicaliser then applies the whitelisted rules.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path

TEXT_SUFFIXES = {".txt", ".text", ".md", ".rst", ".csv", ".tsv"}
PDF_SUFFIXES = {".pdf"}

ENGINE_TEXT = "lexora-text"
ENGINE_PDF = "pypdf"


class IngestError(Exception):
    """The file could not be turned into text. Always names what was missing."""


@dataclass
class IngestResult:
    """Extracted text plus everything a reader needs to trust it."""

    text: str
    provenance: dict = field(default_factory=dict)

    @property
    def is_empty(self) -> bool:
        return not self.text.strip()


def _engine_version() -> str:
    try:
        import pypdf

        return getattr(pypdf, "__version__", "unknown")
    except ImportError:  # pragma: no cover - reported by the caller
        return "absent"


def _read_text(path: Path, declared_encoding: str | None) -> IngestResult:
    raw = path.read_bytes()
    if declared_encoding:
        try:
            text = raw.decode(declared_encoding)
        except (LookupError, UnicodeDecodeError) as exc:
            raise IngestError(
                f"cannot decode {path.name} as {declared_encoding}: {exc}"
            ) from exc
    else:
        # UTF-8 first, then a conservative fallback. Never silently "succeed" with
        # replacement characters on a file that is simply not UTF-8: report it.
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            try:
                text = raw.decode("cp1252")
            except UnicodeDecodeError as exc:
                raise IngestError(
                    f"{path.name} is not UTF-8 or cp1252; pass the encoding explicitly"
                ) from exc
    return IngestResult(
        text=text,
        provenance={
            "mode": "text",
            "engine": ENGINE_TEXT,
            "engine_version": "1",
            "encoding": declared_encoding or "utf-8-or-cp1252",
            "source_bytes": len(raw),
        },
    )


def _read_pdf(path: Path) -> IngestResult:
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover - dependency is declared
        raise IngestError(
            "PDF ingestion needs pypdf (pip install 'lexora[pdf]')"
        ) from exc

    try:
        reader = PdfReader(str(path))
    except Exception as exc:  # noqa: BLE001 - pypdf raises several unrelated types
        raise IngestError(f"{path.name} is not a readable PDF: {exc}") from exc

    if reader.is_encrypted:
        # Try the empty-password case, which is the common "permissions" flavour.
        try:
            if reader.decrypt("") == 0:
                raise IngestError(f"{path.name} is encrypted; supply a password first")
        except IngestError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise IngestError(f"{path.name} is encrypted and could not be opened") from exc

    pages: list[str] = []
    empty_pages: list[int] = []
    for number, page in enumerate(reader.pages, start=1):
        try:
            page_text = page.extract_text() or ""
        except Exception:  # noqa: BLE001 - one bad page must not lose the rest
            page_text = ""
        if not page_text.strip():
            empty_pages.append(number)
        pages.append(page_text)

    text = "\n".join(pages)
    provenance = {
        "mode": "pdf-text-layer",
        "engine": ENGINE_PDF,
        "engine_version": _engine_version(),
        "pages": len(pages),
        "pages_without_text": empty_pages,
        "source_bytes": path.stat().st_size,
    }

    if not text.strip():
        # A scanned PDF. REQ-ING-003 says the pipeline must run with OCR absent and
        # say so clearly — an empty archive would be the silent failure this
        # project treats as the worst kind.
        raise IngestError(
            f"{path.name} has {len(pages)} page(s) and no extractable text layer "
            "(scanned or image-only). OCR is not available in this build "
            "(REQ-ING-003); nothing was archived."
        )
    return IngestResult(text=text, provenance=provenance)


def extract(path: str | Path, *, declared_encoding: str | None = None) -> IngestResult:
    """Extract text and provenance from a supported file.

    Supported today: plain text (TXT/MD/CSV…) and the PDF text layer. Anything
    else is refused by suffix rather than guessed at.
    """
    path = Path(path)
    if not path.exists():
        raise IngestError(f"no such file: {path}")
    if not path.is_file():
        raise IngestError(f"not a regular file: {path}")

    suffix = path.suffix.lower()
    if suffix in TEXT_SUFFIXES:
        return _read_text(path, declared_encoding)
    if suffix in PDF_SUFFIXES:
        return _read_pdf(path)
    raise IngestError(
        f"unsupported input {suffix or '(no extension)'}: supported are "
        f"{sorted(TEXT_SUFFIXES | PDF_SUFFIXES)}"
    )


def describe(result: IngestResult) -> dict:
    """Provenance plus a content digest — what gets stored beside the document."""
    out = dict(result.provenance)
    out["text_sha256"] = hashlib.sha256(result.text.encode("utf-8")).hexdigest()
    out["chars"] = len(result.text)
    return out
