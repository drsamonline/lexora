# LEXORA Build Guide

> **Status:** Draft (describes the build as *planned*; no package exists yet — verified 2026-10-15)
> **Owner:** Documentation architect (delegated)
> **Related:** [INSTALLATION.md](INSTALLATION.md) · [DEVELOPMENT_SETUP.md](DEVELOPMENT_SETUP.md) · DEPENDENCY_POLICY.md *(Batch D)* · DECISIONS OQ-7

## Purpose & scope

How to produce a working LEXORA from source once P1-T1 lands, and what is true today. Today: the repository is documentation + `scripts/linkcheck.py` only; there is nothing to build.

## Current reality (verified 2026-10-15)

```text
python3 scripts/linkcheck.py   # works today; checks docs integrity
git status --short             # inspect tree state
```

No `pyproject.toml`, no package, no test suite, no CI.

## Planned build (P1-T1 onward — PROPOSED, not yet valid commands)

```text
# PROPOSED workflow after packaging decision (OQ-7 pins Python range):
python -m venv .venv
. .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -e ".[dev]"         # core deps: zstandard (+ pinned versions in pyproject)
pip install -e ".[ocr]"         # optional extra for PDF/OCR stack (OQ-10)
python -m pytest                # unit/integration/negative layers
```

Expected outputs above are intentionally not shown until they can be captured from real runs; when they can, this file gains an "Observed output" section with date + commit hash.

## Core vs optional dependencies (design intent)

| Tier | Contents | Notes |
|---|---|---|
| Core | Python stdlib + `zstandard` | Must install offline via vendored wheels (REQ-RES-003) |
| Ingest extras | PDF text-layer library (choice pending ADR at P3 planning) | Not needed for TXT path |
| OCR extra | Tesseract binary + language data hi/gu (OQ-10) | External binary; graceful-skip required if absent (REQ-ING-003) |
| Benchmark tools | `zstd` CLI, `brotli`, `xz`, PPMd-capable tool | Measurement-only per ADR-0002/0003; versions pinned into env.json |
| Dev | pytest, fuzzer, linters (selection ADR pending) | Never required by end users |

## Offline constraint

Target machine may lack internet. Plan: vendor wheelhouse (`pip download … -w wheels/`) documented here once versions are pinned; OCR binaries installed manually per OS notes below.

## Common failures (anticipated — hypotheses, labeled)

- Wheel ABI mismatch on old distros → pin manylinux wheels (hypothesis; confirm at P1).
- Tesseract traineddata missing for gu → pipeline must skip OCR with report (REQ-ING-003), not crash.
- Baseline tools absent → benchmark harness refuses to start with explicit checklist (never silently skips ⇒ would fake success).

## Windows / Linux notes

Both targeted (REF-4G allows either). Path handling must stay platform-neutral in archives (stored paths normalized in FORMAT_LXZ §compat — proposed).

## Release build

Deferred to P7; see RELEASE_PROCESS.md (Batch E). No release artifacts exist.
