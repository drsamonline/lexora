# Next Session Resume Card

**Last verified state:** 2026-10-17, Session 24 complete. **OQ-11 closed by owner delegation ("DECIDE UR SELF"): ADR-0007 accepted with three recorded amendments; `.lxz` v0 container implemented** (`src/lexora/container.py`, CLI `pack`/`unpack`, exit code 7, golden vectors under `tests/vectors/lxz_format/`) — suite **96 passed**, linkcheck OK. **GitHub Actions PAUSED by owner directive** (free-tier minutes exhausted; OQ-15): do NOT push expecting CI runs and do not delete the workflow; local gate is `python3 -m pytest -q` + `python3 scripts/linkcheck.py` before every commit; resume Actions only when the whole app is built or owner says so. **GUI planned only:** `docs/DESIGN_GUI.md` (parts G1–G8, milestones GUI-M1…M3, OQ-12/13/14 open) — zero GUI code, implementation deferred until the CLI app is complete (owner directive). Environment: fresh container images may lack pytest/package — run `pip install -e .` first (verified working 2026-10-17); if a stale `libtmux` plugin reappears add `-p no:libtmux`. Sessions 20–24 commits remain local-only (`.vault/github_token.txt` absent). Published benchmark revisions unchanged: R1 + R2; **no ADR-0001 verdict**; `benchmarks/results-r3.json` is an unpublished harness artifact.
**Current phase:** Phase 1 — finish the CLI app scope; English-only build scope (owner directive); GUI after "whole app".
**Branch/commit:** working branch (verify with `git log --oneline -3`).
**Working-tree state:** Clean after Session 24 commit.

## Read first
- [ ] docs/SESSION_LOG.md (Session 24 last)
- [ ] docs/DESIGN_GUI.md (plan of record for the GUI; nothing implemented)
- [ ] docs/CLI_REFERENCE.md (all five real subcommands incl. pack/unpack + exit 7)
- [ ] docs/ADR/ADR-0007-container-v0-freeze.md (Accepted + amendments section is normative)
- [ ] docs/STATUS.md (CI row = Paused/OQ-15; Build indicator now evidence-backed)

## Tasks in order
1. **Finish the CLI app (P1 closure):** remaining polish items — ERROR_HANDLING taxonomy reconciliation vs shipped exit codes 0/2/3/4/5/6/7; block-boundary edge tests beyond current set if any gaps; `canon --meta` JSON audit output (library already has `canonicalize_with_meta`); decide whether to expose public `verify_archive()` (needed later by GUI G4 — keep it library+tests first). Keep CLI_REFERENCE + TASK_BREAKDOWN rows honest as each lands.
2. **Corpus growth toward a genuine R3 (English-only):** ≥1 GiB Tier-1 expansion via `corpus-fetch` → `corpus-commit` → `manifest` → `verify` → `audit-splits` → `run --revision 3 --reps 3`; owner review before publishing. Track OQ-8.
3. **Push (when token available):** pushes are still allowed while Actions is paused (they just won't burn minutes if runs are disabled/minutes exhausted — verify cheaply via one small push or repo settings before bulk pushes). GIT_ASKPASS pattern, never embed credentials.
4. **After the whole CLI app is complete:** start GUI-M1 per DESIGN_GUI.md — first resolve OQ-12/13 (toolkit + packaging) with owner or under standing delegation, then draft a GUI ADR before any code.
5. Owner review backlog: ADR-0007 amendments revocable; OQ-9 semver; OQ-10 OCR tooling; no ADR-0001 verdict until corpus meets protocol scope.

## Acceptance criteria
- [ ] `python3 scripts/linkcheck.py` → ALL INTERNAL LINKS OK (exit 0) — re-verify after any edit.
- [ ] `python3 -m pytest -q` → **96 passed** (add `-p no:libtmux` only if that stale plugin reappears).
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
