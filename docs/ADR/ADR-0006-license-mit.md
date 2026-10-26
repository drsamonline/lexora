# ADR-0006: Project license — MIT

> **Status:** Accepted 2026-10-15 under standing owner delegation (resolves OQ-5). Basis: explicit owner instruction "oq5 … start working on them" — the only candidate decision path left after presenting options was to adopt the recommendation and record it honestly as delegated, revocable. Not an independent legal review; the owner may supersede at any time.
> **Date:** 2026-10-15
> **Deciders:** Documentation architect (delegated); owner Dr. Sohil Momin accountable
> **Related:** [DECISIONS.md](../DECISIONS.md) OQ-5 · [RELEASE_PROCESS.md](../RELEASE_PROCESS.md) R3 · `LICENSE` (repo root) · `pyproject.toml`

## Context / Problem

No `LICENSE` file existed; README said "Not yet selected"; release gate R3 was open. A public repo without a license means all rights reserved by default, blocking reuse terms, badges, and any release.

## Options considered

- **A. MIT** — permissive, minimal obligations, standard for prototype-stage tooling. Compatible with every runtime dependency in use or planned here: `zstandard` (BSD-3-Clause), CPython (PSF), `pytest` (MIT), `scikit-learn` (BSD-3-Clause, verified from its wheel METADATA 2026-10-15: `License-Expression: BSD-3-Clause`).
- **B. Apache-2.0** — adds an express patent grant. Reasonable if contributor patents become a concern; heavier text, still dependency-compatible.
- **C. Keep all-rights-reserved** — blocks releases and community use; contradicts the project's stated intent of a public benchmarked artifact.

## Decision

Adopt **A: MIT**, copyright line "Copyright (c) 2026 Dr. Sohil Momin". Canonical text taken verbatim from the OSI/choosealicense PolyForm Noncommercial template (`github/choosealicense.com`, fetched 2026-10-15) with only the `[year]`/`[fullname]` placeholders replaced. `pyproject.toml` declares `license = "MIT"` (SPDX).

If the owner later prefers Apache-2.0 (e.g., for patent coverage once Rust/PPMd components ship), supersede this ADR; no code changes beyond the LICENSE file and pyproject metadata would be required.

## Consequences and trade-offs

- (+) Release gate R3 satisfied; README can state a license.
- (+) No copyleft contamination risk for downstream closed integrations; acceptable at prototype stage.
- (−) No express patent grant. Mitigation: prototype has no patented algorithms; revisit at P5 (packaging/Rust) via a superseding ADR if needed.

## Security / performance / compatibility impact

None. Dependency license audit recorded above; PyMuPDF (planned PDF extraction candidate, AGPL-3.0) is flagged in the blueprint as subject to dependency/license review and is **not** a declared dependency — adding it later requires revisiting this ADR (AGPL incompatibility with MIT-only relicensing).

## Verification

- `LICENSE` present at repo root with canonical MIT text (diff vs. OSI template: placeholders substituted only).
- `python -m pytest` unaffected; package metadata build includes the license field (verified in Session 14 test run).
