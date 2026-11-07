# ADR-0019: OCR as an external plugin — Tesseract, and no PDF renderer

> **Status:** **Accepted 2026-11-07** — implementation landed with this record. Owner asked
> whether Tesseract could be used "as external plugin"; it can, and that is now the design.
> **Date:** 2026-11-07
> **Deciders:** Owner Dr Sohil Momin (approach), documentation architect (engine + mechanism)
> **Related:** [ADR-0017](ADR-0017-pdf-engine.md) (pypdf, and the same optional-extra pattern) · [ADR-0009](ADR-0009-license-polyform-noncommercial.md) (why PyMuPDF is unavailable) · [ADR-0015](ADR-0015-codec-policy.md) (the external-binary pattern this copies) · [OCR_PIPELINE.md](../OCR_PIPELINE.md) · [PATH_TO_V1.md](../PATH_TO_V1.md) P3.3

## Context / Problem

REQ-ING-003 asks for optional OCR with a graceful skip. Two things blocked it: no engine
decision, and the assumption that OCR of a *scanned PDF* needs a PDF renderer — which would
mean poppler's `pdftoppm` (GPL) or PyMuPDF (AGPL, blocked by ADR-0009).

The owner supplied a real document (a 99-page declassified CIA scan) and asked whether
Tesseract could be an external plugin. Measuring that document answered both questions.

**What the document actually is** (measured, and worth recording because it is the shape of the
problem):

- **99 pages, zero extractable characters** — a pure scan, no text layer at all.
- **Every page carries exactly one embedded image**, 1-bit, ~2544×3240 (~300 dpi), as TIFF.
  Extraction costs **77 ms/page** (7.7 s for the whole document).
- **It contains Chinese**, not just English: a table on page 40 has Chinese column headers
  (e.g. 特异功能组, 对照组). English-only OCR will mangle those cells.
- **Every page repeats a boilerplate stamp** — "Approved For Release 2001/03/07 :
  CIA-RDP96-00792R000300330001-8", plus "LN734-85" and a page number — 99 times.
- Pages 10 and 40 carry **underlines and handwritten annotations** over the typescript.

## Decision

1. **Tesseract is an external plugin, exactly like ziptastic** (ADR-0015): discovered via
   `$LEXORA_TESSERACT` then `PATH`, never vendored, version and installed languages read from
   the binary and recorded in provenance.
2. **Call the binary, do not wrap it.** `pytesseract` is a thin subprocess wrapper, so adopting
   it would add a Python dependency *without* removing the binary dependency. `ocr_core.py`
   invokes `tesseract stdin stdout -l LANG` directly — image in on stdin, text out on stdout, no
   temporary files, nothing on disk.
3. **No PDF renderer.** `scan_pages()` pulls the **embedded** page image out with pypdf +
   Pillow and re-encodes it as PNG for Tesseract. This preserves the scanner's own resolution
   instead of resampling it, costs 77 ms/page, and needs neither poppler nor PyMuPDF. When a
   page has no embedded image the page number is **reported**, not silently skipped.
4. **OCR is opt-in**: `lexora db add --ocr [--lang eng]`. A scanned PDF without `--ocr` is
   refused with a message naming the flag; with `--ocr` but no binary, refused with install
   guidance. Nothing is ever archived empty.
5. **Provenance records the whole story**: `mode: "ocr"`, `engine`, `engine_version`,
   `languages`, `renderer: "embedded-image"`, `pages`, `pages_ocrd`, `pages_failed`,
   `text_sha256`. A reader can tell OCR'd text from a real text layer and know which engine and
   languages produced it — which matters when a document has to be re-OCR'd later.
6. **A text layer always wins.** If a PDF has any extractable text, that is used and OCR is not
   attempted: it is exact and free, whereas OCR is a guess. Mixed documents keep their text
   pages and report the rest in `pages_without_text`.

## Consequences & trade-offs

**Positive.** OCR with no new mandatory dependency, no AGPL/GPL question, and no renderer in the
loop. A scanned PDF can go straight into the queryable archive with provenance. The "scanned
PDF" case fails honestly instead of producing an empty archive.

**Negative / accepted risks.**

- **The embedded-image shortcut does not cover every PDF.** A PDF whose pages are vector art, or
  a scan split into multiple image tiles, or one image per page but rotated, will need a real
  rasteriser. `scan_pages()` reports such pages rather than pretending; the honest fallback
  (poppler `pdftoppm` as a second plugin) is not implemented.
- **Mixed-script documents need the right `--lang`.** The supplied document needs
  `eng+chi_sim`; with `eng` alone the Chinese table headers come out as noise. Tesseract needs a
  `traineddata` file per script, so this is an install-time decision, not a runtime one.
- **Boilerplate repeats.** Every page of the supplied scan carries the same release stamp, so
  OCR emits it 99 times. Header/footer dedup is a *cleaning* rule and belongs in the
  canonicaliser's whitelist (REQ-CAN-003), not in OCR — deliberately not done here.
- **OCR is slow and lossy.** Roughly 0.5–2 s/page with real Tesseract, and every character is a
  guess. Storing the source bytes' digest (`text_sha256` covers the text, `source_bytes` the
  input) is what makes a re-run comparable.
- **No accuracy claim is made.** The tests use a stub binary, which proves discovery, invocation,
  provenance and every refusal — and proves nothing about OCR quality. Accuracy needs the real
  binary and a human-checked sample; that is a measurement, not a unit test.

## Impact analysis

| Dimension | Impact |
|---|---|
| Licence | Tesseract (Apache-2.0) + Pillow (MIT-CMU) — both permissive; no copyleft obligation |
| Security | New parse surface: PDF images (via pypdf/Pillow, in an optional extra) and one subprocess per page, with a per-page timeout |
| Performance | 77 ms/page extraction + 0.5–2 s/page OCR; not on the query path |
| Compatibility | Base install unchanged; `lexora[ocr]` adds pypdf + Pillow. `tesseract` stays a system dependency the user installs |

## Implementation & test implications

`src/lexora/ocr_core.py` (discovery, `ocr_image`, `scan_pages`, `ocr_pdf`), wired into
`ingest._read_pdf` and `lexora db add --ocr --lang`. `tests/test_ocr.py` — 15 tests using a stub
Tesseract and synthetic scanned-PDF fixtures generated from raw PDF syntax. **Verified end to
end on the real 99-page document**: 99/99 pages extracted and OCR'd, provenance recorded,
30 s with a stub binary.
