# Next Session Resume Card

**Last verified state:** 2026-10-16, Session 22 complete. **Docs backlog closed:** CHANGELOG + SESSION_LOG entries for Sessions 20–22 written; TASK_BREAKDOWN P1-T2 and P1-T6 rows flipped to landed. **P1-T2 done:** 9 byte-exact golden vectors under `tests/vectors/canonicalization/` (`scripts/gen_canon_vectors.py` → `tests/test_canon_vectors.py`). **P1-T6 done (mechanism + first measurement):** peak-RSS capture works end-to-end on Linux (forked child + `/proc` VmHWM sampling); harness artifact `benchmarks/results-r3.json` records zstd19 = 85,956 KiB, xz9 = 35,348 KiB (tier T1-gutenberg-p0). It is committed as harness output only — **not published** as a revision (protocol §7 requires a manifest change; corpus bytes identical to R2; publication needs owner review). Suite: **60 passed**; linkcheck OK. Branch tip before this session's docs commit: `38bc99d`; hosted `main` still at `7e31656` — Sessions 20–22 commits are local-only (`.vault/github_token.txt` absent in this container). Benchmark published revisions unchanged: R1 + R2; **no ADR-0001 verdict**.
**Current phase:** Phase 1 — Core Zstd baseline + harness; English-only app-build scope (owner directive).
**Branch/commit:** working branch, tip = Session 22 docs commit (verify with `git log --oneline -3`).
**Working-tree state:** Clean after Session 22 commit.

## Read first
- [ ] docs/SESSION_LOG.md (Sessions 20–22 — ADR-0007 draft, pipe CLI, vectors, RSS mechanism + bug fix)
- [ ] docs/TASK_BREAKDOWN.md P1 table (T2/T6 now landed; T3/T5 blocked on OQ-11)
- [ ] docs/BENCHMARK_RESULTS.md (published = R1+R2 only; results-r3.json is an unpublished artifact)
- [ ] benchmarks/MANIFEST.json + benchmarks/provenance/gutenberg-r0/ (committed evidence chain)

## Tasks in order
0. **OWNER DECISION (task 0, unblocks container work):** accept/amend/reject [ADR-0007](ADR/ADR-0007-container-v0-freeze.md) — proposed minimal `.lxz` v0 byte-layout freeze (OQ-11 in docs/DECISIONS.md). Until accepted, policy forbids implementing the container (SPEC §7.2). Related owner asks: whether to publish the RSS numbers (needs a genuine manifest change first), and comparison of peaks vs PERFORMANCE_BUDGET limits.
1. **App-build velocity, decision-independent pieces:** `docs/CLI_REFERENCE.md` covering the four real subcommands (`canon`, `zround`, `pipe`, plus exit codes — all already tested in `tests/test_cli.py`); property/invariant tests that untouched byte classes pass through canonicalization (P1-T2 acceptance second half); block-boundary edge tests (0 B, ±1) when container work starts. If ADR-0007 accepted: implement `.lxz` container (`src/lexora/container.py`) + CLI `pack`/`unpack` (P1-T3/P1-T5) immediately.
2. **Corpus growth toward a genuine R3 (English-only):** expand Tier-1 snapshot toward BENCHMARK_PROTOCOL scale (≥1 GiB, more lineages/categories): `corpus-fetch` → `corpus-commit` → `manifest` (new hash ⇒ legitimate revision renumber) → `verify` → `audit-splits` → `run --revision 3 --reps 3`; then owner review before publishing into BENCHMARK_RESULTS.md. Track as OQ-8 progress.
3. **Push:** `.vault/github_token.txt` does not exist in this container — ask owner for a token or push from their side; GIT_ASKPASS pattern, never embed credentials; confirm CI green afterwards.
4. Owner review of P1 prototype code + remaining OQs (OQ-9 semver, OQ-10 OCR tooling, OQ-11/ADR-0007 container freeze).
5. Only after a protocol-scope corpus (English-only acceptable per owner directive): issue first ADR-0001 Pass/Partial/Fail verdicts.

## Acceptance criteria
- [ ] `python3 scripts/linkcheck.py` → ALL INTERNAL LINKS OK (exit 0) — re-verify after any edit.
- [ ] `python -m pytest -q` → 60 passed (current truth).
- [ ] Any published number carries its corpus-tier label; STATUS/PROGRESS/SESSION_LOG/NEXT_SESSION/README/CHANGELOG agree; commit hashes real.
- [ ] No ADR-0001 verdict until corpus meets BENCHMARK_PROTOCOL scope; no new *published* revision without a manifest change.
- [ ] After any corpus change: `verify` + `audit-splits` clean AND `benchmarks/provenance/<snapshot>/` updated via `corpus-commit` before committing a manifest.

## Commands to run
```text
cd /workspace
git status --short
git log --oneline -3
git fetch origin && git status          # compare local vs hosted main
python -m pytest -q                     # expect 60 passed
python3 scripts/linkcheck.py            # expect ALL INTERNAL LINKS OK
python benchmarks/harness.py verify --manifest benchmarks/MANIFEST.json   # needs corpus/ present
python benchmarks/harness.py audit-splits --manifest benchmarks/MANIFEST.json
python benchmarks/harness.py run --manifest benchmarks/MANIFEST.json --out benchmarks/results-r3.json --reps 3 --revision 3   # regenerates RSS artifact
python benchmarks/harness.py corpus-commit --root corpus/gutenberg-r0     # idempotent; refresh committed sidecars
# pushes: GIT_ASKPASS script echoing contents of .vault/github_token.txt (NEVER embed in URL/commits)
curl -s -H "Authorization: Bearer $(cat .vault/github_token.txt)" \
  https://api.github.com/repos/drsamonline/lexora/actions/runs?per_page=3   # check CI status
```
