# Next Session Resume Card

**Last verified state:** 2026-10-16, Session 17 complete. **Benchmark Revision R1 published** in docs/BENCHMARK_RESULTS.md from the Tier-1 fallback corpus (mandatory label T1-gutenberg-p0): Zstd-19 ratio 0.3004 vs XZ-9 0.2975 on 7,124,095 B public-domain English text; smoke scope only — no ADR-0001 verdict. Code/artifacts committed at `908698c` (harness v2 + `benchmarks/corpus.py`) + Session 17 doc commit. 35 tests passing; linkcheck OK.
**Current phase:** Phase 1 — Core Zstd baseline + harness. First measured baselines exist (R1); full-protocol corpus still missing.
**Branch/commit:** working branch tip = Session 17 doc commit on top of `908698c`; verify with `git log --oneline -3`. Hosted `origin/main` was last pushed at `7259ee3` (Session 16) — Sessions ~14–17 commits may be unpushed; check `git fetch origin && git status`.
**Working-tree state:** Clean after Session 17 commit. Raw corpus texts under `corpus/gutenberg-r0/` are gitignored (provenance sidecars ARE committed).

## Read first
- [ ] docs/BENCHMARK_RESULTS.md (Revision R1 block — note the correction re: manifest metadata fields)
- [ ] Latest entry of docs/SESSION_LOG.md (Session 17)
- [ ] docs/CORPUS_POLICY.md "Current status" + docs/DECISIONS.md OQ-8 row
- [ ] benchmarks/MANIFEST.json + benchmarks/results-r0.json (evidence chain)

## Tasks in order
1. **R2 manifest regeneration:** rebuild manifest with rights/language/category folded in from `corpus/gutenberg-r0.meta.json` (fixes the UNCLASSIFIED fields flagged in R1's correction note); re-run `verify` + `audit-splits`; keep tier labeling.
2. **Corpus expansion toward protocol scope:** owner input needed for `data/raw/` (Tier 0); otherwise expand Tier-1 fetch (more lineages, add hi/gu sources per CORPUS_POLICY) toward ≥1 GiB. Track as OQ-8 progress.
3. Push unpushed commits once token available in `.vault/github_token.txt` (GIT_ASKPASS pattern; never embed); confirm CI green after push.
4. Owner review of P1 prototype code + remaining OQs (OQ-9 semver, OQ-10 OCR tooling).
5. Only after a protocol-scope corpus: run R2+ and issue first ADR-0001 Pass/Partial/Fail verdicts.

## Acceptance criteria
- [ ] `python3 scripts/linkcheck.py` → ALL INTERNAL LINKS OK (exit 0) — re-verify after any edit.
- [ ] `python -m pytest -q` → 35 passed (current truth).
- [ ] Any published number carries its corpus-tier label; STATUS/PROGRESS/SESSION_LOG/NEXT_SESSION/README/CHANGELOG agree; commit hashes real.
- [ ] No ADR-0001 verdict until corpus meets BENCHMARK_PROTOCOL scope.

## Commands to run
```text
cd /workspace
git status --short
git log --oneline -3
git fetch origin && git status          # compare local vs hosted main
python -m pytest -q                     # expect 35 passed
python3 scripts/linkcheck.py            # expect ALL INTERNAL LINKS OK
python benchmarks/harness.py verify --manifest benchmarks/MANIFEST.json   # needs corpus/ present
# pushes: GIT_ASKPASS script echoing contents of .vault/github_token.txt (NEVER embed in URL/commits)
curl -s -H "Authorization: Bearer $(cat .vault/github_token.txt)" \
  https://api.github.com/repos/drsamonline/lexora/actions/runs?per_page=3   # check CI status
```
