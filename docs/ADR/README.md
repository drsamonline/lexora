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
| [ADR-0006](ADR-0006-license-mit.md) | License = MIT | **Superseded** by ADR-0009 | 2026-10-15 |
| [ADR-0007](ADR-0007-container-v0-freeze.md) | `.lxz` v0 layout freeze | **Accepted** w/ recorded amendments (delegated) | 2026-10-16 |
| [ADR-0008](ADR-0008-gui-toolkit-architecture.md) | GUI toolkit, packaging & architecture | **Accepted** (delegated) | 2026-10-17 |
| [ADR-0009](ADR-0009-license-polyform-noncommercial.md) | License = PolyForm Noncommercial 1.0.0 (supersedes ADR-0006) | **Accepted** (owner decision) | 2026-10-29 |
| [ADR-0010](ADR-0010-lxdb-direction.md) | `.lxdb` direction — container-of-containers vs block pool (no byte layout) | **Accepted** (owner delegation) | 2026-10-29 |
| [ADR-0011](ADR-0011-gui-process-separation.md) | GUI distribution — process separation, not in-process linking | **Accepted** (owner choice) | 2026-10-29 |
| [ADR-0012](ADR-0012-default-encode-level.md) | Default zstd level = 9 (one source of truth across library, CLI, GUI) | **Accepted** (owner delegation) | 2026-10-29 |
| [ADR-0014](ADR-0014-ziptastic-codec.md) | Second codec — ziptastic (CHCE) behind a codec registry | **Accepted** (owner delegation) | 2026-11-07 |
| [ADR-0015](ADR-0015-codec-policy.md) | Codec policy — zstd stays the default, CHCE is the documented max-ratio preset (closes OQ-16) | **Accepted** (owner decision) | 2026-11-07 |
| [ADR-0016](ADR-0016-queryable-archive.md) | Queryable compressed archive — SQLite index over `.lxz` payloads (no new format bytes; `.lxdb` still gated) | **Accepted** (owner decision) | 2026-11-07 |
| [ADR-0017](ADR-0017-pdf-engine.md) | PDF ingestion engine — pypdf (BSD-3) over PyMuPDF (AGPL); closes ADR-0009's open PyMuPDF item | **Accepted** (owner delegation) | 2026-11-07 |
| [ADR-0018](ADR-0018-level-usage-error.md) | An out-of-range `--level` is a usage error (exit 2) on every surface — makes the GUI↔CLI parity claim true | **Accepted** (owner delegation) | 2026-11-07 |
| [ADR-0019](ADR-0019-ocr-plugin.md) | OCR as an external plugin — Tesseract as a binary, no PDF renderer (embedded page images via pypdf + Pillow) | **Accepted** (owner delegation) | 2026-11-07 |
| [ADR-0020](ADR-0020-codec-id-naming.md) | `codec_id` names a level it does not use — rename to a level-neutral id at v0→v1, old id read as an alias | **Proposed** (awaiting owner decision) | 2026-11-08 |
| [ADR-0021](ADR-0021-codec-policy-v2.md) | Codec policy v2 — **PPMd is the max-ratio preset** (ties CHCE at 7× the speed, no external binary); CHCE demoted to the extreme option; zstd stays default | **Withdrawn** same day — PPMd corrupts 3–8 % of real files; CHCE stays the preset | 2026-11-08 |
| [ADR-0022](ADR-0022-language-plugins.md) | **Language support arrives as plugins** (cleaning rules + tokenizer + optional dictionary/OCR hints); English becomes the first plugin; decoding never needs one | **Proposed** (owner direction) | 2026-11-08 |
| [ADR-0013](ADR-0013-lxdb-layout.md) | `.lxdb` single-file shape + mutation model (append payload, rewrite index, commit by superblock flip) — **no byte layout** | **Proposed** (blocked on G2) | 2026-11-07 |

Template location note: the canonical template now lives at [../templates/ADR_TEMPLATE.md](../templates/ADR_TEMPLATE.md); `ADR-0001-template.md` remains for historical continuity only.
