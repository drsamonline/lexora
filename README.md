<div align="center">

<h1>LEXORA</h1>

<p><b>Layered EXact-text Repository &amp; Adaptive compression architecture</b><br>
Canonicalize text conservatively, then compress it with guaranteed byte-exact recovery — <code>decode(encode(C)) == C</code> for every input.</p>

<p>
<a href="https://drsamonline.github.io/lexora/"><img alt="Landing page: live" src="https://img.shields.io/badge/landing%20page-live-84cc16"></a>
<a href="https://github.com/drsamonline/lexora/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/drsamonline/lexora/actions/workflows/ci.yml/badge.svg"></a>
<img alt="Tests: 192 passed (local)" src="https://img.shields.io/badge/tests-192%20passed%20(local)-informational">
<img alt="Python 3.12" src="https://img.shields.io/badge/python-3.12-blue">
<a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-green"></a>
<img alt="Version 0.0.1.dev1" src="https://img.shields.io/badge/version-0.0.1.dev1-orange">
</p>

<p>
<a href="https://drsamonline.github.io/lexora/"><b>Landing page</b></a> &nbsp;·&nbsp;
<a href="https://drsamonline.github.io/lexora/#start">Install from source</a> &nbsp;·&nbsp;
<a href="https://drsamonline.github.io/lexora/#benchmarks">Benchmarks</a> &nbsp;·&nbsp;
<a href="https://drsamonline.github.io/lexora/#faq">FAQ</a> &nbsp;·&nbsp;
<a href="docs/STATUS.md">Status</a> &nbsp;·&nbsp;
<a href="https://github.com/drsamonline/lexora">Repository</a>
</p>

<p><sub>Phase 1 prototype — no releases and no stable API yet; install from a source checkout. MIT © 2026 Dr. Sohil Momin.</sub></p>

</div>

---

# LEXORA

