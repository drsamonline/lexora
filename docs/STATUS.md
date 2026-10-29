# LEXORA Project Status

> **Status:** Active — update at every session end
> **Last verified:** 2026-10-29 (Session 40: **licence reconciled to PolyForm Noncommercial 1.0.0** per ADR-0009, superseding ADR-0006's MIT — `pyproject.toml` SPDX id, README, docs site, STATUS/PROGRESS/DECISIONS/RELEASE_PROCESS and ADR index swept; `pip install -e .` reports `License-Expression: PolyForm-Noncommercial-1.0.0`; no code touched. Prior: Session 39 (2026-10-28: **streaming encoder landed + first Core-path RSS evidence** — `container.pack_stream()` is the CLI default (byte-identical output, encode peak RSS flat at ≈126 MiB); `benchmarks/rss_probe.py` + `results-rss-core.json` replace the baseline-tool proxy in P1 evidence item 2; fresh-clone red suite fixed (`.gitignore` was hiding the `.lxz` golden vector); suite **201 passed, 1 skipped**. P1 reconciled to COMPLETE per the S38 owner acceptance recorded in PHASES/TASK_BREAKDOWN. Open: P1-T8 streaming `unpack`. Prior trail: Sessions 37 (P1 evidence draft), 36 (push unblocked), 34 (GUI-M3 closed), 33 (M3 verification), 31 (GUI-M2c), 30 (GUI-M2b), 29 (GUI-M2 async), 27–28 (GUI-M1 shell), 26 (P1 closure sweep), 24 (ADR-0007 container), 23 (CLI_REFERENCE), 22 (golden vectors + RSS capture), 20 (pipe + ADR-0007 draft), 19 (English-only scope), 12–18 (P0 batches A–E + first code) — full detail in SESSION_LOG.md)

## Current phase

**Phase 1 (P1) — Core Zstd baseline + harness, COMPLETE (owner-accepted 2026-10-17, Session 38; evidence: docs/P1_EVIDENCE_DRAFT.md).** Session 39 (2026-10-28) added the streaming encoder and the first Core-path peak-RSS measurements (P1-T7), and recorded P1-T8 (streaming decode) as the remaining memory item. Phase 0 documentation batches A–E are complete and hosted (`a1bf3c3`). Session 12 closed OQ-7 via ADR-0005 (Python ≥3.12,<4.0 per owner delegation) and landed the first real code: package skeleton (`pyproject.toml`, `src/lexora/`), canonicalizer rules CAN-R01/R02/R05, frame-level Zstd codec with round-trip verification, and a minimal tested CLI (`canon`/`zround`) — commit `8ee3bef`. Session 13 added the benchmark harness scaffold (`env` / `manifest` / `verify` / `audit-splits` / `run`; protocol §1–§4, §6 mechanics) and fixed the truncation-refusal behavior in `decompress()` (REQ-CMP-006 spirit). The `.lxz` container remains unimplemented (FORMAT_LXZ is PROPOSED — policy forbids implementing from it).

## Verified repository state

| Item | State |
|---|---|
| Implementation code | **Present (prototype):** `src/lexora/{__init__,canonicalize,zstd_core,container,cli}.py`, GUI package `src/lexora/gui/{app,service,crash,__main__}.py` (experimental M1–M3, offscreen-tested), `benchmarks/harness.py` + `corpus.py` — Phase-1 baseline + `.lxz` v0 container (accepted ADR-0007), no stable API |
| Tests / test tooling | **192 tests passing** (`python3 -m pytest -q`; environment note: if a stale third-party `libtmux` plugin reappears in a container, add `-p no:libtmux` — it crashed collection in some images. Sessions 20–24: `pipe` tests, golden-vector conformance, whitelist-invariant property tests, `.lxz` container suite (`tests/test_container_lxz.py`). Sessions 27–29: GUI service adapter suite (`test_gui_service.py`, incl. golden byte-parity vs CLI + AST Qt-isolation), offscreen widget e2e + launcher regression suite (`test_gui_app_offscreen.py`), and M2 job-core/widget tests (+9 in S29). Golden vectors: 9 canonicalization scenarios + lxz format vectors under `tests/vectors/lxz_format/` |
| Build/packaging config (`pyproject.toml` etc.) | **Present** — version `0.0.1.dev1`, requires-python `>=3.12,<4.0` (ADR-0005), deps pinned to tested versions (zstandard 0.25.0) |
| CI/CD workflows | **Paused by owner decision 2026-10-17 (OQ-15):** `.github/workflows/ci.yml` exists and last ran green on `e240af0` (Session 19); free-tier Actions minutes exhausted → no new runs until the whole app is complete or owner re-enables. Local gate meanwhile: `pytest -q` + linkcheck before every commit |
| License file | **Present** — **PolyForm Noncommercial 1.0.0**, © 2026 Dr. Sohil Momin (`LICENSE` at repo root, normative incl. the `Required Notice:` line; `license = "PolyForm-Noncommercial-1.0.0"` in pyproject). Per [ADR-0009](ADR/ADR-0009-license-polyform-noncommercial.md) (owner decision 2026-10-29), superseding [ADR-0006](ADR/ADR-0006-license-mit.md)'s MIT. Source-available, **not** OSI-approved: commercial use requires a separate licence. Metadata sweep completed S40 (pyproject, README, docs site, STATUS, PROGRESS, DECISIONS, ADR index) |
| Git remote | **Push UNBLOCKED (Session 36):** owner supplied a PAT in-chat; `HEAD:main` pushed directly — hosted `main` = `ac182cd` (fast-forward from `871a3ff`), carrying the full Sessions ~14–35 lineage including S33 `17a6711`, S34 `cdc2b8a`, merge `7a689a7`, and the S35 audit commit. Working branch also mirrored remotely (`qwen-code-be12e009-…`). Token was used via a temp credential store, removed afterward, never committed; owner advised to rotate it. Earlier "push blocked" rows above are append-only history, superseded here |
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

1. ~~Batch D/E not yet on remote~~ — resolved in Session 11 (hosted `main` = `a1bf3c3`). ~~Sessions 12–35 local-only~~ — resolved in Session 36: push unblocked, hosted `main` fast-forwarded (`ac182cd`, later `e472146` with the Session-37 evidence draft). Current branch tip not re-pushed this reconciliation (no credentials in this container; owner-supplied token required per policy).
2. ~~OQ-7 (Python version)~~ — closed via ADR-0005 (≥3.12,<4.0, owner delegation, Session 12). ~~OQ-5 (license)~~ — closed via ADR-0006 (PolyForm Noncommercial, `LICENSE` at repo root, Session 14); still blocks publishing to registries until owner approves a release per RELEASE_PROCESS.md.
3. **OQ-8 (corpus availability/rights)** blocks the first real benchmark run — harness scaffold is ready but refuses empty manifests by design.
4. ~~Owner decisions OQ-1…OQ-4~~ — resolved: ADR-0001…0004 Accepted via owner delegation (`86e6b55`).

## Known risks right now

- ~~Blueprint internal conflicts OQ-1…OQ-4~~ resolved by Accepted ADRs; remaining risk is spec text drift if later edits bypass the ADR process.
- GitHub Actions paused (OQ-15): CI workflow exists but runs no more — verification is local-only (`pytest -q` + linkcheck before every commit) until the owner re-enables.
- The GitHub token shared in chat (Sessions 36/37 pushes) must be treated as exposed — owner should revoke/rotate it (repo hygiene; no copy persists in this container or the repo).

## Health indicators *(verified, not asserted)*

- Tests: **192 passed** — `python3 -m pytest -q` (re-verified live 2026-10-17 on the current working branch after restoring the committed golden vector `tests/vectors/lxz_format/golden_1byte.lxz`, whose SHA-256 matches the pinned digest `27877df5…`; GUI offscreen tests additionally need `QT_QPA_PLATFORM=offscreen` with PySide6 + `libegl1` installed. Progression: 35 → 40 (S20 `pipe`) → 60 (S21–22 vectors) → 68 (S23 invariants) → 96 (S24 container suite) → 101 (S25) → 108 (S26) → 132 (S27 gui-service) → 148 (S28 file-ops/offscreen/launcher) → 157 (S29 job runner) → 162 (S30 G5/G6 panels) → 171 (S31 G7 settings) → 182 (S32 crash/path tests; committed red, fixed S33) → 186 (S33 picker seams + icon) → 192 (S34 About + crash-viewer tests). Note: the stale `libtmux` plugin crash is neutralized repo-wide via `addopts = "-p no:libtmux"` in pyproject.toml.)
- Link gate: `python3 scripts/linkcheck.py` → ALL INTERNAL LINKS OK (re-verified live 2026-10-17 after this documentation reconciliation).
- Build: `pip install -e .` **verified working** in this container 2026-10-17 (was previously untested).
- Coverage/badges/releases: none; none claimed anywhere in docs (README badges are flagged historical/local-snapshot only).

## Next milestone

Owner verdict on `docs/P1_EVIDENCE_DRAFT.md` (accept → flip PHASES P1 + TASK_BREAKDOWN P1-T1 to Landed; or request a Core-specific peak-RSS run first). CLI app scope is complete and GUI milestones M1–M3 landed; remaining GUI work (G8-full batch queue, drag-and-drop, shortcuts) is stretch-only per owner request. First *published* benchmark revision beyond R2 requires corpus growth toward ≥1 GiB (OQ-8) in a network-capable environment. Pushes remain possible while Actions stay paused (OQ-15).
