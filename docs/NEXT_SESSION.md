# Next Session Resume Card

**Last verified state:** 2026-10-17, Session 26 complete. **CLI app scope: all five subcommands (`canon` incl. `--meta`, `zround`, `pipe`, `pack` incl. `--block-size` bounds→exit 2, `unpack` incl. `--meta`) implemented + CLI-level tested; suite 108 passed; linkcheck OK.** Phase 1 posture: **In progress (closure pending two evidence items)** — NOT flatly Complete: (a) editable-install evidence note (STATUS claims verified once), (b) peak-RSS-vs-PERFORMANCE_BUDGET owner verdict. Stale docs corrected this session: FORMAT_LXZ banner (now "v0 EXPERIMENTAL — frozen by ADR-0007"), ADR/README index (full 0001–0008 table), TASK_BREAKDOWN P1-T3 → Landed, PHASES P1 / ROADMAP M1 → In progress. **GUI decisions landed on paper only:** ADR-0008 Accepted (delegated) — PySide6 via optional `[gui]` extra (`pyside6>=6.6,<7`), same repo, thin-client architecture constraints binding, OQ-12/OQ-13 resolved, OQ-14 provisionally format-minimal through GUI-M3. **Zero GUI code** (verified). GitHub Actions PAUSED (OQ-15); local gate = `python3 -m pytest -q` + `python3 scripts/linkcheck.py`. Sessions 20–26 commits remain local-only (`.vault/github_token.txt` absent). Published benchmark revisions unchanged: R1 + R2; no ADR-0001 verdict.
**Current phase:** P1 evidence backfill → GUI-M1 scaffold decision (Qt availability first). English-only build scope (owner directive).
**Branch/commit:** working branch (verify with `git log --oneline -3`).
**Working-tree state:** Clean after Session 26 commit.

## Read first
- [ ] docs/SESSION_LOG.md (Session 26 last)
- [ ] docs/ADR/ADR-0008-gui-toolkit-architecture.md (binding GUI constraints BEFORE any GUI code)
- [ ] docs/DESIGN_GUI.md (Plan v0.2; G1–G4 = MVP; milestones GUI-M1…M3)
- [ ] docs/ROADMAP.md M1 row (the two remaining closure-evidence items)
- [ ] docs/CLI_REFERENCE.md (five real subcommands; `--block-size` range contract)

## Tasks in order
1. **Probe Qt availability:** `pip install pyside6` (or `pip download --no-deps pyside6` dry check) in-container. If wheels install AND offscreen import works (`QT_QPA_PLATFORM=offscreen python -c "import PySide6"`), start task 2; otherwise do task 3 instead and record the blocker.
2. **GUI-M1 scaffold (only if task 1 succeeds):** create `src/lexora/gui/` package skeleton + app-service adapter (job runner over `canonicalize`/`container.pack/unpack/verify_archive`), `[gui]` extra in pyproject, FIRST tests headless/offscreen only, golden-parity test design per ADR-0008 decision 4. No console entry point until a runnable window exists. Keep suite green throughout.
3. **P1 evidence backfill (either way):** re-run `pip install -e .` capture for the M1 exit-evidence row; draft (do NOT publish) the peak-RSS-vs-budget comparison note from existing `benchmarks/results-r3.json` numbers for owner verdict; then flip PHASES P1 → Complete candidate ONLY if both evidences land.
4. **Corpus growth toward genuine R3 (English-only):** ≥1 GiB Tier-1 expansion via `corpus-fetch` → `corpus-commit` → `manifest` → `verify` → `audit-splits` → `run --revision 3 --reps 3`; owner review before publishing. Track OQ-8.
5. **Push (when token available):** pushes allowed while Actions paused. GIT_ASKPASS pattern, never embed credentials.
6. Owner review backlog: ADR-0007 amendments revocable; **ADR-0008 accepted under delegation — owner may supersede toolkit choice**; OQ-9 semver; OQ-10 OCR tooling; ERROR_HANDLING severity/recovery sections still Draft contract; no ADR-0001 verdict until corpus meets protocol scope.

## Acceptance criteria
- [ ] `python3 scripts/linkcheck.py` → ALL INTERNAL LINKS OK (exit 0) — re-verify after any edit.
- [ ] `python3 -m pytest -q` → **108 passed** baseline (addopts neutralizes libtmux; do not remove unless the plugin is gone from images for good).
- [ ] No GitHub Actions runs triggered without owner sign-off (OQ-15 pause stands).
- [ ] Any GUI code obeys ADR-0008 (thin client, no CLI shelling, offscreen tests, `[gui]` extra keeps core Qt-free) — and only lands after the Qt-availability probe passes.
- [ ] Any published number carries its corpus-tier label; STATUS/PROGRESS/SESSION_LOG/NEXT_SESSION/README/CHANGELOG agree; commit hashes real.
- [ ] No ADR-0001 verdict until corpus meets BENCHMARK_PROTOCOL scope; no new *published* revision without a manifest change.

## Commands to run
```text
cd /workspace
git status --short
git log --oneline -3
pip install -e .                        # fresh containers lack the package
python3 -m pytest -q                    # expect 108 passed
python3 scripts/linkcheck.py            # expect ALL INTERNAL LINKS OK
pip install pyside6 && QT_QPA_PLATFORM=offscreen python -c "import PySide6.QtWidgets; print('qt-ok')"   # task 1 probe
python -m lexora.cli pack --in IN --out OUT.lxz --block-size 0; echo $?    # expect 2 (bounds messaging)
python -m lexora.cli unpack --in OUT.lxz --meta    # index JSON smoke
python benchmarks/harness.py verify --manifest benchmarks/MANIFEST.json   # needs corpus/ present
# NOTE: no CI expectation this session (OQ-15); pushes fine, Actions runs are not.
```
