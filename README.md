# LEXORA

[![CI](https://github.com/drsamonline/lexora/actions/workflows/ci.yml/badge.svg)](https://github.com/drsamonline/lexora/actions/workflows/ci.yml)
![Tests](https://img.shields.io/badge/tests-35%20passed-informational)
![Python](https://img.shields.io/badge/python-3.12-blue?logo=python&logoColor=white)
![License](https://img.shields.io/badge/license-MIT-green)

**Layered EXact-text Repository & Adaptive compression architecture**

> **Project status: Phase 1 prototype in development.** Documentation (Batches A–F) drafted;
> early implementation code exists (canonicalization, Zstd core baseline, benchmark harness).
> Nothing here is a shipped or released feature. See [docs/STATUS.md](docs/STATUS.md) for the verified state.
> **Badge honesty note:** the CI badge reflects the real workflow in `.github/workflows/ci.yml`
> (added 2026-10-15; its first-run result will be recorded in the session log). The *Tests* badge is a
> static snapshot of the locally verified suite (35 passed, re-verified 2026-10-15), not a live measurement.
> **Last verified:** 2026-10-15 against local branch `main` (see git history).

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
- Claiming any performance advantage over Zstd/Brotli/XZ/PPMd before reproducible benchmark evidence exists (**no LEXORA-vs-baseline evidence exists**; the only published numbers, Revision R1, are baseline-vs-baseline on a Tier-1 smoke corpus — see [docs/BENCHMARK_RESULTS.md](docs/BENCHMARK_RESULTS.md)).
- Being a general-purpose archive format.

## Features by maturity

| Status | Capability |
|---|---|
| **Implemented** | Early Phase 1 prototype: conservative canonicalizer (`src/lexora/canonicalize.py`), Zstd core baseline (`src/lexora/zstd_core.py`), CLI scaffold, benchmark harness (`benchmarks/harness.py`), test suite (35 passed locally) |
| **In progress** | Phase 1 baseline metrics on real corpus data; CI first run (workflow added 2026-10-15); documentation Batches A–F pending owner review |
| **Planned** | TXT/PDF ingestion; `.lxz` archive format (proposed); experimental candidates (dictionaries, Re-Pair, bounded token PPM, numeric/record coding, template+residual); `.lxdb` database mode; optional encryption profile |

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

**No validated LEXORA-vs-baseline results exist.** The acceptance gates are defined in the blueprint (Pass ≥ 10%, Partial ≥ 3% smaller total stored size vs. best frozen baseline) and formalized in `docs/BENCHMARK_PROTOCOL.md`. Baselines: Zstandard level 19, plus pinned Brotli/XZ/PPMd comparisons per protocol. First published figures — Revision R1 in [docs/BENCHMARK_RESULTS.md](docs/BENCHMARK_RESULTS.md) (2026-10-16) — are a **Tier T1-gutenberg-p0 smoke baseline** (7.1 MB public-domain English text; Zstd-19 ratio 0.3004 vs XZ-9 0.2975 on that snapshot), not gate verdicts.

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

*This README's badges are backed by real artifacts: the CI badge points to `.github/workflows/ci.yml`,
the License badge to [LICENSE](LICENSE), and the Python badge to `requires-python` in `pyproject.toml`.
No coverage, release, or download badges exist — those claims are not yet true. Badges will be removed
or corrected if the underlying workflows/services are removed or fail.*
