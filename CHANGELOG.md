# Changelog

All notable changes to the LEXORA project (code **and** documentation) are documented here.
Format loosely follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning policy is an open decision ([docs/DECISIONS.md](docs/DECISIONS.md) OQ-9) — **no releases or version tags exist yet**.

## [Unreleased]

### Added
- 2026-10-16 — Sessions 20–22 app-build velocity (working branch; commits `3e94d57`, `88286b1`, `38bc99d`):
  - **Session 20 (`3e94d57`):** `docs/ADR/ADR-0007-container-v0-freeze.md` drafted — proposed minimal `.lxz` v0 byte-layout freeze with exact layout + verification plan, tracked as **OQ-11** in docs/DECISIONS.md (owner accept/amend/reject is NEXT_SESSION task 0; nothing implemented from PROPOSED specs meanwhile). New CLI subcommand `lexora pipe` — end-to-end baseline flow canon → compress → verify-decompress with cost-accounting line; 5 new tests, suite 35 → **40 passed**.
  - **Sessions 21–22 (`88286b1`, `38bc99d`):** P1-T2 golden vectors landed — `scripts/gen_canon_vectors.py` generates 9 deterministic vectors under `tests/vectors/canonicalization/` (CRLF→LF, Devanagari marks/ZWJ passthrough, ZWNJ passthrough, soft-hyphen removal, declared cp1251 transcode, UTF-8/UTF-16LE BOM handling, empty input, ASCII passthrough), locked byte-exact by `tests/test_canon_vectors.py`; suite now **60 passed**. P1-T6 peak-RSS capture implemented in `benchmarks/harness.py run` (forked child runs the identical encode call; parent samples `/proc/<pid>/status` VmHWM — Linux-only, honest skip reason otherwise; failures recorded, never faked). First bug found and fixed: child received `str` instead of `Path` for the output path (AttributeError on `write_bytes`).
  - **Benchmark artifact R3 (measurement run 2026-10-16, this session):** `python benchmarks/harness.py run --reps 3 --revision 3` on the unchanged Tier-1 corpus (manifest hash `a32240d7…`) produced `benchmarks/results-r3.json` — 12 rows (6 files × zstd19/xz9) plus the first real peak-RSS captures: **zstd19 = 85,956 KiB, xz9 = 35,348 KiB** (largest manifest file, tier label T1-gutenberg-p0 mandatory). This is a harness artifact, **not** a published revision: per protocol §7 an R3 renumber requires a manifest change (corpus bytes are identical to R2) and publication into BENCHMARK_RESULTS.md needs owner review — numbers therefore NOT published yet.
