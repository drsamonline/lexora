# Architecture Decision Records

Numbered decision records for LEXORA. See [../DECISIONS.md](../DECISIONS.md) for the index and open questions.

## Rules

- One file per decision: `ADR-NNNN-short-title.md` (zero-padded, sequential).
- Statuses: **Proposed → Accepted** (owner approval) **| Rejected**, or **Superseded by ADR-XXXX**.
- Accepted ADRs are immutable except for status-link corrections; new understanding ⇒ new ADR that supersedes.
- Every material decision affecting behavior, format, security, compatibility, or scope gets an ADR.

## Template

Use [ADR-0001-template.md](ADR-0001-template.md) as the starting point (it doubles as the canonical template until ADR-0001 is created; when the first real ADR is written, it becomes `ADR-0001-*.md` and the template moves to `../templates/ADR_TEMPLATE.md`).

## Index

| ID | Title | Status | Date |
|---|---|---|---|
| [ADR-0001](ADR-0001-gate-scope.md) | Benchmark gate scope | **Accepted** (delegated) | 2026-10-15 |
| [ADR-0002](ADR-0002-brotli-role.md) | Brotli role | **Accepted** (delegated) | 2026-10-15 |
| [ADR-0003](ADR-0003-ppmd-role.md) | PPMd role | **Accepted** (delegated) | 2026-10-15 |
| [ADR-0004](ADR-0004-cleaning-error-metric.md) | Cleaning error metric | **Accepted** (delegated) | 2026-10-15 |
| [ADR-0005](ADR-0005-python-version.md) | Python version range | **Accepted** (delegated) | 2026-10-15 |
| [ADR-0006](ADR-0006-license-mit.md) | License = MIT | **Accepted** (delegated) | 2026-10-15 |
| [ADR-0007](ADR-0007-container-v0-freeze.md) | `.lxz` v0 layout freeze | **Accepted** w/ recorded amendments (delegated) | 2026-10-16 |
| [ADR-0008](ADR-0008-gui-toolkit-architecture.md) | GUI toolkit, packaging & architecture | **Accepted** (delegated) | 2026-10-17 |

Template location note: the canonical template now lives at [../templates/ADR_TEMPLATE.md](../templates/ADR_TEMPLATE.md); `ADR-0001-template.md` remains for historical continuity only.
