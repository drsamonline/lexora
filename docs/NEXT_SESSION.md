# Next Session Resume Card

**Last verified state:** 2026-10-16, Session 20 complete. **Container unblock drafted:** ADR-0007 (minimal `.lxz` v0 layout freeze) proposed as OQ-11 — owner accept/amend/reject is task 0 below; nothing implemented from PROPOSED specs meanwhile. **App velocity:** `lexora pipe` end-to-end baseline flow landed with 5 tests → suite now **40 passed**; linkcheck OK. Prior state (Session 19): Sessions 14–18 pushed (`e240af0`) + merged via PR #4 (`0fafef4`); English-only is the build scope (Hindi/Gujarati deferred, not required). Benchmark unchanged: R2 published (manifest hash `a32240d7…`), tier T1-gutenberg-p0 label mandatory, **no ADR-0001 verdict**.
**Current phase:** Phase 1 — Core Zstd baseline + harness; shift focus to end-to-end app build on English-only scope.
**Branch/commit:** Session 20 work committed on the working branch (tip recorded in commit below); hosted `main` was at `7e31656` after Session 19. Verify with `git log --oneline -3` and `git status`.
**Working-tree state:** Clean after Session 20 commit.

## Read first
- [ ] docs/BENCHMARK_RESULTS.md (R2 block; R1 block incl. its correction note — append-only history)
- [ ] Latest entries of docs/SESSION_LOG.md (Session 19 — push/merge closure + English-only directive; Session 18 — sidecar-path bug root cause)
- [ ] docs/CORPUS_POLICY.md "Current status" + docs/DECISIONS.md OQ-8 row
- [ ] benchmarks/MANIFEST.json + benchmarks/provenance/gutenberg-r0/ (committed evidence chain)

## Tasks in order
0. **OWNER DECISION (task 0, unblocks container work):** accept/amend/reject [ADR-0007](ADR/ADR-0007-container-v0-freeze.md) — proposed minimal `.lxz` v0 byte-layout freeze (tracked as OQ-11 in docs/DECISIONS.md). Drafted Session 20 with exact layout + verification plan so acceptance is a one-word reply. Until accepted, policy forbids implementing the container (SPEC §7.2).
1. **App-build velocity on English-only scope (owner directive 2026-10-16):** drive Phase 1 forward — Session 20 landed the `lexora pipe` end-to-end baseline flow (canon → compress → verify; 5 new tests, suite now 40). Next pieces that do NOT depend on pending format decisions: canonicalizer golden vectors (`tests/vectors/canonicalization/`, P1-T2), peak-RSS capture in harness (P1-T6), `docs/CLI_REFERENCE.md` for the three real subcommands. If ADR-0007 is accepted, implement `.lxz` container (`src/lexora/container.py`) + CLI `pack`/`unpack` (P1-T3/P1-T5) immediately.
2. **Corpus growth opportunistically (English-only):** expand Tier-1 English snapshot toward BENCHMARK_PROTOCOL scale (≥1 GiB, more lineages/categories) when convenient; hi/gu sources are DEFERRED (future capability) — do not block on them. Then `corpus-fetch` → `corpus-commit` → `manifest` → `verify` → `audit-splits` → `run --revision 3` so R3 carries genuinely new measurements. Track as OQ-8 progress.
3. Push docs commit + confirm CI green (token in `.vault/github_token.txt`; GIT_ASKPASS pattern; never embed).
4. Owner review of P1 prototype code + remaining OQs (OQ-9 semver, OQ-10 OCR tooling, OQ-11/ADR-0007 container freeze).
5. Only after a protocol-scope corpus (English-only acceptable per owner directive): issue first ADR-0001 Pass/Partial/Fail verdicts (R3+).

## Acceptance criteria
- [ ] `python3 scripts/linkcheck.py` → ALL INTERNAL LINKS OK (exit 0) — re-verify after any edit.
- [ ] `python -m pytest -q` → 40 passed (current truth).
- [ ] Any published number carries its corpus-tier label; STATUS/PROGRESS/SESSION_LOG/NEXT_SESSION/README/CHANGELOG agree; commit hashes real.
- [ ] No ADR-0001 verdict until corpus meets BENCHMARK_PROTOCOL scope.
- [ ] After any corpus change: `verify` + `audit-splits` clean AND `benchmarks/provenance/<snapshot>/` updated via `corpus-commit` before committing a manifest.

## Commands to run
```text
cd /workspace
git status --short
git log --oneline -3
git fetch origin && git status          # compare local vs hosted main
python -m pytest -q                     # expect 40 passed
python3 scripts/linkcheck.py            # expect ALL INTERNAL LINKS OK
python benchmarks/harness.py verify --manifest benchmarks/MANIFEST.json   # needs corpus/ present
python benchmarks/harness.py audit-splits --manifest benchmarks/MANIFEST.json
python benchmarks/harness.py corpus-commit --root corpus/gutenberg-r0     # idempotent; refresh committed sidecars
# pushes: GIT_ASKPASS script echoing contents of .vault/github_token.txt (NEVER embed in URL/commits)
curl -s -H "Authorization: Bearer $(cat .vault/github_token.txt)" \
  https://api.github.com/repos/drsamonline/lexora/actions/runs?per_page=3   # check CI status
```
