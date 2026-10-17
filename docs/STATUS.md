# LEXORA Project Status

> **Status:** Active — update at every session end
> **Last verified:** 2026-10-17 (Session 24: ADR-0007 accepted under owner delegation "DECIDE UR SELF" — `.lxz` v0 container implemented (`src/lexora/container.py`) with CLI `pack`/`unpack`, exit code 7, golden-archive vectors; 96 tests passing. GitHub Actions PAUSED by owner (free-tier minutes exhausted; OQ-15) — local verification gate until the whole app is built. GUI design plan drafted: docs/DESIGN_GUI.md (OQ-12…14 open). Prior: Session 23: CLI_REFERENCE.md written + P1-T2 invariant tests landed — 68 tests passing; Session 22: P1-T2 golden vectors + P1-T6 peak-RSS capture landed and verified; first real RSS numbers in harness artifact `benchmarks/results-r3.json` (not yet published as a revision). Prior: Session 20 `lexora pipe` flow + ADR-0007 drafted (OQ-11, awaiting owner accept/amend/reject); Session 19 English-only scope directive; Sessions 14–18 merged via PR #4, hosted `main` at `7e31656`)

## Current phase

**Phase 1 (P1) — Core Zstd baseline + harness, STARTED.** Phase 0 documentation batches A–E are complete and hosted (`a1bf3c3`). Session 12 closed OQ-7 via ADR-0005 (Python ≥3.12,<4.0 per owner delegation) and landed the first real code: package skeleton (`pyproject.toml`, `src/lexora/`), canonicalizer rules CAN-R01/R02/R05, frame-level Zstd codec with round-trip verification, and a minimal tested CLI (`canon`/`zround`) — commit `8ee3bef`. Session 13 added the benchmark harness scaffold (`env` / `manifest` / `verify` / `audit-splits` / `run`; protocol §1–§4, §6 mechanics) and fixed the truncation-refusal behavior in `decompress()` (REQ-CMP-006 spirit). The `.lxz` container remains unimplemented (FORMAT_LXZ is PROPOSED — policy forbids implementing from it).

## Verified repository state

| Item | State |
|---|---|
| Implementation code | **Present (prototype):** `src/lexora/{__init__,canonicalize,zstd_core,container,cli}.py`, `benchmarks/harness.py` — Phase-1 baseline + `.lxz` v0 container (accepted ADR-0007), no stable API |
| Tests / test tooling | **96 tests passing** (`python3 -m pytest -q`; environment note: if a stale third-party `libtmux` plugin reappears in a container, add `-p no:libtmux` — it crashed collection in some images. Sessions 20–24: `pipe` tests, golden-vector conformance, whitelist-invariant property tests, `.lxz` container suite (`tests/test_container_lxz.py`). Golden vectors: 9 canonicalization scenarios + lxz format vectors under `tests/vectors/lxz_format/` |
| Build/packaging config (`pyproject.toml` etc.) | **Present** — version `0.0.1.dev1`, requires-python `>=3.12,<4.0` (ADR-0005), deps pinned to tested versions (zstandard 0.25.0) |
| CI/CD workflows | **Paused by owner decision 2026-10-17 (OQ-15):** `.github/workflows/ci.yml` exists and last ran green on `e240af0` (Session 19); free-tier Actions minutes exhausted → no new runs until the whole app is complete or owner re-enables. Local gate meanwhile: `pytest -q` + linkcheck before every commit |
| License file | **Absent** — license not selected (OQ-5) |
| Git remote | **Configured:** origin → https://github.com/drsamonline/lexora.git (no embedded creds). Local `main` ahead of hosted `a1bf3c3` by Session 12–13 commits; push needs owner token |
| Benchmark corpus / results | **R0 smoke snapshot** (Tier T1-gutenberg-p0, 7.1 MB English P0 texts; owner `data/raw/` still empty). Revisions R1+R2 published in BENCHMARK_RESULTS.md (2026-10-16) — baseline Zstd-19 vs XZ-9 numbers only, **no ADR-0001 verdict**; R2 regenerated the manifest with rights/language/category folded in (hash `a32240d7…`) and committed the provenance chain (`benchmarks/provenance/`); ≥1 GiB corpus (OQ-8) still outstanding. **Owner directive 2026-10-16:** English-only is the build scope; Hindi/Gujarati coverage deferred to a future phase (not blocking)
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

- Tests: **96 passed** — `python3 -m pytest -q` (2026-10-17, Session 24 re-verification after `.lxz` container + pack/unpack landed; progression: 35 → 40 (S20 `pipe`) → 60 (S21–22 vectors) → 68 (S23 invariants) → 96 (S24 container suite).
- Build: `pip install -e .` **verified working** in this container 2026-10-17 (was previously untested).
- Coverage/badges/releases: none; none claimed anywhere in docs.

## Next milestone

Finish the CLI app (remaining P1 items + owner review of ADR-0007 amendments), push when a token is available (Actions runs paused meanwhile per OQ-15 — pushes themselves still fine), then GUI-M1 per docs/DESIGN_GUI.md once the app is complete. ADR-0007 accepted under delegation and `.lxz` container + `pack`/`unpack` landed (P1-T3/T5 core); golden vectors (P1-T2) and peak-RSS capture (P1-T6) landed earlier. First *published* benchmark revision beyond R2 requires corpus growth toward ≥1 GiB (OQ-8). CI workflow running linkcheck + tests is already live since Session 15.
