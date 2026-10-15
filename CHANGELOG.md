# Changelog

All notable changes to the LEXORA project (code **and** documentation) are documented here.
Format loosely follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning policy is an open decision ([docs/DECISIONS.md](docs/DECISIONS.md) OQ-9) — **no releases or version tags exist yet**.

## [Unreleased]

### Added
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