[![CI](https://github.com/drsamonline/lexora/actions/workflows/ci.yml/badge.svg)](https://github.com/drsamonline/lexora/actions/workflows/ci.yml)
![Tests](https://img.shields.io/badge/tests-192%20passed%20(local)%20-informational)
![Python](https://img.shields.io/badge/python-3.12-blue?logo=python&logoColor=white)
![License](https://img.shields.io/badge/license-MIT-green)

**Layered EXact-text Repository & Adaptive compression architecture**

> **Project status: Phase 1 prototype in development.** Documentation (Batches A–E) complete/drafted;
> early implementation code exists (canonicalization, Zstd core baseline, `.lxz` v0 container, benchmark harness,
> CLI app, experimental PySide6 GUI milestones M1–M3).
> Nothing here is a shipped or released feature. See [docs/STATUS.md](docs/STATUS.md) for the verified state.
> **Badge honesty note:** the CI badge reflects the real workflow in `.github/workflows/ci.yml`, but
> **GitHub Actions runs are paused by owner decision 2026-10-17** (free-tier minutes exhausted; OQ-15) —
> the badge shows the last historical run, not current state; verification gate is local (`pytest -q` + linkcheck
> before every commit). The *Tests* badge is a
> static snapshot of the locally verified suite (101 passed, re-verified 2026-10-17), not a live measurement.
> **Last verified:** 2026-10-17 against the current working branch (see git history).

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
| **Implemented** | Early Phase 1 prototype: conservative canonicalizer (`src/lexora/canonicalize.py`), Zstd core baseline (`src/lexora/zstd_core.py`), `.lxz` v0 container (`src/lexora/container.py`, ADR-0007), full CLI (`canon`/`zround`/`pipe`/`pack`/`unpack` — see [docs/CLI_REFERENCE.md](docs/CLI_REFERENCE.md)), benchmark harness (`benchmarks/harness.py` + `corpus.py`), test suite (192 passed locally, re-verified 2026-10-17) |
| **In progress** | GUI milestones M1–M3 landed & offscreen-tested (experimental, not released — PySide6 via `[gui]` extra, ADR-0008; see [docs/DESIGN_GUI.md](docs/DESIGN_GUI.md)); Phase 1 closure evidence awaiting owner verdict ([docs/P1_EVIDENCE_DRAFT.md](docs/P1_EVIDENCE_DRAFT.md)); GitHub Actions paused by owner (OQ-15) — local gate is `pytest -q` + linkcheck |
| **Planned** | TXT/PDF ingestion; experimental candidates (dictionaries, Re-Pair, bounded token PPM, numeric/record coding, template+residual); `.lxdb` database mode; optional encryption profile; GUI stretch items (batch queue, drag-and-drop, shortcuts) |

## Architecture overview (proposed)

```
TXT/PDF ──▶ Extraction (optional OCR) ──▶ Canonicalization (versioned, deterministic)
        ──▶ Compression (byte-exact, cost-selected codec) ──▶ .lxz archive (.lxdb later)
        ◀── decode ◀── verify: decode(encode(C)) == C enforced at build time
```

A normative specification (`docs/SPECIFICATION.md`) and detailed architecture documents exist as drafts (Batch B). To contribute, see [CONTRIBUTING.md](CONTRIBUTING.md); the release process is documented in `docs/RELEASE_PROCESS.md` (no releases exist yet).

## Supported inputs & current limitations

- **Design targets:** `.txt` (UTF-8/other encodings), `.pdf` (text-layer first; OCR for scanned pages), scripts: Latin, Devanagari, Gujarati.
- **Current reality:** byte-level canonicalization of raw text streams is implemented (rules CAN-R01/R02/R05 of the v0 rule set); TXT/PDF *file ingestion* is not implemented yet. Build scope is English-only per owner directive 2026-10-16 (Hindi/Gujarati deferred, not blocking).

## Installation / Quick start

Install from a source checkout (no published package exists):

```bash
pip install -e .            # core (Qt-free): zstandard pinned range, Python >=3.12,<4.0
pip install -e ".[dev]"     # + pytest for the test suite
pip install -e ".[gui]"     # + PySide6 for the experimental GUI (opt-in extra, ADR-0008)
```

Then try the CLI: `lexora --help` (subcommands: `canon`, `zround`, `pipe`, `pack`, `unpack` — documented in [docs/CLI_REFERENCE.md](docs/CLI_REFERENCE.md)) or the GUI launcher `lexora-gui` (requires the `[gui]` extra; exits 2 with guidance without it).

## Build & test commands

Verified in-container (2026-10-17):

```bash
python3 -m pytest -q                     # test suite (192 passed; addopts neutralizes a stale libtmux plugin)
QT_QPA_PLATFORM=offscreen python3 -m pytest -q   # same, incl. offscreen GUI widget tests (needs pyside6 + libegl1)
python3 scripts/linkcheck.py             # docs integrity gate — ALL INTERNAL LINKS OK
```

## Benchmarks

**No validated LEXORA-vs-baseline results exist.** The acceptance gates are defined in the blueprint (Pass ≥ 10%, Partial ≥ 3% smaller total stored size vs. best frozen baseline) and formalized in `docs/BENCHMARK_PROTOCOL.md`. Baselines: Zstandard level 19, plus pinned Brotli/XZ/PPMd comparisons per protocol. First published figures — Revision R1 in [docs/BENCHMARK_RESULTS.md](docs/BENCHMARK_RESULTS.md) (2026-10-16) — are a **Tier T1-gutenberg-p0 smoke baseline** (7.1 MB public-domain English text; Zstd-19 ratio 0.3004 vs XZ-9 0.2975 on that snapshot), not gate verdicts.

## Security & privacy notes

- No security guarantees are claimed. No formal review has been performed.
- Design intent: decoders enforce resource limits (bounded blocks, memory caps) to survive hostile archives; sensitive/clinical corpora must not train shared dictionaries by default.
- Vulnerability reporting instructions live in [SECURITY.md](SECURITY.md).

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

1. **Phase 0 (complete):** Documentation foundation, canonicalization decisions & test vectors, open conflicts resolved via delegated ADRs.
2. **Phase 1 (current):** Core Zstandard baseline + corpus manifest + benchmark harness — code landed; closure evidence awaiting owner verdict. GUI milestones M1–M3 landed experimentally alongside.
3. **Phase 2:** Ingestion & canonicalization with golden vectors.
4. **Phase 3+:** Experimental candidates, `.lxz` format freeze, `.lxdb`, optional encryption — each gated by measured evidence.

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