- 2026-10-16 — Session 19 delivery & scope: owner supplied a working GitHub token; Sessions 14–18 commits pushed (`e240af0`) and **merged to hosted `main` via PR #4** (merge commit `0fafef4`); CI verified green on `e240af0`. Token stored only in gitignored `.vault/github_token.txt`; repo scanned — no full token ever committed. **Owner scope decision recorded:** English-only is the build scope for rapid app development; Hindi/Gujarati corpus coverage moved to deferred/future capability across CORPUS_POLICY/STATUS/PROGRESS/NEXT_SESSION.
- 2026-10-16 — Session 18 benchmark Revision **R2** published (manifest regeneration, closes R1's correction note): `benchmarks/MANIFEST.json` rebuilt with per-file rights/language/category folded in from provenance sidecars (new hash `a32240d7…`, supersedes `7d65d09d…`; `verify` 6 files 0 problems; split audit clean). New harness subcommand `corpus-commit` copies the small provenance JSONs into the committed evidence dir `benchmarks/provenance/gutenberg-r0/` (raw texts remain gitignored) so the classification chain no longer lives only in gitignored state. Measured numbers unchanged by design (same corpus bytes; metadata does not enter the measurement path) — R2 block in `docs/BENCHMARK_RESULTS.md` re-publishes them under the corrected manifest with mandatory tier label T1-gutenberg-p0 and still **no ADR-0001 verdict**.
- 2026-10-16 — Session 17 first benchmark revision published: **Revision R1** in `docs/BENCHMARK_RESULTS.md` from the Tier-1 fallback corpus (commit `908698c`: `benchmarks/corpus.py` tiered fetch + harness manifest v2). Measured smoke baselines on 7,124,095 B public-domain English text (tier label T1-gutenberg-p0 mandatory on all figures): Zstd-19 stored 2,139,962 B (ratio 0.3004), XZ-9 stored 2,119,756 B (ratio 0.2975); held-out file ratios 0.2809 / 0.2786; no ADR-0001 verdict issued (corpus ≪ ≥1 GiB protocol target). Evidence artifacts committed: `benchmarks/MANIFEST.json` (hash re-verified at publication), `benchmarks/env.json`, `benchmarks/results-r0.json`; raw corpus texts stay gitignored with provenance sidecars recorded. STATUS/PROGRESS/CORPUS_POLICY/README updated to reflect R1 honestly.
- 2026-10-15 — Session 16 push unblocked (owner supplied a working token): pushed local `main` (`b026d15..7259ee3`) to GitHub, so Sessions 12–15 work (Phase 1 prototype code, benchmark harness, OQ-5/OQ-8 resolution, README badges + CI workflow) is now hosted. First CI run on GitHub Actions: **CI / 7259ee3 / completed / success** — the CI badge in README is now backed by a live passing run. Token used transiently via GIT_ASKPASS only; never persisted.
- 2026-10-15 — Session 15 badges & CI (owner request "update readme file with github badges"):
  - `.github/workflows/ci.yml` — **real** CI workflow (Python 3.12, `pip install -e ".[dev]"`, `pytest -q`, linkcheck). Reverses the earlier "no workflows yet" decision because runnable code + tests now exist (Phase 1 prototype). First-run result will be recorded here once Actions executes it.
  - `README.md` — badge row: CI (points at the real workflow), Tests (static snapshot: 35 passed, re-verified locally), Python 3.12 (matches `requires-python`), License MIT (matches `LICENSE`). Footer rewritten from "no badges exist" to explicit badge-provenance statements. Also corrected two stale README blocks ("no implementation code exists yet" and the Features-by-maturity table) that contradicted the Phase 1 code already on `main`.
### Fixed
- 2026-10-16 — Peak-RSS capture bug (P1-T6, commit `38bc99d`): forked child in `benchmarks/harness.py::_peak_rss_kib` was passed `str(out_path)` while the `SYSTEMS` callables use `Path` methods (`write_bytes`/`open`) — every measurement failed with AttributeError. Now passes a `Path`, uses `os._exit(2)` to distinguish encode failures from success, and the skip-reason text matches the actual VmHWM mechanism. Verified end-to-end: real per-system peaks recorded in `benchmarks/results-r3.json`. Also fixed two golden-vector expectation typos in `tests/test_canon_vectors.py` (missing ZWJ; non-canonicalizable codepoint in the REQ-CAN-005 set).
- 2026-10-15 — Test-suite environment: container had accumulated a broken third-party pytest plugin (`libtmux`'s auto-registered plugin crashes under pytest 9.x — marks applied to fixtures). Uninstalled `libtmux`; `python -m pytest -q` now passes cleanly (35 passed). Earlier session claims of "39 passed / 4 skipped" could not be reproduced against current `main` (only 3 test files, 35 tests, no skips); corrected honestly in README.
- 2026-10-15 — Removed dangling "Last verified: commit `816f58f`" reference in README (commit does not exist in this repo's history).
- 2026-10-15 — Session 11 remote reconciliation (no new documents): configured `origin` (credential-free URL), discovered remote `main` had advanced via PR #2 merge (`76476cf`, Batch D landed remotely), performed clean non-ff merge into local `main` (`a1bf3c3`), re-verified linkcheck (OK), and pushed — **hosted `main` now contains Batches A–E**. Token used transiently via GIT_ASKPASS; never persisted to repo or git config.
- 2026-10-15 — Batch E GitHub & release polish (drafted, Session 10; commit `aa266a2` + PR-template fix):
  - `CONTRIBUTING.md` — project-status disclaimer, honesty ground rules, current workflow, branching/PR guidance.
  - `.github/ISSUE_TEMPLATE/design-proposal.yml`, `.github/ISSUE_TEMPLATE/documentation.yml` — structured issue forms (proposal areas, doc-error severity).
  - `.github/pull_request_template.md` — honesty checklist + "verification actually run" table (resolves the dangling reference from `aa266a2`).
  - `docs/RELEASE_PROCESS.md` — release preconditions, proposed versioning scheme (OQ-9 pending formal adoption), rollback policy, explicit non-goals. **No releases or tags exist.**
  - CI workflows and badges intentionally **not created** — no runnable checks exist yet; placeholders prohibited (master prompt §2.10).
- 2026-10-15 — Batch D security & operations documentation (drafted, pending owner review):
  - `SECURITY.md` (root) — vulnerability reporting process; explicit "no guarantees" status; no fabricated contacts or SLAs.
  - `docs/SECURITY_ARCHITECTURE.md` — trust boundaries, asset inventory, REQ-SEC mechanism map.
  - `docs/THREAT_MODEL.md` — STRIDE-based threat register TM-01…TM-13 and attacker profiles.
  - `docs/PRIVACY_AND_DATA_HANDLING.md` — P0–P3 data classification tiers, dictionary leakage policies.
  - `docs/ENCRYPTION_PROFILE.md` — proposed optional AEAD encryption blueprint (Phase 9 gate; Proposed status only).
  - `docs/ERROR_HANDLING.md` — machine-readable error taxonomy, severity levels, fail-closed contract.
  - `docs/LOGGING_AND_DIAGNOSTICS.md` — privacy-safe logging rules, log levels, run manifest format.
  - `docs/TROUBLESHOOTING.md` — symptom → cause → action mapping for the designed system.
  - `docs/runbooks/BENCHMARK_RUNBOOK.md`, `CORRUPTION_TRIAGE.md`, `PERFORMANCE_TRIAGE.md`, `RECOVERY_RUNBOOK.md`.
- 2026-10-15 — Batch A documentation foundation:
  - `README.md` — project overview with honest Implemented/In progress/Planned split; no badges (none applicable).
  - `docs/index.md` — documentation portal organized by reader need.
  - `docs/PROJECT_CHARTER.md` — problem, goals, constraints, non-goals, risks (Draft, pending owner approval).
  - `docs/PRODUCT_REQUIREMENTS.md` — requirements `REQ-ING/CAN/CMP/EXP/FMT/BMK/RES/SEC-*` with priorities and verification methods.
  - `docs/GLOSSARY.md` — canonical terminology.
  - `docs/DECISIONS.md` — ADR index + open questions OQ-1…OQ-10 (includes four blueprint internal conflicts).
  - `docs/ADR/README.md`, `docs/ADR/ADR-0001-template.md` — decision-record system (no ADRs accepted yet).
  - `docs/STATUS.md`, `docs/PROGRESS.md`, `docs/SESSION_LOG.md`, `docs/NEXT_SESSION.md` — session continuity artifacts.
  - `docs/templates/SESSION_NOTE_TEMPLATE.md`, `docs/templates/ADR_TEMPLATE.md`.
  - Root hygiene files: `.editorconfig`, `.gitattributes`, `.gitignore`.
- 2026-10-15 — Documentation audit (Session 1): repository inventory, conflict identification, staged batch plan (A–E). *(Report delivered in conversation; findings persisted into DECISIONS.md.)*

### Changed
- Nothing changed in existing files; `LEXORA_Full_Blueprint_Design_Master_Prompt.md` remains untouched as source of truth.

### Fixed / Removed / Deprecated / Security
- None.

---

*Compatibility impact:* documentation-only; no format/API/data implications.
*Note:* this changelog will gain commit links once commits are created; hashes are recorded only when verified.
