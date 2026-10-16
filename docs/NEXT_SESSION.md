# Next Session Resume Card

**Last verified state:** 2026-10-16, Session 23 complete. **Decision-independent NEXT_SESSION task-1 items both landed:** (a) `docs/CLI_REFERENCE.md` — real-scope reference for `canon`/`zround`/`pipe` incl. tested exit-code table; linked from `docs/index.md`; `docs/ERROR_HANDLING.md` annotated that its proposed taxonomy must reconcile with it. (b) P1-T2 invariant half — `tests/test_canonicalize_invariants.py` (idempotence, untouched-byte passthrough, seeded ASCII/Indic fuzz, output shape). Suite: **68 passed**; linkcheck OK. **Environment caveat:** this container again has the broken `libtmux` pytest plugin (image drift) — run `python -m pytest -q -p no:libtmux`; plain invocation crashes on collection. Sessions 20–23 commits remain local-only (`.vault/github_token.txt` still absent). Benchmark published revisions unchanged: R1 + R2; **no ADR-0001 verdict**; `benchmarks/results-r3.json` is an unpublished harness artifact.
**Current phase:** Phase 1 — Core Zstd baseline + harness; English-only app-build scope (owner directive).
**Branch/commit:** working branch (verify with `git log --oneline -3`).
**Working-tree state:** Clean after Session 23 commit.

## Read first
- [ ] docs/SESSION_LOG.md (Session 23 last; Sessions 20–22 before it)
- [ ] docs/CLI_REFERENCE.md (new — normative for shipped commands)
- [ ] docs/TASK_BREAKDOWN.md P1 table (T2 fully landed incl. invariants; T5 precursor done, pack/unpack still blocked)
- [ ] docs/BENCHMARK_RESULTS.md (published = R1+R2 only; results-r3.json is an unpublished artifact)

## Tasks in order
0. **OWNER DECISION (task 0, unblocks container work):** accept/amend/reject [ADR-0007](ADR/ADR-0007-container-v0-freeze.md) — proposed minimal `.lxz` v0 byte-layout freeze (OQ-11 in docs/DECISIONS.md). Until accepted, policy forbids implementing the container (SPEC §7.2). Related owner asks: whether to publish the RSS numbers (needs a genuine manifest change first), comparison of peaks vs PERFORMANCE_BUDGET limits, and reconciliation of ERROR_HANDLING's proposed exit-code taxonomy with the shipped one.
1. **If ADR-0007 accepted:** implement `.lxz` container (`src/lexora/container.py`) + CLI `pack`/`unpack` (P1-T3/P1-T5) + block-boundary edge tests (0 B, ±1) + golden archive vectors under `tests/vectors/lxz_format/`; extend CLI_REFERENCE accordingly. If not yet accepted: remaining independent candidates are thin — e.g. `canon --meta` JSON audit output (canonicalize_with_meta is already implemented and tested at library level), or corpus growth.
2. **Corpus growth toward a genuine R3 (English-only):** expand Tier-1 snapshot toward BENCHMARK_PROTOCOL scale (≥1 GiB, more lineages/categories): `corpus-fetch` → `corpus-commit` → `manifest` (new hash ⇒ legitimate revision renumber) → `verify` → `audit-splits` → `run --revision 3 --reps 3`; then owner review before publishing into BENCHMARK_RESULTS.md. Track as OQ-8 progress.
3. **Push:** `.vault/github_token.txt` does not exist in this container — ask owner for a token or push from their side; GIT_ASKPASS pattern, never embed credentials; confirm CI green afterwards.
4. Owner review of P1 prototype code + remaining OQs (OQ-9 semver, OQ-10 OCR tooling, OQ-11/ADR-0007 container freeze).
5. Only after a protocol-scope corpus (English-only acceptable per owner directive): issue first ADR-0001 Pass/Partial/Fail verdicts.

## Acceptance criteria
- [ ] `python3 scripts/linkcheck.py` → ALL INTERNAL LINKS OK (exit 0) — re-verify after any edit.
- [ ] `python -m pytest -q -p no:libtmux` → 68 passed (current truth; drop `-p no:libtmux` only if the stale plugin is gone).
- [ ] Any published number carries its corpus-tier label; STATUS/PROGRESS/SESSION_LOG/NEXT_SESSION/README/CHANGELOG agree; commit hashes real.
- [ ] No ADR-0001 verdict until corpus meets BENCHMARK_PROTOCOL scope; no new *published* revision without a manifest change.
- [ ] After any corpus change: `verify` + `audit-splits` clean AND `benchmarks/provenance/<snapshot>/` updated via `corpus-commit` before committing a manifest.

## Commands to run
```text
cd /workspace
git status --short
git log --oneline -3
python -m pytest -q -p no:libtmux     # expect 68 passed
python3 scripts/linkcheck.py          # expect ALL INTERNAL LINKS OK
python benchmarks/harness.py verify --manifest benchmarks/MANIFEST.json   # needs corpus/ present
python benchmarks/harness.py audit-splits --manifest benchmarks/MANIFEST.json
python benchmarks/harness.py run --manifest benchmarks/MANIFEST.json --out benchmarks/results-r3.json --reps 3 --revision 3   # regenerates RSS artifact
python benchmarks/harness.py corpus-commit --root corpus/gutenberg-r0     # idempotent; refresh committed sidecars
# pushes: GIT_ASKPASS script echoing contents of .vault/github_token.txt (NEVER embed in URL/commits)
curl -s -H "Authorization: Bearer $(cat .vault/github_token.txt)" \
  https://api.github.com/repos/drsamonline/lexora/actions/runs?per_page=3   # check CI status
```
