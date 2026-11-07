# ADR-0017: PDF ingestion engine — pypdf, not PyMuPDF

> **Status:** **Accepted 2026-11-07** — implementation landed with this record. Closes the
> PyMuPDF item that [ADR-0009](ADR-0009-license-polyform-noncommercial.md) left open ("adding
> it requires its own ADR").
> **Date:** 2026-11-07
> **Deciders:** Owner Dr Sohil Momin (licence-compatibility question delegated to this record; the direction — "ingest PDFs" — is the owner's, from the blueprint's primary deliverables)
> **Related:** [ADR-0009](ADR-0009-license-polyform-noncommercial.md) (licence of record + the open item this closes) · [DEPENDENCY_LICENCE_REVIEW.md](../DEPENDENCY_LICENCE_REVIEW.md) · [PATH_TO_V1.md](../PATH_TO_V1.md) P3 · [PRODUCT_REQUIREMENTS.md](../PRODUCT_REQUIREMENTS.md) REQ-ING-002/003/004 · [OCR_PIPELINE.md](../OCR_PIPELINE.md)

## Context / Problem

REQ-ING-002 requires PDF text extraction, and the blueprint's primary deliverables name
"TXT/PDF ingestion and OCR cleaning" — so PDF support is not optional scope.

The obvious engine was **PyMuPDF** (`fitz`): fast, mature, good text extraction. It is also
**AGPL-3.0**. ADR-0009 recorded the consequence plainly: PolyForm Noncommercial 1.0.0 "does
not satisfy AGPL's copyleft either, so the flag stands unchanged and unchanged in force: it is
**not** a declared dependency and adding it requires its own ADR."

That left three ways forward: write the AGPL ADR and accept the obligation, ship PDF support
as a separate download the user installs themselves, or find an engine with no copyleft
problem at all. The third is strictly better if the engine is adequate — a permissive
dependency removes a legal question instead of answering it.

## Decision drivers

- **No new licence obligation** on a project whose licence is already unusual (source-
  available, non-OSI, non-commercial).
- **Adequate extraction for this project's purpose.** Lexora canonicalises *English text*; it
  does not need layout reconstruction, table detection, or font-level fidelity.
- **Optional, like the GUI.** A base install must not grow a dependency for a feature most
  users never touch (the same reasoning as ADR-0008's `[gui]` extra).
- **Graceful absence.** REQ-ING-003 already requires the pipeline to run with the OCR engine
  missing and say so; the same discipline applies to the PDF engine.
- **Refuse loudly on scans.** A scanned PDF has no text layer; archiving an empty document
  would be the silent failure this project treats as worst-in-class.

## Options considered

- **A. PyMuPDF (AGPL-3.0).** Best extraction and speed. Requires an AGPL ADR, a NOTICE
  obligation, and a copyleft story that sits badly beside PolyForm Noncommercial.
- **B. pypdf (BSD-3-Clause).** *(chosen)* Permissive, pure Python, no build step, no copyleft
  obligation. Slower, no OCR, weaker on unusual encodings and complex layouts.
- **C. pdfminer.six (MIT).** Comparable licence position, better layout analysis, notably
  slower and a heavier dependency tree.
- **D. Shell out to `pdftotext` (poppler, GPL).** A GPL binary invoked as a subprocess is a
  different relationship than linking, but it adds a *system* dependency and a version matrix,
  and the CLI already has one optional external binary (ziptastic) to explain.

## Decision

1. **pypdf is the PDF text-layer engine**, declared as the optional extra `lexora[pdf]`
   (`pypdf>=5,<7`, tested against 6.21.4). It is not a base-install dependency.
2. **Ingestion is a module, not a CLI hack**: `src/lexora/ingest.py` returns text plus
   provenance, and `lexora db add` consumes it, so a PDF can go straight into the queryable
   archive.
3. **Provenance is stored per document** (REQ-ING-004): `mode` (`text` | `pdf-text-layer`),
   `engine`, `engine_version`, `pages`, `pages_without_text`, `source_bytes`, `chars`,
   `text_sha256`. Explicit `--meta` values override provenance keys, because the user's label
   should win.
4. **A PDF with no text layer is refused**, with a message naming OCR and REQ-ING-003. Nothing
   is archived.
5. **No OCR in this ADR.** OCR remains open (OQ-10, REQ-ING-003, [OCR_PIPELINE.md](../OCR_PIPELINE.md));
   when it lands it will need its own engine decision, and pypdf is not a candidate for it.
6. **No layout reconstruction, column detection, table extraction or de-hyphenation.** The
   canonicaliser owns text changes, and it only applies whitelisted, versioned rules
   (REQ-CAN-003). Extraction hands over characters in page reading order and stops there.

## Consequences & trade-offs

**Positive.** A real product capability with zero licence exposure and no build step. PDFs
land directly in the queryable archive with provenance, which is what makes a mixed
TXT/PDF collection searchable. The "scanned PDF" case fails honestly instead of producing an
empty archive.

**Negative / accepted risks.**

- **Slower than MuPDF**, materially so on large files. Acceptable because ingestion is a
  one-time cost per document and is not on the query path.
- **Weaker extraction on hard PDFs** — unusual encodings, multi-column layouts, and
  right-to-left scripts may come out worse. The honest mitigation is to record the engine and
  version in provenance, so a document that extracted badly can be re-ingested later with a
  better engine *without* silently changing what is stored.
- **Pure Python means a real dependency tree of its own** (pypdf is dependency-free at
  runtime, which is why it was chosen over pdfminer.six).
- **`pages_without_text` is recorded but not acted on.** A 300-page PDF with 200 scanned pages
  will archive the 100 text pages and report the rest; it does not refuse. That is a deliberate
  choice — partial extraction is more useful than none — but it means a user must read the
  provenance to know what they got.

## Impact analysis

| Dimension | Impact |
|---|---|
| Licence | **Removes** an open AGPL question rather than answering it; pypdf is BSD-3-Clause, compatible with PolyForm Noncommercial |
| Security | New parse surface (PDF), but in an optional extra; a malformed PDF raises a clean `IngestError` rather than a traceback |
| Performance | Not on the query path; `db add` for a PDF costs extraction + canonicalisation |
| Compatibility | Base install unchanged; `lexora[pdf]` adds pypdf |

## Implementation & test implications

`src/lexora/ingest.py`, wired into `lexora db add` (`--encoding` added; `--no-canon` now
documented as text-only). `tests/test_ingest.py` — 15 tests. The PDF fixtures are **generated
from raw PDF syntax inside the test file**, deliberately: a fixture built with the library
under test would pass even if extraction were broken. Covered: single and multi-page order,
`pages_without_text`, a scanned PDF refusing with OCR named, a non-PDF named `.pdf`, cp1252
fallback recorded rather than silent, a declared encoding honoured, and an end-to-end run where
a PDF is added to the catalog, searched by full text and filtered by `mode`.
