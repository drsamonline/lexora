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
| REQ-CAN-001 | Deterministic canonicalization | [CANONICALIZATION](CANONICALIZATION.md) §Determinism | planned `lexora/canon.py` — absent | T-CAN-101 (property) | none | Not started | Rule table unfrozen (P0-T6) |
| REQ-CAN-002 | UTF-8/no-BOM/LF policy per version | CANONICALIZATION §Output form | same | T-CAN-102 (golden) | none | Not started | Newline/BOM policy needs freeze |
| REQ-CAN-003 | Whitelisted rules only | CANONICALIZATION rule table CAN-R01…R09 | same | T-CAN-103 (invariant) | none | Not started | Rule table Proposed |
| REQ-CAN-004 | Canonicalizer version in archive | SPEC §2.4; FORMAT_LXZ header | container writer | T-CAN-104 | none | Not started | Depends on format freeze |
| REQ-CAN-005 | Devanagari/Gujarati safety | CANONICALIZATION §Scripts | canon + golden vectors | T-CAN-105 | none | Not started | Script vectors not authored |
| REQ-CAN-006 | Confidence-gated OCR correction + log | CANONICALIZATION CAN-R09; OCR_PIPELINE | ocr postprocess | T-CAN-106 | none | Not started | Threshold default unmeasured |
| REQ-CAN-007 | Cleaning ≤1% per ADR-0004 | [ADR-0004](ADR/ADR-0004-cleaning-error-metric.md) (Accepted) | sampling/review tooling planned | T-CAN-107 | metric defined; no run yet | Not started | Needs P3 sample review |
| REQ-CMP-001 | Byte-exact round trip | SPEC §3.1; COMPRESSION_ARCHITECTURE | planned `lexora/codec/zstd_block.py` | T-CMP-101 (property/fuzz) | none | Not started | Core invariant — must gate P1 exit |
| REQ-CMP-002 | Zstd core codec, IDs declared | SPEC §4; ADR-0002/0003 roles | codec registry (planned) | T-CMP-102 | none | Not started | Registry absent |
| REQ-CMP-003 | Cost-driven reproducible selection | [COST_MODEL](COST_MODEL.md) | selector (planned) | T-CMP-103 | none | Not started | Only Zstd initially ⇒ trivial selection |
| REQ-CMP-004 | Total serialized-byte accounting | COST_MODEL formula | size auditor (planned) | T-CMP-104 | none | Not started | Needed before any candidate claim |
| REQ-CMP-005 | Bounded block decoding memory | SPEC §4.4; RESOURCE_LIMITS | reader (planned) | T-CMP-105 (RSS profile) | none | Not started | Block-size limits undecided numerically |
| REQ-CMP-006 | Unknown-ID clean refusal | SPEC §4.5 | reader validation | T-CMP-106 (negative) | none | Not started | — |
| REQ-EXP-001 | Candidate promotion gate | SPEC §5.2 per ADR-0001 (Accepted) | benchmark harness | T-EXP-101 | none | Not started | Gate normative; harness absent |
| REQ-EXP-002 | Train-split-only induction | CORPUS_POLICY (this batch) | lineage splitter | T-EXP-102 (audit) | none | Not started | Corpus absent (OQ-8) |
| REQ-EXP-003 | Retirement thresholds | BENCHMARK_PROTOCOL ablation | report schema | T-EXP-103 | none | Not started | — |
| REQ-FMT-001 | `.lxz` layout via ADR+vectors | [FORMAT_LXZ](FORMAT_LXZ.md) (**PROPOSED**) | container writer | T-FMT-101 conformance | none | Proposed | Layout deliberately NOT invented |
| REQ-FMT-002 | Resource-limit declarations enforced | FORMAT_LXZ limits fields | reader | T-FMT-102 | none | Not started | Values pending budget doc |
| REQ-FMT-003 | Must-understand/may-ignore flags | FORMAT_LXZ compat rules | reader | T-FMT-103 synthetic | none | Not started | — |
| REQ-FMT-004 | `.lxdb` deferred | [FORMAT_LXDB](FORMAT_LXDB.md) proposal | — | — | — | Deferred | Intentional (blueprint §phase order) |
| REQ-BMK-001 | ≥1 GiB manifest, 70/10/20 lineage | CORPUS_POLICY | corpus tooling | T-BMK-101 split audit | none | Not started | OQ-8 |
| REQ-BMK-002 | Pinned baselines incl. roles | SPEC §4.6 (ADR-0002/0003 Accepted) | baseline runners | T-BMK-102 | none | Not started | External tools install guide needed |
| REQ-BMK-003 | Pass/Partial/Fail verdicts | SPEC §5.2 (ADR-0001 Accepted) | verdict generator | T-BMK-103 | none | Not started | No results until real run |
| REQ-BMK-004 | Per-doc/category/env reporting | BENCHMARK_PROTOCOL | report schema | T-BMK-104 | none | Not started | — |
| REQ-RES-001 | Streaming under ~4 GiB RAM | RESOURCE_LIMITS, PERFORMANCE_BUDGET | whole pipeline | T-RES-101 RSS | none | Not started | Reference machine undefined |
| REQ-RES-002 | Python range via ADR | DECISIONS OQ-7 | build config | CI matrix | none | Blocked on OQ-7 | — |
| REQ-RES-003 | Offline operation | INSTALLATION/BUILD_GUIDE | packaging | T-RES-103 smoke | none | Not started | Wheel vendoring plan missing |
| REQ-SEC-001 | Hostile-archive safety | SPEC §4; THREAT_MODEL (Batch D) | reader validation | fuzz campaign | none | Not started | Fuzz target after P1 |
| REQ-SEC-002 | Clinical data isolation | CORPUS_POLICY | corpus tooling | policy audit | none | Not started | OQ-8 classification unknown |
| REQ-SEC-003 | AEAD encryption profile | ENCRYPTION_PROFILE (Batch D, if in scope) | — | KAT vectors | none | Out of current scope | Owner confirm scope |
| REQ-SEC-004 | Checksum refuse-on-mismatch | FORMAT_LXZ checksums | reader | bit-flip tests | none | Not started | Hash algorithm undecided |

## Reading notes

- "planned … — absent" means the path is a design intent, not repository content (verified 2026-10-15).
- Test IDs are placeholders assigned here so traceability rows can exist before tests; they become real when files land. That is honest bookkeeping, not claimed coverage.
- Any row moving to Verified requires: code present + named test passing + evidence link committed.
