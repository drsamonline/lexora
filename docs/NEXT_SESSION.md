# Next Session Resume Card

**Last verified state:** 2026-10-16, Session 19 complete. **Delivery unblocked and current:** Sessions 14–18 work pushed (`e240af0`) and merged to hosted `main` via PR #4 (merge commit `0fafef4`); CI green on `e240af0`. Owner scope decision recorded: **English-only is the build scope** for rapid app development; Hindi/Gujarati corpus coverage is a deferred future capability, not a requirement. Benchmark state unchanged from Session 18: Revision R2 published (manifest hash `a32240d7…`, provenance chain committed), tier T1-gutenberg-p0 label mandatory, **no ADR-0001 verdict**. 35 tests passing; linkcheck OK.
**Current phase:** Phase 1 — Core Zstd baseline + harness; shift focus to end-to-end app build on English-only scope.
**Branch/commit:** local `main` == `origin/main` == `0fafef4` (+ Session 19 doc commit on top once pushed); verify with `git log --oneline -3` and `git status`.
**Working-tree state:** Clean after Session 19 docs commit.

## Read first
- [ ] docs/BENCHMARK_RESULTS.md (R2 block; R1 block incl. its correction note — append-only history)
- [ ] Latest entries of docs/SESSION_LOG.md (Session 19 — push/merge closure + English-only directive; Session 18 — sidecar-path bug root cause)
- [ ] docs/CORPUS_POLICY.md "Current status" + docs/DECISIONS.md OQ-8 row
- [ ] benchmarks/MANIFEST.json + benchmarks/provenance/gutenberg-r0/ (committed evidence chain)

## Tasks in order
1. **App-build velocity on English-only scope (owner directive 2026-10-16):** drive Phase 1 forward — CLI end-to-end compress/decompress flows and the next implementation pieces that do NOT depend on pending format decisions. If FORMAT_LXZ (docs/DECISIONS.md) is accepted by owner, implement the `.lxz` container immediately; until then policy forbids implementing from PROPOSED specs — ask owner to accept/amend it as task 0 if container work is wanted now.
2. **Corpus growth opportunistically (English-only):** expand Tier-1 English snapshot toward BENCHMARK_PROTOCOL scale (≥1 GiB, more lineages/categories) when convenient; hi/gu sources are DEFERRED (future capability) — do not block on them. Then `corpus-fetch` → `corpus-commit` → `manifest` → `verify` → `audit-splits` → `run --revision 3` so R3 carries genuinely new measurements. Track as OQ-8 progress.
3. Push docs commit + confirm CI green (token in `.vault/github_token.txt`; GIT_ASKPASS pattern; never embed).
4. Owner review of P1 prototype code + remaining OQs (OQ-9 semver, OQ-10 OCR tooling, FORMAT_LXZ acceptance).
5. Only after a protocol-scope corpus (English-only acceptable per owner directive): issue first ADR-0001 Pass/Partial/Fail verdicts (R3+).

## Acceptance criteria
- [ ] `python3 scripts/linkcheck.py` → ALL INTERNAL LINKS OK (exit 0) — re-verify after any edit.
- [ ] `python -m pytest -q` → 35 passed (current truth).
- [ ] Any published number carries its corpus-tier label; STATUS/PROGRESS/SESSION_LOG/NEXT_SESSION/README/CHANGELOG agree; commit hashes real.
- [ ] No ADR-0001 verdict until corpus meets BENCHMARK_PROTOCOL scope.
- [ ] After any corpus change: `verify` + `audit-splits` clean AND `benchmarks/provenance/<snapshot>/` updated via `corpus-commit` before committing a manifest.

## Commands to run
```text
cd /workspace
git status --short
git log --oneline -3
git fetch origin && git status          # compare local vs hosted main
python -m pytest -q                     # expect 35 passed
python3 scripts/linkcheck.py            # expect ALL INTERNAL LINKS OK
python benchmarks/harness.py verify --manifest benchmarks/MANIFEST.json   # needs corpus/ present
python benchmarks/harness.py audit-splits --manifest benchmarks/MANIFEST.json
python benchmarks/harness.py corpus-commit --root corpus/gutenberg-r0     # idempotent; refresh committed sidecars
# pushes: GIT_ASKPASS script echoing contents of .vault/github_token.txt (NEVER embed in URL/commits)
curl -s -H "Authorization: Bearer $(cat .vault/github_token.txt)" \
  https://api.github.com/repos/drsamonline/lexora/actions/runs?per_page=3   # check CI status
```
