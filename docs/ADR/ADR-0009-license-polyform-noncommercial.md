# ADR-0009: Project license — PolyForm Noncommercial 1.0.0 (supersedes ADR-0006)

> **Status:** Accepted 2026-10-29 by explicit owner decision (owner replied "polyform" when the licence contradiction was put to them at the end of Session 39). Supersedes [ADR-0006](ADR-0006-license-mit.md).
> **Date:** 2026-10-29
> **Deciders:** Owner Dr. Sohil Momin (decision); documentation architect (reconciliation sweep, delegated)
> **Related:** [DECISIONS.md](../DECISIONS.md) OQ-5 · [ADR-0006](ADR-0006-license-mit.md) (superseded) · [RELEASE_PROCESS.md](../RELEASE_PROCESS.md) R3 · `LICENSE` (repo root) · `pyproject.toml` · [ADR-0008](ADR-0008-gui-toolkit-architecture.md) (GUI dependency licences)

## Context / Problem

The repository had drifted into a contradiction that no reader could resolve:

- `LICENSE` at repo root carried **PolyForm Noncommercial 1.0.0** (with the required `Required Notice:` line), and the README badge agreed with it;
- but `pyproject.toml` still declared `license = "MIT"`, README §License still said "MIT © 2026", `docs/STATUS.md` still listed MIT, and [ADR-0006](ADR-0006-license-mit.md) remained the Accepted decision of record for OQ-5.

The drift came from a series of `licence: PolyForm Noncommercial 1.0.0 (…)` commits (2026-10-17) that updated the licence text, the badge and several docs, but not the package metadata or the ADR. Package metadata and licence text disagreeing is the worst state to ship: an installer and a human read different terms from the same repository. Session 39 recorded the contradiction rather than resolving it, because relicensing is the owner's decision, not an agent's.

## Options considered

- **A. PolyForm Noncommercial 1.0.0** — keep what `LICENSE` already says. Source stays public and modifiable; noncommercial purposes (personal use, research, study, charities, educational institutions, public research and government bodies) are permitted; commercial use requires a separate licence from the owner. SPDX `PolyForm-Noncommercial-1.0.0`, `isOsiApproved = false`.
- **B. Revert to MIT** — restore the ADR-0006 posture, undo the licence commits. Maximum permissiveness, but it discards the owner's apparent intent in those commits.
- **C. PolyForm Small Business 1.0.0** — allows small commercial users, still excludes large ones.
- **D. Dual licensing (PolyForm for noncommercial + a paid commercial licence)** — a business decision layered on A; not a licence text of its own.

## Decision

**Adopt A: PolyForm Noncommercial 1.0.0.**

- `LICENSE` at repo root is **normative**, including its `Required Notice: Copyright 2026 Dr Sohil Momin` line. Per the licence's *Notices* section, anyone distributing the software or a work based on it must pass on these terms (or their URL) and that notice line.
- `pyproject.toml` declares the SPDX short identifier `PolyForm-Noncommercial-1.0.0`.
- README (badge, footer, §License), the docs site (`docs/index.md`, `docs/index.html` incl. its JSON-LD `license` field, `docs/404.html`), `docs/STATUS.md`, `docs/PROGRESS.md`, `docs/DECISIONS.md`, `docs/RELEASE_PROCESS.md` and the ADR index are reconciled to it.
- [ADR-0006](ADR-0006-license-mit.md) is marked **Superseded**, body unedited per the append-only policy; its filename is retained so existing links keep resolving.

## Consequences

1. **Source-available, not open source.** SPDX records `isOsiApproved = false` for this licence, and that is the accurate description: the code stays public and forkable, but every permission MIT granted for *commercial* use is gone. Copies already distributed under MIT remain MIT for their recipients — relicensing binds future distributions, not the past.
2. **Notice obligation is now a release gate.** R3 in [RELEASE_PROCESS.md](../RELEASE_PROCESS.md) requires the `LICENSE` file (with the `Required Notice:` line) to travel with every artifact — wheel, sdist, and the GUI packaging recipe (`packaging/`). A wheel without it is a licence violation, not just an omission.
3. **Dependency licences need a fresh read — flagged, not resolved here.** Two open items carry over or are sharpened by this change:
   - **PySide6 (LGPL-3.0 + exception, `[gui]` extra).** LGPL permits distribution under other terms provided recipients can relink/replace the library; dynamic linking satisfies that in practice. **Reviewed in Session 44 — [DEPENDENCY_LICENCE_REVIEW.md](../DEPENDENCY_LICENCE_REVIEW.md)** finds no licence conflict, bounds the exposure to the optional `[gui]` extra (the core install stays Qt-free), and lists the notices/relinking obligations that distribution would carry. The owner decision it asks for is still open (proposed as ADR-0010); until then this remains an open item, not a blocker.
   - **PyMuPDF (AGPL-3.0, planned PDF/OCR candidate).** ADR-0006 already flagged it; PolyForm does not satisfy AGPL's copyleft either, so the flag stands unchanged and unchanged in force: it is **not** a declared dependency and adding it requires its own ADR.
4. **Contributions arrive under the project licence.** Nothing in `CONTRIBUTING.md` promises a separate contributor agreement; a future external contribution would land under PolyForm unless the owner says otherwise. Worth a line in `CONTRIBUTING.md` if the project takes outside patches.
5. **Not a legal review.** Identical caveat to ADR-0006: this record documents an owner decision and the mechanical sweep that followed it. The owner is accountable; nothing here constitutes legal advice.
6. **Reversible.** If commercial reuse should be permitted later (options C or D), that is a further superseding ADR, and the sweep in this one is the template for it.

## Verification

- A word-boundary grep for `MIT` (`(^|[^A-Za-z_-])MIT([^A-Za-z_-]|$)`) over `*.md`, `*.toml`, `*.html` and `*.yml` returns no licence-position reference outside ADR-0006's historical body, this ADR, the ADR index/supersession rows, and the changelog/session-log history. **Note for future licence sweeps:** the first pass missed two *prose* claims in `docs/index.html` — the FAQ answer to "What is the licence…" and the second footer span — because the sweep looked at structured fields (JSON-LD, badge, footer link) and `grep -c MIT` was drowned by `RESOURCE_LIMITS`/`COMMITTED` noise. Both were caught by the word-boundary re-audit and fixed in the follow-up commit; the docs site is generated-looking HTML with duplicated copy, so it needs a prose read, not just a field check.
- `pip install -e .` succeeds and the built metadata reports `License-Expression: PolyForm-Noncommercial-1.0.0`.
- `python3 scripts/linkcheck.py` → all internal links OK.
- `python3 -m pytest -q` → unchanged suite result (this ADR touches no code).
