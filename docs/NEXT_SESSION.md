# Next Session Resume Card

**Last verified state:** 2026-10-17, Session 30 complete. **GUI-M2b landed: G5 preview view (Qt-free pure renderer `format_preview_text` — canon audit header + line-numbered canonicalized text, 64 KiB render cap), G4 inspector now renders the full block-index table (`format_inspect_text`), G6 diagnostics = append-only banner history capped at 50 entries.** Prior: Session 29 job runner. **GUI-M2 job runner landed: Qt-free job core in `src/lexora/gui/service.py` (`CancelToken`, `JobCancelled`, staged cancel-aware `pack_file_job`/`unpack_file_job` — cancel checked before every stage, never reaches write after cancellation; bounds refusals identical to sync paths) + `JobRunner` QThread adapter (progressed/finished/cancelled/failed signals, queued connections, direct-callable hooks for non-Qt consumers, lazy Qt inside `_make_qthread_worker`). `app.py` pack/unpack now async with QProgressBar + Cancel; inspect stays sync.** Prior: Session 28 GUI-M1 (service adapter + G1 shell + headless launcher); Session 27 scaffold. Suite **162 passed**; linkcheck OK. Environment: PySide6 6.12 installs in-container but fresh containers need `pip install pyside6` AND `apt-get install -y libegl1` (offscreen Qt aborts without it; ~673 MB wheel). Phase 1 posture unchanged: In progress pending two evidence items (editable-install note, peak-RSS-vs-budget owner verdict). GitHub Actions PAUSED (OQ-15); local gate = `python3 -m pytest -q` + `python3 scripts/linkcheck.py`. Sessions 20–30 commits remain local-only (`.vault/github_token.txt` absent). Published benchmark revisions unchanged: R1 + R2; no ADR-0001 verdict.
**Current phase:** GUI-M2c wrap-up (owner directive: build whole app; skip Actions until complete). English-only build scope.
**Branch/commit:** working branch (verify with `git log --oneline -3`).
**Working-tree state:** Clean after Session 30 commit.

## Read first
- [ ] docs/SESSION_LOG.md (Session 30 last)
- [ ] docs/ADR/ADR-0008-gui-toolkit-architecture.md (binding GUI constraints — obeyed so far; keep it that way)
- [ ] docs/DESIGN_GUI.md §5 milestones (GUI-M2 scope: job runner, cancel, progress, G5/G6 panels)
- [ ] src/lexora/gui/service.py `JobRunner`/‘_make_qthread_worker’ (M2 landed — extend, don't reinvent)
- [ ] docs/TASK_BREAKDOWN.md GUI milestones table (M1 Landed / M2 Partially landed — M2b pending)

## Tasks in order
1. **Qt env setup check:** `QT_QPA_PLATFORM=offscreen python3 -c "import PySide6"` — if ImportError on libEGL, run `apt-get install -y libegl1` and `pip install pyside6` first (record in DEVELOPMENT_SETUP if still missing there).
2. **GUI-M2c closure:** G7 settings (persist default level/block-size; app-level only, no format impact) + packaging recipe per DESIGN_GUI §5 (wheel `[gui]` extra exists; add Linux `.desktop` file, macOS/Windows smoke notes) + screenshot-driven docs page (headless offscreen screenshots via QWindow.grab or QTest grabWidget committed under docs/assets).
3. **P1 evidence backfill (standing):** draft (do NOT publish) peak-RSS-vs-PERFORMANCE_BUDGET note from `benchmarks/results-r3.json` for owner verdict; then PHASES P1 → Complete candidate ONLY if both evidences land.
4. **Corpus growth toward genuine R3 (English-only):** ≥1 GiB Tier-1 expansion via harness `corpus-fetch` → `corpus-commit` → `manifest` → `verify` → `audit-splits` → `run --revision 3 --reps 3`; owner review before publishing. Track OQ-8.
6. **Push (when token available):** pushes allowed while Actions paused. GIT_ASKPASS pattern, never embed credentials.
6. Owner review backlog: ADR-0007 amendments revocable; ADR-0008 accepted under delegation (supersedable); OQ-9 semver; OQ-10 OCR tooling; ERROR_HANDLING severity/recovery sections Draft; no ADR-0001 verdict until corpus meets protocol scope.

## Acceptance criteria
- [ ] `python3 scripts/linkcheck.py` → ALL INTERNAL LINKS OK (exit 0) — re-verify after any edit.
- [ ] `python3 -m pytest -q` → **162 passed** baseline (addopts neutralizes libtmux; do not remove unless the plugin is gone from images for good).
- [ ] No GitHub Actions runs triggered without owner sign-off (OQ-15 pause stands).
- [ ] GUI obeys ADR-0008: thin client (no CLI shelling — subprocess only inside TESTS), lazy Qt imports (AST-enforced test must stay green), core install stays Qt-free, every new widget path covered offscreen.
- [ ] `lexora-gui --help`/`--version` keep working on bare headless boxes (regression tests exist — don't break them).
- [ ] Any published number carries its corpus-tier label; STATUS/PROGRESS/SESSION_LOG/NEXT_SESSION/README/CHANGELOG agree; commit hashes real.
- [ ] No ADR-0001 verdict until corpus meets BENCHMARK_PROTOCOL scope; no new *published* revision without a manifest change.
