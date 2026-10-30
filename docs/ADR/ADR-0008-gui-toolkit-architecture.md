# ADR-0008: GUI toolkit, packaging, and architecture constraints

> **Status:** **Accepted** (2026-10-17, Session 26) — **partly superseded 2026-10-29 by [ADR-0011](ADR-0011-gui-process-separation.md)**: decisions 2–3 assumed an in-process service layer calling the library, and the GUI is now a *client of the CLI* (process separation). The toolkit choice (PySide6) and the Qt-free-core constraint stand unchanged under the project owner's standing autonomous-decision delegation ("DECIDE UR SELF", 2026-10-16), consistent with ADR-0001…0007. Revocable/amendable by the owner at any time via a superseding ADR per policy.
> **Date:** 2026-10-17
> **Deciders:** Documentation architect, under standing owner delegation (not independent owner review)
> **Related:** [DESIGN_GUI.md](../DESIGN_GUI.md) (plan of record) · [CLI_REFERENCE.md](../CLI_REFERENCE.md) · [RESOURCE_LIMITS.md](../RESOURCE_LIMITS.md) · OQ-12 / OQ-13 / OQ-14 · [ADR-0009](ADR-0009-license-polyform-noncommercial.md) (PolyForm Noncommercial 1.0.0; supersedes ADR-0006's MIT) · [ADR-0007](ADR-0007-container-v0-freeze.md)

## Context / Problem

The CLI app scope is effectively complete (five subcommands; 108 tests passing, Session 26). DESIGN_GUI.md defines screens G1–G4 as the GUI MVP (GUI-M1) but deliberately left three decisions open: toolkit (OQ-12), packaging location (OQ-13), and whether the GUI exposes future dictionary compression (OQ-14). GUI-M1 cannot start without resolving OQ-12/OQ-13, and repo governance requires an accepted ADR **before** any GUI code exists (DESIGN_GUI §5: "Each milestone gets its own ADR/amendment before code").

Constraints in force:
- PolyForm Noncommercial license project (ADR-0006); core install must stay minimal — zstandard is the only runtime dependency today.
- GitHub Actions paused (OQ-15): all GUI verification must be runnable locally (offscreen Qt).
- English-only build scope (owner directive); Indic UI text is a later phase but the design must not preclude it.
- The GUI is a thin client of `src/lexora/*` — never a second implementation of core logic (DESIGN_GUI §2).

## Options considered

### Toolkit (OQ-12)
- **A. PySide6 (LGPL v3 + exception).** Native widgets, mature QThread/worker patterns, strong Unicode/text handling, first-class offscreen testing (`QT_QPA_PLATFORM=offscreen`, pytest-qt). LGPL permits distribution under other terms while preserving relink rights (dynamic linking, no source-taint). **Chosen.** — the LGPL-vs-PolyForm combination is flagged for a dependency-licence re-read in ADR-0009 Consequences; this ADR's toolkit decision itself is unaffected.
- **B. Tkinter (stdlib).** Zero dependencies, but weak table/tree views (G4 inspector needs columns + sortable rows), poor high-DPI text rendering, no mainstream worker/cancel idioms, ttk theming dead-end for a productivity app. Kept only as documented fallback if the Qt dependency budget is ever rejected.
- **C. PyQt6.** Same tech as A but GPL/commercial dual licensing adds friction against the project's noncommercial licence posture (mirrors ADR-0009 reasoning). Rejected.
- **D. Electron/web stack.** Hundreds of MB of runtime against RESOURCE_LIMITS ethos for a local file tool. Rejected.

### Packaging (OQ-13)
- **A. Same repo, optional extra `lexora[gui]`.** Single version train between library and GUI; parity tests (same input → byte-identical `.lxz` from CLI path vs GUI service layer) live next to the code they test; CLI users keep a Qt-free install because extras are opt-in. **Chosen.**
- **B. Sibling repo.** Independent release cadence nobody asked for, cross-repo CI coupling while Actions are paused, duplicated vector fixtures. Rejected.

## Decision

On acceptance:

1. **Toolkit = PySide6**, pinned as `pyside6>=6.6,<7` inside the new optional extra `[gui]` in `pyproject.toml`. Core package dependencies remain unchanged (`zstandard` only).
2. **Packaging = same repo, `pip install -e ".[gui]"`**; console entry point `lexora-gui` added ONLY when GUI-M1 code lands (no placeholder entry points before real code exist — master-prompt rule).
3. **Architecture = exactly the DESIGN_GUI §2 layering**: views/controllers → thin app-service adapter (job runner, progress, cancellation) → `lexora.canonicalize` / `lexora.zstd_core` / `lexora.container` (single source of truth). The GUI MUST NOT shell out to the CLI and MUST NOT re-implement canonicalization, codec, or container logic. Typed exceptions (`CanonicalizationError`, `CodecError`, `ContainerError`) map 1:1 to the exit-code semantics frozen in CLI_REFERENCE (0/2/3/4/5/6/7).
4. **Testing gate:** every GUI-M1+ test runs headless via `QT_QPA_PLATFORM=offscreen`; the golden-parity test (GUI pack path == CLI pack bytes, using `tests/vectors/lxz_format/`) is mandatory before GUI-M1 can be called complete. Local-only until Actions resume (OQ-15).
5. **OQ-14 provisional answer: format-minimal through GUI-M3.** The GUI exposes only capabilities present in the shipped library (canonicalize/pack/unpack/inspect/verify via `verify_archive()`). Dictionary/trained-model surfaces wait for an actual post-P1 library feature + its own ADR amendment — nothing to expose today.
6. **RESOURCE_LIMITS enforcement stays in the library reader**; the service layer passes caps through and surfaces refusals verbatim (no bypass, no silent clamping — mirrors the Session-26 `--block-size` exit-2 precedent on the CLI side).
7. All user-visible strings go through Qt translation (`tr()`) from the first line of GUI code, even though Phase 1 copy is English-only.

## Consequences

- (+) GUI-M1 is unblocked: next step is scaffolding `src/lexora/gui/` (empty package + service adapter skeleton) with the `[gui]` extra — in a session that has PySide6 installable; this environment may lack Qt wheels, so M1 kickoff must verify `pip install pyside6` availability FIRST.
- (+) One repo, one version train, parity tests colocated with vectors.
- (−) ~150–200 MB installed footprint for Qt in GUI venvs — acceptable because it is opt-in and documented in INSTALLATION.md at GUI-M2 packaging time.
- (−) LGPL attribution obligation ships with binaries (Qt notices file required at first GUI release; tracked here so it isn't forgotten).
- Neutral: Tkinter fallback (Option B) remains documented but unexercised; switching later requires a superseding ADR.

## Verification performed before accepting

- No GUI code exists anywhere in the repo (verified `grep -ri pyside|tkinter src/ tests/` → empty), so this ADR commits a decision without invalidating any implemented claim.
- DESIGN_GUI.md G1–G4 backings confirmed shipped: `container.pack/unpack/read_index/verify_archive` all exist and are tested (Session 25/26 suite: 108 passed).
