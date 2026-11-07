"""OCR as an external plugin: the Tesseract binary, called the same way as ziptastic.

Why a plugin and not a dependency
---------------------------------
`pytesseract` is a thin wrapper that shells out to the `tesseract` binary — so using
it would add a Python dependency *without* removing the binary dependency. Calling
the binary directly (as `ziptastic_core` does) gives the same behaviour with one
fewer thing to install, one fewer version to pin, and no wrapper between us and the
version we record in provenance.

So the rule is the project's existing one (ADR-0015, ADR-0017): an optional external
tool is discovered, never vendored; when it is absent the pipeline says so and
refuses, rather than silently archiving nothing.

What OCR needs that the codec did not
-------------------------------------
Tesseract reads an **image**, so a scanned PDF has to become images first. That would
normally mean a PDF renderer — poppler's `pdftoppm` (GPL) or PyMuPDF (AGPL, rejected
by ADR-0009). Measured on a real 99-page declassified scan (2026-11-07), every page
carried exactly **one embedded image**, 1-bit, ~2544×3240 (~300 dpi), extractable in
77 ms/page. So the common case needs **no renderer at all**: pull the embedded scan
out with pypdf and hand it to tesseract.

`scan_pages()` does that, and reports when a page cannot be handled that way so the
caller can refuse instead of OCR-ing a blank image and calling it success.
"""

from __future__ import annotations

import io
import os
import shutil
import subprocess
from dataclasses import dataclass, field
from functools import lru_cache

BINARY_ENV = "LEXORA_TESSERACT"
TIMEOUT_ENV = "LEXORA_TESSERACT_TIMEOUT"
DEFAULT_TIMEOUT = 300
DEFAULT_LANG = "eng"


class OcrError(Exception):
    """OCR could not run. Always names what is missing or what failed."""


@dataclass
class OcrResult:
    text: str
    languages: str
    engine_version: str
    pages_ocrd: int = 0
    pages_failed: list[int] = field(default_factory=list)
    renderer: str = "embedded-image"


# --------------------------------------------------------------------------- #
# discovery
# --------------------------------------------------------------------------- #

def find_binary() -> str | None:
    override = os.environ.get(BINARY_ENV)
    if override:
        return override if os.path.exists(override) else None
    return shutil.which("tesseract")


def available() -> bool:
    return find_binary() is not None


def _require_binary(binary: str | None) -> str:
    path = binary or find_binary()
    if not path:
        raise OcrError(
            "OCR needs the `tesseract` binary on PATH (or set "
            f"${BINARY_ENV} to its full path); it is not vendored. Install it "
            "(Debian/Ubuntu: apt install tesseract-ocr, macOS: brew install tesseract) "
            "or run without --ocr."
        )
    return path


@lru_cache(maxsize=4)
def _version_cached(path: str) -> str:
    proc = subprocess.run([path, "--version"], capture_output=True, check=False, timeout=60)
    text = (proc.stdout or proc.stderr).decode("utf-8", "replace").strip()
    first = text.splitlines()[0] if text else "unknown"
    return first


def version(binary: str | None = None) -> str | None:
    path = binary or find_binary()
    if not path:
        return None
    try:
        return _version_cached(path)
    except (OSError, subprocess.SubprocessError):  # pragma: no cover - env dependent
        return None


@lru_cache(maxsize=4)
def _langs_cached(path: str) -> frozenset[str]:
    proc = subprocess.run([path, "--list-langs"], capture_output=True, check=False, timeout=60)
    text = (proc.stdout or b"").decode("utf-8", "replace")
    return frozenset(
        line.strip() for line in text.splitlines()
        if line.strip() and "available languages" not in line.lower()
    )


def languages(binary: str | None = None) -> frozenset[str]:
    """Installed traineddata codes, e.g. {'eng', 'osd'}. Empty when absent."""
    path = binary or find_binary()
    if not path:
        return frozenset()
    try:
        return _langs_cached(path)
    except (OSError, subprocess.SubprocessError):  # pragma: no cover
        return frozenset()


# --------------------------------------------------------------------------- #
# OCR one image
# --------------------------------------------------------------------------- #

