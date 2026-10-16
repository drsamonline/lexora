# Next Session Resume Card

**Last verified state:** 2026-10-16, Session 18 complete. **Benchmark Revision R2 published** (docs/BENCHMARK_RESULTS.md): manifest regenerated with rights=P0/language=en/category=prose/books folded in — new hash `a32240d792c06953465ef71dd9dc30a2033aea976ab23291c326b32014161a5f` (supersedes R1's `7d65d09d…`); R1 correction note closed; provenance evidence chain committed under `benchmarks/provenance/gutenberg-r0/` (raw texts still gitignored). Measured numbers unchanged by design (same corpus bytes) — tier T1-gutenberg-p0 label mandatory, **no ADR-0001 verdict**. 35 tests passing; linkcheck OK.
**Current phase:** Phase 1 — Core Zstd baseline + harness. Evidence chain now fully committed; full-protocol corpus still missing.
**Branch/commit:** working branch tip = Session 18 commit (on top of `2bf6355`, `908698c`); verify with `git log --oneline -3`. Hosted `origin/main` last pushed at `7259ee3` (Session 16) — Sessions ~14–18 commits unpushed; check `git fetch origin && git status`.
**Working-tree state:** Clean after Session 18 commit.

## Read first
- [ ] docs/BENCHMARK_RESULTS.md (R2 block; R1 block incl. its correction note — append-only history)
- [ ] Latest entry of docs/SESSION_LOG.md (Session 18 — includes the sidecar-path bug root cause)
- [ ] docs/CORPUS_POLICY.md "Current status" + docs/DECISIONS.md OQ-8 row
- [ ] benchmarks/MANIFEST.json + benchmarks/provenance/gutenberg-r0/ (committed evidence chain)

## Tasks in order
1. **Corpus expansion toward protocol scope (R3):** more lineages + Hindi/Gujarati sources per CORPUS_POLICY (PG has hi/gu titles; add ids to `corpus.py` curated lists or fetch via language-specific indexes), toward ≥1 GiB; owner input for `data/raw/` (Tier 0) always preferred. Then `corpus-fetch` → `corpus-commit` → `manifest` → `verify` → `audit-splits` → `run --revision 3` so R3 carries genuinely new measurements. Track as OQ-8 progress.
2. Push unpushed commits once token available in `.vault/github_token.txt` (GIT_ASKPASS pattern; never embed); confirm CI green after push (CI runs pytest+linkcheck only — harness needs no corpus in CI).
3. Owner review of P1 prototype code + remaining OQs (OQ-9 semver, OQ-10 OCR tooling).
4. Only after a protocol-scope corpus: issue first ADR-0001 Pass/Partial/Fail verdicts (R3+).

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
