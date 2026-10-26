# LEXORA Release Process

> **Status: Proposed — no release has been made and no version exists yet.** This document defines the process that will be followed when the project reaches its first releasable state. It deliberately contains no URLs to nonexistent artifacts, no version numbers, and no dates.
> **Last verified:** 2026-10-15 against repository commit `7969155`.

## Preconditions (all must be true before any release)

| # | Condition | Current state (2026-10-15) |
|---|---|---|
| R1 | Implementation code exists with passing tests in-repo | ❌ No code, no test tooling |
| R2 | Python version range decided (OQ-7 in [DECISIONS.md](DECISIONS.md)) | ❌ Open |
| R3 | License chosen and LICENSE file added (OQ-5) | ✅ Done — PolyForm Noncommercial via ADR-0006, `LICENSE` at root (2026-10-15) |
| R4 | `.lxz` format frozen: byte layout approved + conformance test vectors published ([FORMAT_LXZ.md](FORMAT_LXZ.md) currently PROPOSED) | ❌ Not frozen |
| R5 | Benchmark protocol executed on a rights-cleared corpus; claims in README/CHANGELOG limited to measured results ([BENCHMARK_PROTOCOL.md](BENCHMARK_PROTOCOL.md), [CORPUS_POLICY.md](CORPUS_POLICY.md)) | ❌ No corpus (OQ-8), no results |
| R6 | Versioning scheme formally adopted via ADR (OQ-9; SemVer proposed) | ❌ Open |
| R7 | CI or at minimum a documented, reproducible pre-release checklist run recorded in SESSION_LOG | ❌ No CI |

Until every row above is ✅, **there is nothing to release** and this document stays Proposed.

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
