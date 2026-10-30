# LEXORA Implementation Matrix

> **Status:** Draft (living document; every row reflects repository reality as of the verification date)
> **Owner:** Documentation architect (delegated)
> **Last verified:** 2026-10-15 — `git ls-files` shows documentation and scripts only; **no implementation modules, no tests exist**
> **Related:** [PRODUCT_REQUIREMENTS.md](PRODUCT_REQUIREMENTS.md) · [REQUIREMENTS_TRACEABILITY.md](REQUIREMENTS_TRACEABILITY.md) · [PHASES.md](PHASES.md)

## Purpose

Single table mapping each requirement to design section, implementation module/file, test ID, evidence link, status, and known gap. A requirement is never "Implemented" merely because a document mentions it.

## Status values

`Not started` · `In progress` · `Blocked` · `Implemented-untested` · `Verified` · `Deferred` · `Proposed`

## Matrix

| Req | Summary | Design section | Module/file (planned → actual) | Test ID | Evidence | Status | Known gap |
|---|---|---|---|---|---|---|---|
| REQ-ING-001 | TXT ingest, encoding-safe decode | [SPEC §1](SPECIFICATION.md), [BLUEPRINT](MASTER_BLUEPRINT.md) | planned `lexora/ingest/txt.py` — **absent** | T-ING-101 (planned) | none | Not started | OQ-7 blocks package creation |
| REQ-ING-002 | PDF text layer, page order | SPEC §1; [OCR_PIPELINE](OCR_PIPELINE.md) | planned `lexora/ingest/pdf.py` — absent | T-ING-102 | none | Not started | PDF library choice undecided |
| REQ-ING-003 | Optional OCR, graceful skip | [OCR_PIPELINE](OCR_PIPELINE.md) | planned `lexora/ingest/ocr.py` — absent | T-ING-103 | none | Not started | OQ-10 (Tesseract availability) |
| REQ-ING-004 | Provenance metadata | SPEC §1.4; FORMAT_LXZ §metadata | planned in container writer | T-ING-104 | none | Not started | Format not frozen |
| REQ-CAN-001 | Deterministic canonicalization | [CANONICALIZATION](CANONICALIZATION.md) §Determinism | `src/lexora/canonicalize.py` | T-CAN-101 (property) | none | **Verified** | test_canonicalize.py, test_canonicalize_invariants.py |
| REQ-CAN-002 | UTF-8/no-BOM/LF policy per version | CANONICALIZATION §Output form | `src/lexora/canonicalize.py` | T-CAN-102 (golden) | none | **Verified** | 9 golden vectors in tests/vectors/canonicalization/ |
| REQ-CAN-003 | Whitelisted rules only | CANONICALIZATION rule table CAN-R01…R09 | `src/lexora/canonicalize.py` | T-CAN-103 (invariant) | none | **Verified** | whitelist asserted by test_canonicalize_invariants.py |
| REQ-CAN-004 | Canonicalizer version in archive | SPEC §2.4; FORMAT_LXZ header | `src/lexora/container.py` | T-CAN-104 | none | **Verified** | `canonicalizer_version` in the header, checked on read |
| REQ-CAN-005 | Devanagari/Gujarati safety | CANONICALIZATION §Scripts | canon + golden vectors | T-CAN-105 | none | Not started | Script vectors not authored |
| REQ-CAN-006 | Confidence-gated OCR correction + log | CANONICALIZATION CAN-R09; OCR_PIPELINE | ocr postprocess | T-CAN-106 | none | Not started | Threshold default unmeasured |
| REQ-CAN-007 | Cleaning ≤1% per ADR-0004 | [ADR-0004](ADR/ADR-0004-cleaning-error-metric.md) (Accepted) | sampling/review tooling planned | T-CAN-107 | metric defined; no run yet | Not started | Needs P3 sample review |
| REQ-CMP-001 | Byte-exact round trip | SPEC §3.1; COMPRESSION_ARCHITECTURE | `src/lexora/zstd_core.py` + container | T-CMP-101 (property/fuzz) | none | **Verified** | round trip asserted in test_reader_fuzz.py + test_writer_fuzz.py |
| REQ-CMP-002 | Zstd core codec, IDs declared | SPEC §4; ADR-0002/0003 roles | `src/lexora/zstd_core.py` | T-CMP-102 | none | **Verified** | `codec_id` in header; unknown id refused E-CMP-006 |
| REQ-CMP-003 | Cost-driven reproducible selection | [COST_MODEL](COST_MODEL.md) | `src/lexora/container.py` | T-CMP-103 | none | **Implemented** | single candidate ⇒ trivial; determinism tested, level pinned by ADR-0012 |
| REQ-CMP-004 | Total serialized-byte accounting | COST_MODEL formula | `src/lexora/inspect.py` + harness | T-CMP-104 | none | **Verified** | `inspect` checks header+Σframes+index+trailer == file length; harness asserts stored == disk |
| REQ-CMP-005 | Bounded block decoding memory | SPEC §4.4; RESOURCE_LIMITS | `src/lexora/container.py` (streaming) | T-CMP-105 (RSS profile) | none | **Verified** | LIM-01/02 enforced (E-RES-004); benchmarks/results-rss-core.json |
| REQ-CMP-006 | Unknown-ID clean refusal | SPEC §4.5 | `src/lexora/container.py` | T-CMP-106 (negative) | none | **Verified** | E-CMP-006; covered by test_reader_fuzz.py |
| REQ-EXP-001 | Candidate promotion gate | SPEC §5.2 per ADR-0001 (Accepted) | benchmark harness | T-EXP-101 | none | Not started | Gate normative; harness absent |
| REQ-EXP-002 | Train-split-only induction | CORPUS_POLICY (this batch) | lineage splitter | T-EXP-102 (audit) | none | Not started | Corpus absent (OQ-8) |
| REQ-EXP-003 | Retirement thresholds | BENCHMARK_PROTOCOL ablation | report schema | T-EXP-103 | none | Not started | — |
| REQ-FMT-001 | `.lxz` layout via ADR+vectors | [FORMAT_LXZ](FORMAT_LXZ.md) (**PROPOSED**) | `src/lexora/container.py` | T-FMT-101 conformance | none | **Verified** | ADR-0007 accepted; canonicalization + `.lxz` golden vectors tracked |
| REQ-FMT-002 | Resource-limit declarations enforced | FORMAT_LXZ limits fields | `src/lexora/container.py` | T-FMT-102 | none | **Verified** | LIM-01/LIM-02 clamped, `E-RES-004`; tests/test_reader_fuzz.py |
| REQ-FMT-003 | Must-understand/may-ignore flags | FORMAT_LXZ compat rules | `src/lexora/container.py` | T-FMT-103 synthetic | none | **Verified** | must-understand bits refused (`E-FMT-HEAD-002`), may-ignore bits tolerated; tests/test_format_flags.py (7 tests) |
| REQ-FMT-004 | `.lxdb` deferred | [FORMAT_LXDB](FORMAT_LXDB.md) proposal | — | — | — | Deferred | Intentional (blueprint §phase order) |
| REQ-BMK-001 | ≥1 GiB manifest, 70/10/20 lineage | CORPUS_POLICY | `benchmarks/harness.py` + corpus.py | T-BMK-101 split audit | none | **In progress** | corpus 1.054 GiB (manifest `c92cf578…`); protocol-scope run + sign-off open |
| REQ-BMK-002 | Pinned baselines incl. roles | SPEC §4.6 (ADR-0002/0003 Accepted) | `benchmarks/harness.py` SYSTEMS | T-BMK-102 | none | **Implemented** | zstd-19 and xz (CLI or liblzma) registered with ADR-0002/0003 roles; Brotli q11 and PPMd absent because the tools are not installed — documented in benchmarks/README.md |
| REQ-BMK-003 | Pass/Partial/Fail verdicts | SPEC §5.2 (ADR-0001 Accepted) | verdict generator | T-BMK-103 | none | Not started | No results until real run |
| REQ-BMK-004 | Per-doc/category/env reporting | BENCHMARK_PROTOCOL | report schema | T-BMK-104 | none | Not started | — |
| REQ-RES-001 | Streaming under ~4 GiB RAM | RESOURCE_LIMITS, PERFORMANCE_BUDGET | whole pipeline (streaming) | T-RES-101 RSS | none | **Verified** | flat peak RSS measured: encode 126 MiB, decode 34.8 MiB, canon 35.5 MiB — benchmarks/results-rss-core.json |
| REQ-RES-002 | Python range via ADR | DECISIONS OQ-7 | `pyproject.toml` | CI matrix | none | **Verified** | ADR-0005 accepted; `requires-python = ">=3.12,<4.0"` and CI runs 3.12 |
| REQ-RES-003 | Offline operation | INSTALLATION/BUILD_GUIDE | packaging | T-RES-103 smoke | none | Not started | Wheel vendoring plan missing |
| REQ-SEC-001 | Hostile-archive safety | SPEC §4; THREAT_MODEL (Batch D) | `src/lexora/container.py` + `zstd_core.py` | fuzz campaign | none | **Verified** | fuzz suites: refuse or decode-to-original, never crash; absolute limits enforced |
| REQ-SEC-002 | Clinical data isolation | CORPUS_POLICY | corpus tooling | policy audit | none | Not started | OQ-8 classification unknown |
| REQ-SEC-003 | AEAD encryption profile | ENCRYPTION_PROFILE (Batch D, if in scope) | — | KAT vectors | none | Out of current scope | Owner confirm scope |
| REQ-SEC-004 | Checksum refuse-on-mismatch | FORMAT_LXZ checksums | `src/lexora/container.py` | bit-flip tests | none | **Verified** | per-block SHA-256 refused on mismatch; bit-flip coverage in test_container_lxz.py + test_reader_fuzz.py |

## Reading notes

- "planned … — absent" means the path is a design intent, not repository content (verified 2026-10-15).
- Test IDs are placeholders assigned here so traceability rows can exist before tests; they become real when files land. That is honest bookkeeping, not claimed coverage.
- Any row moving to Verified requires: code present + named test passing + evidence link committed.
