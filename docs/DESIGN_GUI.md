# LEXORA Desktop GUI — Design Plan (Draft for owner review)

**Status:** Plan v0.2 (Session 26): toolkit/packaging decisions **resolved by accepted [ADR-0008](ADR/ADR-0008-gui-toolkit-architecture.md)** (PySide6; same repo via `[gui]` extra; OQ-14 provisionally format-minimal). §3/§8 below are annotated accordingly. Implementation still deferred until the CLI app is declared complete. Prior: Draft v0.1 (2026-10-17, Session 24). Owner directive: plan the GUI and its parts
now; implementation is **deferred until the whole CLI app is complete** (see
[ROADMAP](ROADMAP.md) / [PHASES](PHASES.md)). This document introduces no code and makes no
implemented claims. All GUI features map to capabilities that already exist or are planned as
CLI/library features — the GUI is a thin layer, never a second implementation of core logic.

## 1. Purpose & scope

A desktop application for non-terminal users to: ingest raw text files, canonicalize them,
pack them into `.lxz` archives, unpack/verify archives, and browse archive contents/metadata.
English-only app-build scope per owner directive (Phase 1); Indic-language UI text rendering
is a later-phase concern, but the design must not preclude it (Unicode-first widgets).

**Non-goals (v0 GUI):** corpus/benchmark tooling (owner-facing, stays CLI), OCR pipeline
(Phase 3+, separate surface), encryption-profile UI (until ENCRYPTION_PROFILE decisions land).

## 2. Architecture principle: GUI = client of library API only

```
┌──────────────────────────────┐
│ GUI shell (Qt Widgets)       │  views/controllers only; no business logic
├──────────────────────────────┤
│ App service layer            │  one thin adapter: async job runner, progress, cancellation
├──────────────────────────────┤
│ src/lexora/* (core library)  │  canonicalize, zstd_core, container — THE single source of truth
└──────────────────────────────┘
```

- The GUI imports `lexora.canonicalize`, `lexora.zstd_core`, `lexora.container` directly.
  It does **not** shell out to `lexora` CLI (avoids arg-quoting bugs and keeps exit-code
  semantics internal). Exit codes 0/3/4/5/6/7 from CLI_REFERENCE map 1:1 to typed exceptions
  (`CanonicalizationError`, `CodecError`, `ContainerError`) which the service layer renders.
- Everything the GUI displays must be produced by already-tested library functions; any new
  capability (e.g. streaming block preview) lands in the library + tests first, then surfaces.
- Long operations run on worker threads/QThreads with cooperative cancellation; UI thread
  never touches file I/O of payload data.

## 3. Technology choice (proposed ADR candidate — see §7)

