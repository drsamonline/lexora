# Next Session Resume Card

**Last verified state:** 2026-10-17, Session 34 complete. **GUI-M3 milestone CLOSED: G8-lite About view (fifth view `about`, pure `format_about_text()` — version/paths/defaults) + crash-log viewer (`crash.py:format_crash_records` newest-first w/ 2000-char traceback cap; "Crash log" button via `win._lexora_crash_log` seam into the G6 pane); suite 186 → 192 passed.** NOTE: this session caught a SECOND false completion report (claimed Sessions 34/35 landed batch queue/drag-drop/shortcuts as commits `276a8f5`/`241f80d` — neither existed; HEAD was still S33 `17a6711`) and deduped a botched-heredoc test stub in `test_gui_app_offscreen.py`. Prior: Session 33 (`17a6711`) M3 verification closure (fixed red suite from S32, picker seams + icon tests, 186). Sessions 27–32: GUI-M1 shell → M2 job runner → M2b panels → M2c settings/packaging/screenshots → M3a pickers/crash/icon. Environment: PySide6 6.12 installs in-container but fresh containers need `pip install pyside6` AND `apt-get install -y libegl1` (offscreen Qt aborts without it; ~673 MB wheel). Phase 1 posture unchanged: In progress pending two evidence items (editable-install note, peak-RSS-vs-budget owner verdict). GitHub Actions PAUSED (OQ-15); local gate = `python3 -m pytest -q` + `python3 scripts/linkcheck.py`. PUSH STATE (Session 36): UNBLOCKED — owner supplied a PAT in-chat; `HEAD:main` pushed directly, hosted `main` fast-forwarded `871a3ff..ac182cd` (full Sessions ~14–35 lineage now public). Token used via temp credential store, deleted after use, never committed. Owner advised to revoke/rotate the token (it appeared in chat transcript). Published benchmark revisions unchanged: R1 + R2; no ADR-0001 verdict.
**Current phase:** CLI app scope complete; GUI milestones M1–M3 complete. Remaining per owner directive ("build whole app"): GUI stretch items optional; load-bearing work is P1 evidence backfill + corpus growth. English-only build scope.
**Branch/commit:** working branch (verify with `git log --oneline -3`).
**Working-tree state:** Clean after Session 34 commit.

## Read first
- [ ] docs/SESSION_LOG.md (Session 34 last; read BOTH incident notes — treat every prior completion claim as unverified until gates run in YOUR session)
- [ ] docs/TASK_BREAKDOWN.md GUI milestones table (M1/M2/M2b/M2c/M3 all Landed)
- [ ] docs/DESIGN_GUI.md §5 (stretch items: G8-full batch queue, OS file associations, tray notes)
- [ ] benchmarks/results-r3.json + docs/PERFORMANCE_BUDGET.md (P1 evidence item #2 raw material)
- [ ] docs/ADR/ADR-0008-gui-toolkit-architecture.md (binding GUI constraints — still applies to any stretch work)

## Tasks in order
1. **Qt env setup check (only if touching GUI):** `QT_QPA_PLATFORM=offscreen python3 -c "import PySide6"` — on ImportError/libEGL error run `apt-get install -y libegl1` and `pip install pyside6`.
2. **P1 evidence backfill (load-bearing):** draft (do NOT publish) peak-RSS-vs-PERFORMANCE_BUDGET comparison from `benchmarks/results-r3.json` for owner verdict; add editable-install verification note. PHASES P1 → Complete candidate ONLY if both evidences land.
3. **Corpus growth toward genuine R3 (English-only):** ≥1 GiB Tier-1 expansion via harness `corpus-fetch` → `corpus-commit` → `manifest` → `verify` → `audit-splits` → `run --revision 3 --reps 3`; owner review before publishing. Track OQ-8.
4. **GUI stretch (only if owner asks):** G8-full batch queue (needs multi-job runner design — current `JobRunner` runs ONE job), drag-and-drop onto G1, keyboard shortcuts. Keep thin-client rule + offscreen coverage for anything built.
5. **Push (when token available):** pushes allowed while Actions paused. GIT_ASKPASS pattern, never embed credentials.
6. Owner review backlog: ADR-0007 amendments revocable; ADR-0008 accepted under delegation (supersedeable); OQ-9 semver; OQ-10 OCR tooling; ERROR_HANDLING severity/recovery sections Draft; no ADR-0001 verdict until corpus meets protocol scope.

## Acceptance criteria
- [ ] `python3 scripts/linkcheck.py` → ALL INTERNAL LINKS OK (exit 0) — re-run after ANY edit, including content-only edits.
- [ ] `python3 -m pytest -q` → **192 passed** baseline (addopts neutralizes libtmux; do not remove unless the plugin is gone from images for good).
- [ ] No GitHub Actions runs triggered without owner sign-off (OQ-15 pause stands).
- [ ] GUI obeys ADR-0008: thin client (no CLI shelling — subprocess only inside TESTS), lazy Qt imports (AST-enforced test must stay green), core install stays Qt-free, every new widget path covered offscreen.
- [ ] `lexora-gui --help`/`--version` keep working on bare headless boxes (regression tests exist — don't break them).
- [ ] Any published number carries its corpus-tier label; STATUS/PROGRESS/SESSION_LOG/NEXT_SESSION/README/CHANGELOG agree; commit hashes real.
- [ ] No ADR-0001 verdict until corpus meets BENCHMARK_PROTOCOL scope; no new *published* revision without a manifest change.
- [ ] NEVER report completion without running both gates in the same session as the claim (S32 + phantom-S34/35 incidents).
