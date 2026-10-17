# Next Session Resume Card

**Last verified state:** 2026-10-17, Session 25 complete. **CLI app scope effectively COMPLETE:** five subcommands (`canon` incl. new `--meta` audit JSON, `zround`, `pipe`, `pack`, `unpack`) all implemented + tested; public `verify_archive()` library API landed (GUI G4 dependency closed); ERROR_HANDLING ↔ shipped exit codes (0/2/3/4/5/6/7) formally reconciled (rule 5). Suite **101 passed**; linkcheck OK. Environment fixed permanently: `addopts = "-p no:libtmux"` in pyproject.toml neutralizes the recurring broken container plugin — plain `python3 -m pytest -q` works. **GitHub Actions PAUSED by owner directive** (OQ-15): no CI expectation until the whole app is built or owner says so; local gate = `python3 -m pytest -q` + `python3 scripts/linkcheck.py` before every commit. **GUI planned only:** docs/DESIGN_GUI.md (G1–G8, GUI-M1…M3, OQ-12/13/14 open); zero GUI code; starts only after CLI-complete declaration + GUI ADR. Sessions 20–25 commits remain local-only (`.vault/github_token.txt` absent). Published benchmark revisions unchanged: R1 + R2; **no ADR-0001 verdict**; `benchmarks/results-r3.json` unpublished harness artifact.
**Current phase:** Phase 1 closure decision → then GUI-M1 planning (or corpus growth to genuine R3). English-only build scope (owner directive).
**Branch/commit:** working branch (verify with `git log --oneline -3`).
**Working-tree state:** Clean after Session 25 commit.

## Read first
- [ ] docs/SESSION_LOG.md (Session 25 last)
- [ ] docs/DESIGN_GUI.md (plan of record for the GUI; nothing implemented)
- [ ] docs/CLI_REFERENCE.md (all five real subcommands incl. pack/unpack + exit 7)
- [ ] docs/ADR/ADR-0007-container-v0-freeze.md (Accepted + amendments section is normative)
- [ ] docs/STATUS.md (CI row = Paused/OQ-15; Build indicator now evidence-backed)

## Tasks in order
1. **Decide & record P1 closure:** either (a) declare Phase 1 CLI app complete in STATUS/ROADMAP (owner review backlog noted) and move to GUI planning, or (b) run one more CLI-polish sweep first (e.g. `unpack --meta` parity exists; consider `pack --block-size` bounds messaging). Under standing delegation ("DECIDE UR SELF"), option (a) is pre-approved if gates pass.
2. **GUI-M1 start (after 1):** resolve OQ-12 (toolkit) + OQ-13 (packaging) under standing delegation, draft ADR-0008 (GUI toolkit & architecture) BEFORE any code, per DESIGN_GUI.md milestones. G4 inspector can now use the shipped `verify_archive()` API.
3. **Corpus growth toward a genuine R3 (English-only):** ≥1 GiB Tier-1 expansion via `corpus-fetch` → `corpus-commit` → `manifest` → `verify` → `audit-splits` → `run --revision 3 --reps 3`; owner review before publishing. Track OQ-8.
4. **Push (when token available):** pushes allowed while Actions paused (no minutes burn — verify cheaply first). GIT_ASKPASS pattern, never embed credentials.
5. Owner review backlog: ADR-0007 amendments revocable; OQ-9 semver; OQ-10 OCR tooling; ERROR_HANDLING severity/recovery sections still Draft contract; no ADR-0001 verdict until corpus meets protocol scope.

## Acceptance criteria
- [ ] `python3 scripts/linkcheck.py` → ALL INTERNAL LINKS OK (exit 0) — re-verify after any edit.
- [ ] `python3 -m pytest -q` → **101 passed** (libtmux neutralization now lives in pyproject addopts; do not remove unless the plugin is gone from images for good).
- [ ] No GitHub Actions runs triggered without owner sign-off (OQ-15 pause stands).
- [ ] Any GUI work starts ONLY after CLI-app-complete + a GUI ADR; DESIGN_GUI stays plan-only meanwhile.
- [ ] Any published number carries its corpus-tier label; STATUS/PROGRESS/SESSION_LOG/NEXT_SESSION/README/CHANGELOG agree; commit hashes real.
- [ ] No ADR-0001 verdict until corpus meets BENCHMARK_PROTOCOL scope; no new *published* revision without a manifest change.

## Commands to run
```text
cd /workspace
git status --short
git log --oneline -3
pip install -e .                        # fresh containers lack the package
python3 -m pytest -q                    # expect 96 passed
python3 scripts/linkcheck.py            # expect ALL INTERNAL LINKS OK
python -m lexora.cli pack --in IN --out OUT.lxz   # smoke the new commands
python -m lexora.cli unpack --in OUT.lxz --out BACK
python benchmarks/harness.py verify --manifest benchmarks/MANIFEST.json   # needs corpus/ present
python benchmarks/harness.py audit-splits --manifest benchmarks/MANIFEST.json
# NOTE: do not curl Actions run-status casually this session — API checks are fine, but no new CI expectation (OQ-15)
```
