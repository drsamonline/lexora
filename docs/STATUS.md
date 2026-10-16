# LEXORA Project Status

> **Status:** Active — update at every session end
> **Last verified:** 2026-10-16 (Session 17: first benchmark Revision R1 published from Tier-1 fallback corpus; harness v2 + `benchmarks/corpus.py` committed at `908698c`)

## Current phase

**Phase 1 (P1) — Core Zstd baseline + harness, STARTED.** Phase 0 documentation batches A–E are complete and hosted (`a1bf3c3`). Session 12 closed OQ-7 via ADR-0005 (Python ≥3.12,<4.0 per owner delegation) and landed the first real code: package skeleton (`pyproject.toml`, `src/lexora/`), canonicalizer rules CAN-R01/R02/R05, frame-level Zstd codec with round-trip verification, and a minimal tested CLI (`canon`/`zround`) — commit `8ee3bef`. Session 13 added the benchmark harness scaffold (`env` / `manifest` / `verify` / `audit-splits` / `run`; protocol §1–§4, §6 mechanics) and fixed the truncation-refusal behavior in `decompress()` (REQ-CMP-006 spirit). The `.lxz` container remains unimplemented (FORMAT_LXZ is PROPOSED — policy forbids implementing from it).

## Verified repository state

| Item | State |
|---|---|
| Implementation code | **Present (prototype):** `src/lexora/{__init__,canonicalize,zstd_core,cli}.py`, `benchmarks/harness.py` — Phase-1 baseline only, no stable API |
| Tests / test tooling | **35 tests passing** (`pytest 9.1.1`; must run with `-p no:libtmux` — system libtmux plugin crashes collection under pytest 9). Golden vector dir `tests/vectors/canonicalization/` still empty |
| Build/packaging config (`pyproject.toml` etc.) | **Present** — version `0.0.1.dev1`, requires-python `>=3.12,<4.0` (ADR-0005), deps pinned to tested versions (zstandard 0.25.0) |
| CI/CD workflows | **None** — intentionally not created until there are runnable checks; now that tests exist, a CI workflow is a reasonable next step pending owner approval |
| License file | **Absent** — license not selected (OQ-5) |
| Git remote | **Configured:** origin → https://github.com/drsamonline/lexora.git (no embedded creds). Local `main` ahead of hosted `a1bf3c3` by Session 12–13 commits; push needs owner token |
| Benchmark corpus / results | **R0 smoke snapshot** (Tier T1-gutenberg-p0, 7.1 MB English P0 texts; owner `data/raw/` still empty). Revision R1 published in BENCHMARK_RESULTS.md (2026-10-16) — baseline Zstd-19 vs XZ-9 numbers only, **no ADR-0001 verdict**; ≥1 GiB multilingual corpus (OQ-8) still outstanding |
| Approved design source of truth | `LEXORA_Full_Blueprint_Design_Master_Prompt.md` (root) |

## Documentation batches

| Batch | Contents | Status |
|---|---|---|
| A — Governance & navigation | README, docs index, charter, requirements, glossary, decisions/ADR system, status/progress/session/resume, changelog, templates, editor hygiene files | **Complete** (commit `07c1564`) |
| B — Architecture & specification | MASTER_BLUEPRINT, SPECIFICATION (LEXORA-SPEC-1.0-draft), canonicalization, tokenizer, OCR, compression architecture, cost model, FORMAT_LXZ/LXDB proposals, diagrams, ADRs 0001–0004 | **Complete** (`91cfbb6`, `5001ab3`; ADRs Accepted in `86e6b55`) — formats still marked PROPOSED/not frozen per policy |
| C — Engineering execution | Roadmap, phases, implementation plan/matrix, traceability, testing strategy, benchmark protocol/corpus policy, build/install/dev setup | **Complete** (commit `3d98eab`) |
| D — Security & operations | Security architecture, threat model, privacy, error handling, logging, encryption profile (Proposed), troubleshooting, runbooks, root SECURITY.md | **Drafted; closure committed `3ecdfaf`; merged into local `main`; on remote via PR #2 merge (`76476cf`) + Session 11 push** — pending owner review |
| E — GitHub & release polish | CONTRIBUTING, issue/PR templates, release process | **Drafted** (Session 10): `CONTRIBUTING.md`, `.github/ISSUE_TEMPLATE/` ×2, `.github/pull_request_template.md`, `docs/RELEASE_PROCESS.md`. On remote since Session 11 push (`a1bf3c3`). CI workflows and badges intentionally **not created** — nothing runnable exists yet (master prompt §2.10 prohibits placeholders) |

## Blockers

1. ~~Batch D/E not yet on remote~~ — resolved in Session 11 (hosted `main` = `a1bf3c3`). **New:** Sessions 12–13 commits (`8ee3bef` + harness/docs) are local-only; push needs an owner-supplied token (container has no persistent credentials).
2. ~~OQ-7 (Python version)~~ — closed via ADR-0005 (≥3.12,<4.0, owner delegation, Session 12). **OQ-5 (license)** still open and blocks any release/publishing.
3. **OQ-8 (corpus availability/rights)** blocks the first real benchmark run — harness scaffold is ready but refuses empty manifests by design.
4. ~~Owner decisions OQ-1…OQ-4~~ — resolved: ADR-0001…0004 Accepted via owner delegation (`86e6b55`).

## Known risks right now

- ~~Blueprint internal conflicts OQ-1…OQ-4~~ resolved by Accepted ADRs; remaining risk is spec text drift if later edits bypass the ADR process.
- No CI exists yet, so documentation validation is local-only (manual link checks).
- The GitHub token shared in chat must be treated as exposed — owner should revoke/rotate it (repo hygiene; no copy persists in this container or the repo).

## Health indicators *(verified, not asserted)*

- Build: `pip install -e .` evidence not yet captured (package config exists; editable install untested).
- Tests: **35 passed** — `python -m pytest tests/ -q -p no:libtmux` (2026-10-15). Plain `pytest` currently crashes at plugin load due to the system-installed libtmux pytest plugin being incompatible with pytest 9.1.1 (marks-on-fixtures); this is an environment issue, not repo code.
- Coverage/badges/releases: none; none claimed anywhere in docs.

## Next milestone

Push Sessions 12–13 work to remote (needs owner token), then: golden canonicalization vectors (P1-T2 completion), peak-RSS capture in the harness (P1-T6), and the first real benchmark revision once OQ-8 supplies a corpus. Optional approved step now permissible: CI workflow running linkcheck + tests (real runnable checks exist since Session 12).
