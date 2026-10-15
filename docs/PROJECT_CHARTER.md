# LEXORA Project Charter

> **Status:** Draft — pending owner approval
> **Owner:** Dr. Sohil Momin (project owner)
> **Last verified:** 2026-10-15 (commit `816f58f`)
> **Related:** [Blueprint](../LEXORA_Full_Blueprint_Design_Master_Prompt.md) · [Requirements](PRODUCT_REQUIREMENTS.md) · [Glossary](GLOSSARY.md) · [Decisions](DECISIONS.md)

## Purpose

Define the problem LEXORA solves, its scope, constraints, and measurable success criteria, so every later design/implementation decision has a stable reference point.

## Scope

This charter covers the LEXORA prototype: a Python-first text cleaning + exact-compression system for document collections. It does **not** cover any production service, cloud deployment, or commercial packaging.

## Problem statement

Collections of textual documents (TXT, PDF, OCR'd scans — including English, Hindi, and Gujarati content) are compressed by generic tools that ignore internal structure. On low-resource hardware (~4 GiB RAM), it is difficult to exploit that structure safely while guaranteeing byte-exact recovery of the cleaned text. LEXORA aims to close that gap with measured, evidence-gated compression improvements over frozen baselines.

## Users & workloads

| User | Need |
|---|---|
| Archive owners / researchers | Store large multilingual text corpora smaller than Zstd-19/XZ achieve, with provable losslessness on canonical bytes |
| Low-resource workstation users | Run ingestion, compression, and decoding within ~4 GiB RAM, offline-capable |
| Developers of record-like datasets | Exploit per-record/template structure (numeric fields, repeated boilerplate) via cost-selected candidates |

## Goals

1. **G1 — Exactness:** `decode(encode(C)) == C` for all canonical byte strings `C`; enforced by round-trip verification at build time. *(normative)*
2. **G2 — Conservative cleaning:** Canonicalization is deterministic, versioned, minimal-risk; may be lossy vs. source but never silently so. *(normative)*
3. **G3 — Measured gains:** Any codec/candidate beats pinned baselines under a frozen benchmark protocol before being "kept"; total-size accounting counts every serialized byte (headers, dictionaries, side-data).
4. **G4 — Low-resource operation:** ~4 GiB RAM budget; bounded block/stream processing; no unbounded memory designs.
5. **G5 — Multilingual correctness:** Latin, Devanagari (Hindi), Gujarati handled correctly through canonicalization and tokenization.

## Proposed success targets *(not validated facts)*

| Target | Value | Status |
|---|---|---|
| Corpus size for benchmarks | ≥ 1 GiB, frozen manifest | Not yet assembled |
| Pass gate vs. best frozen baseline | ≥ 10% smaller total stored size | Proposed (blueprint §12) |
| Partial gate | ≥ 3% but < 10% | Proposed |
| Cleaning-error rate | ≤ 1% (measurement method undefined — open issue OQ-4 in [DECISIONS.md](DECISIONS.md)) | Needs definition |
| Baselines | Zstd-19 (core); Brotli q11, XZ/LZMA, PPMd as frozen comparison points | Versions not yet pinned |

## Constraints

- **Hardware:** ~4 GiB RAM target machine.
- **Language/runtime:** Python-first prototype (exact supported Python version = open decision).
- **Environment:** must work offline after dependency install.
- **Correctness priority:** losslessness > compression ratio > speed.
- **Evidence priority:** no claim ships without reproducible measurement.

## Non-goals

- Reconstructing original source/OCR bytes exactly (canonicalization is allowed to be lossy vs. source).
- General-purpose archiving (`.zip` replacement).
- Lossy text compression or summarization.
- Beating baselines on non-text data.
- Formal security certification or audited cryptography claims.

## Key risks

| Risk | Impact | Mitigation |
|---|---|---|
| Learned structures (dictionaries, grammars) leak sensitive corpus content | Privacy breach | Lineage-separated train/val/held-out splits; clinical data excluded from shared dictionaries by default ([CORPUS_POLICY.md] — planned Batch C) |
| Overfitting benchmarks; false "improvement" claims | Credibility loss | Frozen manifests, held-out sets, total-size accounting, pre-registered gates |
| Format churn breaking compatibility | Data loss | Versioned formats, ADRs before semantic changes, test vectors |
| Low-RAM target violated by naive implementations | Unusable product | Resource limits documented and tested (planned `RESOURCE_LIMITS.md`, Batch D) |
| Blueprint internal conflicts (see [DECISIONS.md](DECISIONS.md)) | Ambiguous spec | Resolve via ADRs before Phase 0 exit |

## Assumptions

- The blueprint file at repository root is the approved master design document.
- Zstandard (`zstandard` Python binding) will be the Core baseline codec.
- OCR (Tesseract) is optional and environment-dependent.

## Dependencies

- `zstandard` (Core), `brotli`, `lzma` (stdlib), `ppmd` (baselines); `pypdf`/similar (PDF text extraction); `pytesseract`+Tesseract (optional OCR). None installed/configured in this repository yet.

## Governance

- Source-of-truth hierarchy and no-fabrication rules are defined in the documentation master prompt (`LEXORA-DOCS-MASTER-PROMPT-1.0`) and enforced via [STATUS.md](STATUS.md)/[SESSION_LOG.md](SESSION_LOG.md) discipline.
- Material decisions require an accepted ADR listed in [DECISIONS.md](DECISIONS.md).

## Approval

**Not yet approved by project owner.** This charter becomes authoritative upon owner sign-off; until then it is a Draft that faithfully summarizes the blueprint.
