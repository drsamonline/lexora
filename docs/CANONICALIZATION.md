# Canonicalization

> **Status:** Proposed — rule table NOT frozen (Phase 0 exit criterion)
> **Owner:** Unassigned
> **Last verified:** 2026-10-15 (no implementation; no golden vectors committed yet)
> **Related:** [SPECIFICATION.md §2](SPECIFICATION.md) · [ADR-0004](ADR/ADR-0004-cleaning-error-metric.md) · [GLOSSARY.md](GLOSSARY.md)

## Purpose & Scope

Defines the conservative, deterministic transformation from extracted raw text bytes to canonical UTF-8 bytes `C`. Everything downstream (compression losslessness contract) operates on `C` only.

## Versioning model

- Canonicalizer version string: `lexcan-<major>.<minor>` (proposed identifier format).
- Major bump = any change altering output bytes for existing inputs. Minor = additions gated behind new opt-in profiles.
- Version is serialized in every archive header and checked at verify time (`REQ-CAN-004`).

## Input / output contract

| Property | Rule | Status |
|---|---|---|
| Input | Raw extracted bytes from TXT reader, PDF extractor, or OCR engine, plus declared/detected source encoding | Approved design |
| Output | UTF-8, no BOM, LF newlines (`\n`) | Proposed (newline policy must be frozen per version) |
| Determinism | Pure function of (input bytes, version, profile) | Approved (SPEC §2.1) |

## Candidate rule classes (whitelist draft)

Only rules in this table may alter bytes; all other bytes pass through unchanged (`REQ-CAN-003`). Each row needs golden byte vectors before it can move to *Frozen*.

| ID | Class | Example transformation | Risk | Status |
|---|---|---|---|---|
| CAN-R01 | Encoding normalization | Source charset → UTF-8 | Low | Proposed |
| CAN-R02 | Line-ending normalization | CRLF/CR → LF | Low | Proposed |
| CAN-R03 | Trailing-whitespace trim | Per-line trailing spaces removed | Medium (tables) | Proposed |
| CAN-R04 | Control-char removal | Remove NUL, form feeds outside defined contexts | Medium | Proposed |
| CAN-R05 | Soft-hyphen removal | U+00AD deleted | Low | Proposed |
| CAN-R06 | Ligature expansion (opt-in) | ﬁ→fi etc. — script-safety reviewed | High for Indic | Deferred pending ADR |
| CAN-R07 | Unicode normalization (NFKC etc.) | — | High (Indic combining marks) | Rejected for v1; per-rule ADR required |
| CAN-R08 | Header/footer dedup (OCR/PDF) | Repeated page furniture collapsed | High | Proposed; needs page-order spec |
| CAN-R09 | OCR confidence-gated correction | Word replaced only if engine confidence ≥ threshold; logged | High | Proposed (SPEC §2.6) |

**Script safety (mandatory):** No rule may decompose or reorder Devanagari/Gujarati combining marks, ZWJ/ZWNJ (`REQ-CAN-005`). Any rule touching non-ASCII ranges requires script-specific golden vectors first.

## Error-rate metric

Defined by [ADR-0004](ADR/ADR-0004-cleaning-error-metric.md) — currently **Proposed**. Until accepted, cleaning quality claims are prohibited anywhere in docs/benchmarks.

## Test vectors (required before freeze)

Planned layout `tests/vectors/canonicalization/`:

```text
v001_crlf_lf/        input.bin, expected_output.bin, meta.json (version, rules applied)
v002_devanagari_marks/ ...
v003_zwnj_passthrough/ ...
```

*None exist yet.* Creating them is Phase 0 work after ADR acceptance.

## Open decisions

1. Freeze newline policy + BOM decision for `lexcan-0.1` (owner sign-off).
2. Accept/reject rule rows above individually.
3. ADR-0004 acceptance for the quality metric.
