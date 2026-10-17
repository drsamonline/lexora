# Next Session Resume Card

**Last verified state:** 2026-10-17, Sessions 27–28 complete. **GUI-M1 landed: service adapter (`src/lexora/gui/service.py`, Qt-free thin client over canonicalize/zstd_core/container with exception↔exit-code parity + golden byte-parity test vs CLI) + G1 window shell (`app.py`: pack/unpack/inspect views, lazy Qt only) + launcher (`lexora-gui` script, `python -m lexora.gui` via `__main__.py`; headless-safe: `--help`/`--version` answered before any Qt import rc 0, unknown opts rc 2, offscreen auto-fallback when no DISPLAY).** Suite **148 passed**; linkcheck OK. Environment: PySide6 6.12 installs in-container but fresh containers need `pip install pyside6` AND `apt-get install -y libegl1` (offscreen Qt aborts without it; ~673 MB wheel). Phase 1 posture unchanged: In progress pending two evidence items (editable-install note, peak-RSS-vs-budget owner verdict). GitHub Actions PAUSED (OQ-15); local gate = `python3 -m pytest -q` + `python3 scripts/linkcheck.py`. Sessions 20–28 commits remain local-only (`.vault/github_token.txt` absent). Published benchmark revisions unchanged: R1 + R2; no ADR-0001 verdict.
**Current phase:** GUI-M2 job runner (owner directive: build whole app; skip Actions until complete). English-only build scope.
**Branch/commit:** working branch (verify with `git log --oneline -3`).
**Working-tree state:** Clean after Session 28 commit.

## Read first
- [ ] docs/SESSION_LOG.md (Sessions 27–28 last)
- [ ] docs/ADR/ADR-0008-gui-toolkit-architecture.md (binding GUI constraints — obeyed so far; keep it that way)
- [ ] docs/DESIGN_GUI.md §5 milestones (GUI-M2 scope: job runner, cancel, progress, G5/G6 panels)
- [ ] src/lexora/gui/service.py `_make_qthread_worker` stub (the M2 seam)
- [ ] docs/TASK_BREAKDOWN.md GUI milestones table (M1 Landed / M2 next)

## Tasks in order
1. **Qt env setup check:** `QT_QPA_PLATFORM=offscreen python3 -c "import PySide6"` — if ImportError on libEGL, run `apt-get install -y libegl1` and `pip install pyside6` first (record in DEVELOPMENT_SETUP if still missing there).
2. **GUI-M2 job runner:** replace the `_make_qthread_worker` stub with a real QThread-based worker: start/cancel/progress callbacks driven from AppService ops (chunk-level progress where container APIs allow), wired into `app.py` (Run button → async job, status bar progress, cancel button). Offscreen tests only: simulate jobs, assert cancellation semantics and JobResult parity; NO business logic in widgets. Keep suite green throughout; add tests to `test_gui_app_offscreen.py` or new `test_gui_jobs.py`.
3. **G5 preview / G6 diagnostics panels (DESIGN_GUI MVP list):** preview = canonicalization diff-style text panel fed by `AppService` canon ops; diagnostics = exit-code/error banner history (uses FileOpError/ContainerError.code already surfaced by service).
4. **P1 evidence backfill (standing):** draft (do NOT publish) peak-RSS-vs-PERFORMANCE_BUDGET note from `benchmarks/results-r3.json` for owner verdict; then PHASES P1 → Complete candidate ONLY if both evidences land.
5. **Corpus growth toward genuine R3 (English-only):** ≥1 GiB Tier-1 expansion via harness `corpus-fetch` → `corpus-commit` → `manifest` → `verify` → `audit-splits` → `run --revision 3 --reps 3`; owner review before publishing. Track OQ-8.
6. **Push (when token available):** pushes allowed while Actions paused. GIT_ASKPASS pattern, never embed credentials.
7. Owner review backlog: ADR-0007 amendments revocable; ADR-0008 accepted under delegation (supersedable); OQ-9 semver; OQ-10 OCR tooling; ERROR_HANDLING severity/recovery sections Draft; no ADR-0001 verdict until corpus meets protocol scope.

## Acceptance criteria
- [ ] `python3 scripts/linkcheck.py` → ALL INTERNAL LINKS OK (exit 0) — re-verify after any edit.
- [ ] `python3 -m pytest -q` → **148 passed** baseline (addopts neutralizes libtmux; do not remove unless the plugin is gone from images for good).
- [ ] No GitHub Actions runs triggered without owner sign-off (OQ-15 pause stands).
- [ ] GUI obeys ADR-0008: thin client (no CLI shelling — subprocess only inside TESTS), lazy Qt imports (AST-enforced test must stay green), core install stays Qt-free, every new widget path covered offscreen.
- [ ] `lexora-gui --help`/`--version` keep working on bare headless boxes (regression tests exist — don't break them).
- [ ] Any published number carries its corpus-tier label; STATUS/PROGRESS/SESSION_LOG/NEXT_SESSION/README/CHANGELOG agree; commit hashes real.
- [ ] No ADR-0001 verdict until corpus meets BENCHMARK_PROTOCOL scope; no new *published* revision without a manifest change.