def ocr_image(image: bytes, *, lang: str = DEFAULT_LANG, binary: str | None = None,
              timeout: int | None = None) -> str:
    """Run tesseract over one image (PNG/TIFF bytes) and return its text.

    Uses tesseract's own `stdin`/`stdout` pseudo-files, so no temporary files are
    written and nothing touches the disk.
    """
    if not isinstance(image, bytes):
        raise OcrError("ocr_image() expects image bytes")
    if not image:
        raise OcrError("empty image")
    path = _require_binary(binary)
    limit = timeout or int(os.environ.get(TIMEOUT_ENV, DEFAULT_TIMEOUT))
    try:
        proc = subprocess.run(
            [path, "stdin", "stdout", "-l", lang],
            input=image, capture_output=True, timeout=limit, check=False,
        )
    except FileNotFoundError as exc:  # pragma: no cover - vanished after lookup
        raise OcrError(f"tesseract not executable: {path}") from exc
    except subprocess.TimeoutExpired as exc:
        raise OcrError(
            f"tesseract exceeded {limit}s on one page (raise ${TIMEOUT_ENV} for large scans)"
        ) from exc
    except OSError as exc:
        raise OcrError(f"cannot run tesseract at {path}: {exc}") from exc
    if proc.returncode != 0:
        detail = proc.stderr.decode("utf-8", "replace").strip().splitlines()
        raise OcrError(
            f"tesseract exited {proc.returncode}: "
            f"{detail[-1] if detail else '(no stderr)'}"
        )
    return proc.stdout.decode("utf-8", "replace")


# --------------------------------------------------------------------------- #
# PDF pages -> images, without a renderer
# --------------------------------------------------------------------------- #

def scan_pages(path: str, *, max_pages: int | None = None) -> tuple[list[bytes], list[int]]:
    """Return (page images as PNG bytes, page numbers that had no usable image).

    Deliberately does not rasterise the page: it pulls the embedded scan out of the
    PDF. That is what a scanned PDF actually contains, it preserves the scanner's
    resolution instead of resampling it, and it needs no poppler and no PyMuPDF —
    which matters because PyMuPDF is AGPL and ADR-0009 blocks it as a dependency.
    """
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover - dependency is declared
        raise OcrError("PDF handling needs pypdf (pip install 'lexora[pdf]')") from exc
    try:
        from PIL import Image
    except ImportError as exc:  # pragma: no cover
        raise OcrError(
            "extracting scan images needs Pillow (pip install 'lexora[ocr]')"
        ) from exc

    try:
        reader = PdfReader(path)
    except Exception as exc:  # noqa: BLE001
        raise OcrError(f"{path} is not a readable PDF: {exc}") from exc

    images: list[bytes] = []
    failed: list[int] = []
    for number, page in enumerate(reader.pages, start=1):
        if max_pages is not None and number > max_pages:
            break
        try:
            embedded = list(page.images)
        except Exception:  # noqa: BLE001 - a malformed page must not lose the rest
            failed.append(number)
            continue
        if not embedded:
            failed.append(number)
            continue
        try:
            pil = embedded[0].image
            buf = io.BytesIO()
            # PNG, not the original TIFF/CCITT: one format tesseract reads
            # everywhere, and lossless so the OCR sees exactly the scan.
            pil.save(buf, format="PNG")
            images.append(buf.getvalue())
        except Exception:  # noqa: BLE001
            failed.append(number)
    return images, failed


def ocr_pdf(path: str, *, lang: str = DEFAULT_LANG, max_pages: int | None = None,
            binary: str | None = None) -> OcrResult:
    """OCR every page image in a scanned PDF. Raises OcrError when it cannot."""
    _require_binary(binary)
    images, failed = scan_pages(path, max_pages=max_pages)
    if not images:
        raise OcrError(
            f"{path} has no extractable page image on any of its first "
            f"{max_pages or 'all'} page(s); this build cannot rasterise a PDF "
            "(no poppler, and PyMuPDF is AGPL — ADR-0009), so there is nothing to OCR"
        )
    texts: list[str] = []
    for index, image in enumerate(images, start=1):
        try:
            texts.append(ocr_image(image, lang=lang, binary=binary))
        except OcrError:
            failed.append(index)
            texts.append("")
    return OcrResult(
        text="\n".join(texts),
        languages=lang,
        engine_version=version(binary) or "unknown",
        pages_ocrd=len(images),
        pages_failed=sorted(failed),
    )
