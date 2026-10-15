# Security Policy

> **Status:** Active (process statement only)
> **Last verified:** 2026-10-15

## Current security posture — read this first

**LEXORA has no implementation.** The repository currently contains design documentation only. There is no code to run, no decoder to feed archives to, and therefore **no security guarantees of any kind are claimed or provided**. Design-intent documents ([docs/SECURITY_ARCHITECTURE.md](docs/SECURITY_ARCHITECTURE.md), [docs/THREAT_MODEL.md](docs/THREAT_MODEL.md)) describe controls that *will* be built; none are enforced today. Do not process real or sensitive data with LEXORA tooling until it exists and passes the verification steps listed in those documents.

## Reporting a vulnerability

When (and only when) implementation code exists in this repository, report suspected vulnerabilities as follows:

1. Open a **private** security report via the GitHub repository's "Report a vulnerability" feature (private vulnerability reporting), if enabled by the repository owner; otherwise open a normal issue titled `security: <short summary>` **without** including exploit details, proofs of concept, or crafted files.
2. Include: affected version/commit, component (ingest / canonicalizer / encoder / decoder / harness), reproduction steps at the level of "which command on which input class," and sanitized logs ([docs/LOGGING_AND_DIAGNOSTICS.md](docs/LOGGING_AND_DIAGNOSTICS.md)).
3. **Never include document contents** from corpora you do not own, and never attach archives containing personal or clinical data.

A dedicated security contact address and response-time commitment are **not published here because none have been confirmed by the project owner yet**. This section will be updated with real contact details and an honest response window once the owner supplies them — tracked as an open item in [docs/DECISIONS.md](docs/DECISIONS.md).

## Scope notes

- Issues about hostile `.lxz` inputs (crashes, memory exhaustion on decode) are in scope once a decoder ships.
- Privacy-policy violations (e.g., sensitive content found in a published dictionary) follow [docs/PRIVACY_AND_DATA_HANDLING.md](docs/PRIVACY_AND_DATA_HANDLING.md) incident handling.
- Encryption-related findings are out of scope until the optional profile leaves Proposed status ([docs/ENCRYPTION_PROFILE.md](docs/ENCRYPTION_PROFILE.md)).

## Supported versions

None released. When releases exist, this table will list supported commit ranges; until then every artifact is pre-release and unsupported.
