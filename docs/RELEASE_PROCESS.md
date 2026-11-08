# LEXORA Release Process

> **Status: Proposed — no release has been made and no version exists yet.** This document defines the process that will be followed when the project reaches its first releasable state. It deliberately contains no URLs to nonexistent artifacts, no version numbers, and no dates.
> **Last verified:** 2026-10-15 against repository commit `7969155`.

## Preconditions (all must be true before a **stable** release)

Re-measured 2026-11-09 against `main` — the previous version of this table said "no code, no CI"
and had been wrong for three weeks.

| # | Condition | State 2026-11-09 |
|---|---|---|
| R1 | Implementation code exists with passing tests in-repo | ✅ **735 tests, 0 skipped**, CI green |
| R2 | Python version range decided | ✅ [ADR-0005](ADR/ADR-0005-python-version.md): `>=3.12,<4.0` |
| R3 | Licence chosen and LICENSE shipped | ✅ PolyForm Noncommercial 1.0.0 ([ADR-0009](ADR/ADR-0009-license-polyform-noncommercial.md)). **Open sub-item:** a `[gui]` artifact must also ship third-party notices + LGPL/GPL texts + a relinking statement |
| R4 | `.lxz` format frozen + conformance vectors published | ✅ [ADR-0007](ADR/ADR-0007-container-v0-freeze.md); `tests/vectors/lxz_format/` carries both a current and a pre-ADR-0020 vector |
| R5 | **Benchmark protocol executed at protocol scope on a rights-cleared corpus** | ❌ **The only blocker.** Smoke and protocol-*shaped* runs exist (R4/R5/R6 artifacts); the full 1.054 GiB three-split run needs a machine this project does not yet have |
| R6 | Versioning scheme adopted | ✅ in practice since 2026-10-30 (Conventional Commits, Keep-a-Changelog, SemVer) |
| R7 | CI or a recorded pre-release checklist | ✅ GitHub Actions green on every merge; `python3 scripts/linkcheck.py` gates the docs |

**A stable release is blocked on R5 alone.** Pre-releases are not: the versioning section below
allows an alpha "for builds distributed to testers with an explicit *not for production data*
notice", and that is exactly what `v0.1.0-alpha.1` is — every other precondition met, R5 stated as
unmet in the release notes rather than quietly skipped.

## Versioning (proposed, pending OQ-9 ADR)

- Semantic Versioning `MAJOR.MINOR.PATCH` for the tool and, separately, explicit **format version** fields inside `.lxz` headers (format compatibility is declared by the container, not inferred from the tool version).
- Pre-release identifiers (`-alpha.1`, `-beta.1`) allowed only for builds distributed to testers with an explicit "not for production data" notice.
- Canonicalization rule-table and dictionary revisions are versioned independently (see [CANONICALIZATION.md](CANONICALIZATION.md)); a release records the exact versions it bundles.

## Release workflow (once preconditions pass)

1. **Freeze:** branch `release/X.Y.Z`; only fixes allowed. Record the starting commit hash.
2. **Verify:** run the full test suite and round-trip conformance vectors; record actual commands, environment, and exit codes in [SESSION_LOG.md](SESSION_LOG.md). Never claim passes without logs.
3. **Benchmark gate:** run the frozen benchmark per [runbooks/BENCHMARK_RUNBOOK.md](runbooks/BENCHMARK_RUNBOOK.md); paste results into [BENCHMARK_RESULTS.md](BENCHMARK_RESULTS.md) with reproduction instructions. Marketing claims in release notes must not exceed these numbers.
4. **Changelog:** promote the relevant [Unreleased] entries of [../CHANGELOG.md](../CHANGELOG.md) into a dated `## [X.Y.Z]` section (Keep a Changelog format).
5. **Tag & build:** annotated git tag `vX.Y.Z`; build distribution artifacts from the tagged commit; record hashes (SHA-256) of every artifact in the release description.
6. **Publish:** GitHub Release created by the owner; attach artifacts + checksums. No badges are added unless a real CI pipeline publishes status.
7. **Post-release:** append a dated release entry to SESSION_LOG; update STATUS.md; if anything failed or was skipped, say so in the release notes rather than omitting it.

## Rollback / yank policy

- A released version is never deleted or force-pushed over. Defective releases are marked yanked/superseded with an explanation; the reason is recorded in CHANGELOG and SESSION_LOG.
- If a format-level defect is found after freeze, the format version field bumps and affected readers must fail closed (see [ERROR_HANDLING.md](ERROR_HANDLING.md)).

## What does NOT happen here

- No fabricated download links, package-index listings, Docker images, or signing keys are referenced until they genuinely exist.
- Encryption profile features remain gated behind Phase 9 review ([ENCRYPTION_PROFILE.md](ENCRYPTION_PROFILE.md)) regardless of release cadence.