| Layer | Proposal | Rationale / alternatives |
|---|---|---|
| Toolkit | **PySide6 (LGPL)** — ✅ decided, [ADR-0008](ADR/ADR-0008-gui-toolkit-architecture.md) Accepted (S26) | Native feel, mature threading, good Unicode/text handling. Tkinter (stdlib, zero deps) is fallback if dependency budget matters; PyQt6 rejected (GPL/commercial licensing friction vs the project's noncommercial licence posture, cf. ADR-0009 reasoning). Electron/web rejected (size, memory vs RESOURCE_LIMITS ethos). |
| Packaging | `pyproject.toml` optional extra `[gui]` → PyPI wheel unchanged for CLI users; later `pyinstaller` build recipe in BUILD_GUIDE | Keeps core install dependency-free of Qt. |
| Theming/i18n | Qt Designer `.ui` files or programmatic widgets; all strings through `tr()` from day 1 | Even though Phase 1 UI copy is English-only, this unblocks Indic localization later without rework. |

## 4. Screens (parts) and feature mapping

| # | Part | Function | Backing (exists?) | Phase |
|---|---|---|---|---|
| G1 | **Main window / workspace** | Open-file pane, action ribbon, status bar; recent files | `container.read_index` (yes), file dialogs | GUI-M1 |
| G2 | **Pack view** | Choose canonicalized input (or "canonicalize first" checkbox), level slider 1–22, block size, output path; progress; result summary (bytes in/out, ratio) | `canonicalize()` + `container.pack()` — both implemented & tested | GUI-M1 |
| G3 | **Unpack view** | Choose `.lxz`, target path; refuse-before-write banner mirrors exit-7 semantics; atomic write feedback | `container.unpack()` (yes) | GUI-M1 |
| G4 | **Archive inspector** | Table of blocks (index entries: offset, comp size, raw size, SHA-256 prefix), header fields, tamper-check button ("verify all") | `read_index` (yes); per-block verify exists inside reader — needs small public `verify_archive()` API | GUI-M1 (after tiny lib addition) |
| G5 | **Text preview** | Read-only preview of canonicalized/plain text with encoding warning banner (declared-vs-detected), line numbers | canonicalizer meta (library has `canonicalize_with_meta`) | GUI-M2 |
| G6 | **Diagnostics panel** | Structured error display (error code names from ERROR_HANDLING/CLI_REFERENCE), copyable log, log file viewer | exceptions + LOGGING_AND_DIAGNOSTICS | GUI-M2 |
| G7 | **Settings** | default level/block-size, temp dir, theme, language stub | app-level only | GUI-M2 |
| G8 | **Batch queue** | drag-drop multiple files → pack/unpack queue with per-item status | loops over same APIs | GUI-M3 (stretch) |

Dependency note: G1–G4 constitute a usable MVP ("open app, pack, unpack, inspect"). Nothing
in the GUI depends on benchmark/corpus outcomes, so it can start the moment the CLI app is
declared feature-complete for Phase 1 (P1 tasks closed).

## 5. Milestones

- **GUI-M1 (MVP):** G1–G4. Acceptance: round-trip a ≥100 MB canonical file entirely via GUI;
  every refusal mode reachable in `tests/test_container_lxz.py` reproducible in the inspector
  with identical messaging; no UI freeze > 50 ms during those ops (worker-thread proof test).
- **GUI-M2:** G5–G7 + packaging recipe (wheel extra, Linux `.desktop`, basic macOS/Windows
  smoke builds) + screenshot-driven docs page. *(Status S31: LANDED — G5/G6 panels (M2b),
  G7 settings + `packaging/` recipe + `scripts/gen_screenshots.py` with committed
  `docs/assets/` screenshots (M2c). macOS/Windows builds remain documented-but-untested;
  see packaging/README.md smoke ban.)*
- **GUI-M3 (optional):** G8 batch queue, OS file associations for `.lxz`, tray completion notes.

Each milestone gets its own ADR/amendment before code (same governance as everything else here).

## 6. Testing strategy for GUI

- Service-layer adapter unit-tested headless (pytest-qt, offscreen platform plugin
  `QT_QPA_PLATFORM=offscreen` in CI when Actions resume).
- Golden parity tests: same input → GUI pack path produces byte-identical `.lxz` as CLI pack
  (reuses existing lxz vectors under `tests/vectors/lxz_format/`).
- Manual smoke checklist per release (RELEASE_PROCESS additions).

## 7. Security & limits carried over

All RESOURCE_LIMITS caps enforced at the service layer before invoking library calls (the
reader already refuses oversized headers/indexes — GUI must surface, not bypass). Threat-model
items relevant to GUI: arbitrary-path writes mitigated by save-dialog default + explicit
confirm on overwrite (mirrors CLI atomic-rename discipline); no elevation; no network.

## 8. Open questions for owner (new OQ candidates)

- ~~**OQ-12:** Confirm toolkit~~ — **RESOLVED S26: PySide6** via [ADR-0008](ADR/ADR-0008-gui-toolkit-architecture.md) (Tkinter kept as documented fallback; superseding ADR required to switch).
- ~~**OQ-13:** Same repo vs sibling~~ — **RESOLVED S26: same repo, optional `[gui]` extra** (core install stays Qt-free).
- **OQ-14:** Dictionary/trained-model exposure — **provisionally answered in ADR-0008 decision 5: format-minimal through GUI-M3**; revisit when such a library feature actually lands. Owner may override.

## 9. What will NOT happen until owner says so

No GUI code, no PySide6 dependency, no ADR acceptance for the toolkit yet — this document is
a plan artifact only, consistent with the repo rule that docs describe reality: nothing here
claims an implemented UI.
