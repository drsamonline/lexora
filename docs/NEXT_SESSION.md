# Next Session Resume Card

**Last verified state:** 2026-10-17, Session 33 complete. **M3 verification closure landed: fixed the red suite left by Session 32 (stale `__all__` assertion after `crash.py` — set-superset form now), added file-picker dialog-factory seams (`win._lexora_open_dialog`/`_lexora_save_dialog`, production default unchanged) + 4 offscreen tests (picked/cancel/tuple/icon-from-committed-SVG). Suite 171 → 182 (S32 crash/path tests) → 186 passed.** Prior: Session 32 (`7342b1a`) GUI-M3 code drop — crash diagnostics (`src/lexora/gui/crash.py`: faulthandler + JSONL excepthook sink wired into `main()`), committed SVG icon as window icon, native Browse… buttons, Qt-free `resolve_path()`. NOTE: S32's completion report was FALSE (claimed 193 green + docs updated; actually red suite, zero doc edits) — corrected and recorded in SESSION_LOG per append-only policy. Sessions 27–31: GUI-M1 shell → M2 job runner → M2b panels → M2c settings/packaging/screenshots. Environment: PySide6 6.12 installs in-container but fresh containers need `pip install pyside6` AND `apt-get install -y libegl1` (offscreen Qt aborts without it; ~673 MB wheel). Phase 1 posture unchanged: In progress pending two evidence items (editable-install note, peak-RSS-vs-budget owner verdict). GitHub Actions PAUSED (OQ-15); local gate = `python3 -m pytest -q` + `python3 scripts/linkcheck.py`. Sessions 20–33 commits remain local-only (`.vault/github_token.txt` absent). Published benchmark revisions unchanged: R1 + R2; no ADR-0001 verdict.
**Current phase:** GUI-M3 remaining scope (owner directive: build whole app; skip Actions until complete). English-only build scope.
**Branch/commit:** working branch (verify with `git log --oneline -3`).
**Working-tree state:** Clean after Session 33 commit.

## Read first
- [ ] docs/SESSION_LOG.md (Session 33 last; read the S32 CORRECTION entry — treat completion claims as unverified until gates run)
- [ ] docs/ADR/ADR-0008-gui-toolkit-architecture.md (binding GUI constraints — obeyed so far; keep it that way)
- [ ] docs/DESIGN_GUI.md §5 milestones (GUI-M3 scope: G8 screen, polish) + §3 (G6/G8 definitions)
- [ ] src/lexora/gui/crash.py (`CrashLog.read_records()` exists — viewer panel just needs to render it)
- [ ] docs/TASK_BREAKDOWN.md GUI milestones table (M1/M2 Landed, M3 Partially landed)

## Tasks in order
1. **Qt env setup check:** `QT_QPA_PLATFORM=offscreen python3 -c "import PySide6"` — if ImportError on libEGL, run `apt-get install -y libegl1` and `pip install pyside6` first.
2. **GUI-M3 remainder:** (a) crash-log viewer — button/tab rendering `CrashLog.read_records()` (newest first, count badge, empty-state text) into the G6 pane or a dedicated view; offscreen-tested incl. tmp-XDG isolation. (b) G8 About/settings screen — version, config paths (settings + crash log), link to docs; keep thin-client rule (render via pure Qt-free formatter like the other views). Then declare M3 closed if both land.
3. **P1 evidence backfill (standing):** draft (do NOT publish) peak-RSS-vs-PERFORMANCE_BUDGET note from `benchmarks/results-r3.json` for owner verdict; then PHASES P1 → Complete candidate ONLY if both evidences land.
4. **Corpus growth toward genuine R3 (English-only):** ≥1 GiB Tier-1 expansion via harness `corpus-fetch` → `corpus-commit` → `manifest` → `verify` → `audit-splits` → `run --revision 3 --reps 3`; owner review before publishing. Track OQ-8.
5. **Push (when token available):** pushes allowed while Actions paused. GIT_ASKPASS pattern, never embed credentials.
6. Owner review backlog: ADR-0007 amendments revocable; ADR-0008 accepted under delegation (supersedeable); OQ-9 semver; OQ-10 OCR tooling; ERROR_HANDLING severity/recovery sections Draft; no ADR-0001 verdict until corpus meets protocol scope.

## Acceptance criteria
- [ ] `python3 scripts/linkcheck.py` → ALL INTERNAL LINKS OK (exit 0) — re-run after ANY edit, including content-only edits.
- [ ] `python3 -m pytest -q` → **186 passed** baseline (addopts neutralizes libtmux; do not remove unless the plugin is gone from images for good).
- [ ] No GitHub Actions runs triggered without owner sign-off (OQ-15 pause stands).
- [ ] GUI obeys ADR-0008: thin client (no CLI shelling — subprocess only inside TESTS), lazy Qt imports (AST-enforced test must stay green), core install stays Qt-free, every new widget path covered offscreen.
- [ ] `lexora-gui --help`/`--version` keep working on bare headless boxes (regression tests exist — don't break them).
- [ ] Any published number carries its corpus-tier label; STATUS/PROGRESS/SESSION_LOG/NEXT_SESSION/README/CHANGELOG agree; commit hashes real.
- [ ] No ADR-0001 verdict until corpus meets BENCHMARK_PROTOCOL scope; no new *published* revision without a manifest change.
- [ ] NEVER report completion without running both gates in the same session as the claim (S32 incident lesson).
