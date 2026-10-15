# LEXORA

**Layered EXact-text Repository & Adaptive compression architecture**

> **Project status: In development — design & documentation phase.**
> No implementation code exists yet. Nothing on this page should be read as a shipped feature.
> **Last verified:** 2026-10-15 against repository commit `816f58f`.

---

## What is LEXORA?

LEXORA is a text-cleaning and **exact-compression** system for document collections (TXT, PDF, optionally OCR'd scans). It:

1. **Ingests** TXT and PDF files (OCR optional for scanned pages).
2. **Canonicalizes** the extracted text conservatively into deterministic UTF-8 bytes (this step *may* be lossy relative to the source, by design).
3. **Compresses** those canonical bytes with **guaranteed byte-exact recovery**: `decode(encode(C)) == C` for every input.

The core invariant: **canonicalization may lose information relative to the original source; compression after canonicalization must never lose a single byte.**

## Why?

Generic compressors (Zstandard, XZ, Brotli) treat text as opaque bytes. Document collections contain structure — repeated boilerplate, templates, records, multilingual text (English, Hindi, Gujarati) — that a compressor can exploit if it is allowed to *learn* representations safely. LEXORA's goal is to beat frozen generic baselines on total stored size while preserving strict correctness and running on low-resource hardware (~4 GiB RAM).

## Goals

- Byte-exact losslessness after canonicalization — always, provably, via round-trip verification.
- Conservative, versioned canonicalization with golden test vectors.
- Cost-driven codec/candidate selection: every candidate competes against pinned baselines, and **every serialized byte counts** in the cost model.
- Operate within a ~4 GiB RAM budget with bounded, streaming/block-based processing.
- Multilingual support: English, Hindi (Devanagari), Gujarati.

## Non-goals (current scope)

- Reconstructing original OCR output or source PDF layout bit-for-bit.
- Claiming any performance advantage over Zstd/Brotli/XZ/PPMd before reproducible benchmark evidence exists (**none exists yet**).
- Being a general-purpose archive format.

## Features by maturity

| Status | Capability |
|---|---|
| **Implemented** | *(nothing yet — repository contains only the blueprint and documentation)* |
| **In progress** | Documentation system (Batches A–E drafted: governance, architecture & spec, engineering execution, security & operations, GitHub & release polish — pending owner review) |
| **Planned** | Core Zstandard baseline codec; TXT/PDF ingestion; conservative canonicalizer; benchmark harness; `.lxz` archive format (proposed); experimental candidates (dictionaries, Re-Pair, bounded token PPM, numeric/record coding, template+residual); `.lxdb` database mode; optional encryption profile |

## Architecture overview (proposed)

```
TXT/PDF ──▶ Extraction (optional OCR) ──▶ Canonicalization (versioned, deterministic)
        ──▶ Compression (byte-exact, cost-selected codec) ──▶ .lxz archive (.lxdb later)
        ◀── decode ◀── verify: decode(encode(C)) == C enforced at build time
```

A normative specification (`docs/SPECIFICATION.md`) and detailed architecture documents exist as drafts (Batch B). To contribute, see [CONTRIBUTING.md](CONTRIBUTING.md); the release process is documented in `docs/RELEASE_PROCESS.md` (no releases exist yet).

## Supported inputs & current limitations

- **Design targets:** `.txt` (UTF-8/other encodings), `.pdf` (text-layer first; OCR for scanned pages), scripts: Latin, Devanagari, Gujarati.
- **Current limitation:** none of this is implemented. The repository contains the approved blueprint and documentation only.

## Installation / Quick start

Not yet available. There is no package, CLI, or build configuration in this repository. When implementation lands, installation instructions will appear in `docs/INSTALLATION.md` and be verified against real commands before being documented here.

## Build & test commands

None exist yet. Do not run assumed commands. Verified commands will be added to `docs/BUILD_GUIDE.md` and `docs/TESTING_GUIDE.md` only once tooling is actually configured.

## Benchmarks

**No validated benchmark results exist.** The acceptance gates are defined in the blueprint (Pass ≥ 10%, Partial ≥ 3% smaller total stored size vs. best frozen baseline) and will be formalized in `docs/BENCHMARK_PROTOCOL.md`. Baselines: Zstandard level 19, plus pinned Brotli/XZ/PPMd comparisons per protocol.

## Security & privacy notes

- No security guarantees are claimed. No formal review has been performed.
- Design intent: decoders enforce resource limits (bounded blocks, memory caps) to survive hostile archives; sensitive/clinical corpora must not train shared dictionaries by default.
- Vulnerability reporting instructions will live in `SECURITY.md` once contact details are confirmed by the project owner.

## Documentation index

Start at **[docs/index.md](docs/index.md)**. Key entry points:

| Document | Purpose |
|---|---|
| [docs/STATUS.md](docs/STATUS.md) | Current verified project state |
| [docs/NEXT_SESSION.md](docs/NEXT_SESSION.md) | Resume card for the next work session |
| [docs/PROJECT_CHARTER.md](docs/PROJECT_CHARTER.md) | Problem, scope, constraints, success criteria |
| [docs/PRODUCT_REQUIREMENTS.md](docs/PRODUCT_REQUIREMENTS.md) | Numbered requirements (`REQ-*`) |
| [docs/GLOSSARY.md](docs/GLOSSARY.md) | Terminology |
| [docs/DECISIONS.md](docs/DECISIONS.md) | ADR index & open decisions |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Ground rules, workflow, PR guidance |
| [CHANGELOG.md](CHANGELOG.md) | Change history |
| [LEXORA_Full_Blueprint_Design_Master_Prompt.md](LEXORA_Full_Blueprint_Design_Master_Prompt.md) | Approved master design blueprint (source of truth) |

## Roadmap (summary)

1. **Phase 0 (now):** Documentation foundation, freeze canonicalization decisions & test vectors, resolve open conflicts.
2. **Phase 1:** Core Zstandard baseline + corpus manifest + benchmark harness.
3. **Phase 2:** Ingestion & canonicalization with golden vectors.
4. **Phase 3+:** Experimental candidates, `.lxz` format proposal, `.lxdb`, optional encryption — each gated by measured evidence.

Details in `docs/ROADMAP.md` (Batch C).

## License

MIT © 2026 Dr. Sohil Momin — see [LICENSE](LICENSE). Chosen via owner instruction on 2026-10-15 (resolves OQ-5; recorded as [ADR-0006](docs/ADR/ADR-0006-license-mit.md), revocable by the owner like prior delegated ADRs).

## Project owner

Dr. Sohil Momin.

---

*This README makes no claim about tests, CI, coverage, releases, or badges — none exist. Badges will be added only when backed by real workflows and services.*
