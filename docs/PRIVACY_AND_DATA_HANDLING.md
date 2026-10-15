# LEXORA Privacy & Data Handling Policy

> **Status:** Draft (policy of record; enforceable audit procedures depend on OQ-8 corpus answers — verified 2026-10-15)
> **Owner:** Documentation architect (delegated)
> **Last verified:** 2026-10-15
> **Related:** [CORPUS_POLICY.md](CORPUS_POLICY.md) · [THREAT_MODEL.md](THREAT_MODEL.md) TM-06/TM-07 · REQ-SEC-002 · [ENCRYPTION_PROFILE.md](ENCRYPTION_PROFILE.md) · blueprint §8.2, §2 (dictionary leakage note)

## Purpose & scope

Defines how sensitive text is classified, stored, processed, and published across the LEXORA lifecycle: ingestion → canonicalization → compression → dictionaries/benchmarks → artifacts. Applies to project-owned corpora and any artifact the project publishes. User-run local archives are under the user's own policy; this document still governs defaults that code MUST implement (REQ-SEC-002).

## Core principles

1. **Compression is not confidentiality.** Canonical bytes and `.lxz` blocks are *not* secret storage. Anyone with the archive can recover the exact text. Treat every archive containing sensitive classes as a sensitive object itself.
2. **Dictionaries leak vocabulary.** A shared dictionary trained on documents exposes frequent (and especially rare-but-included) strings to anyone holding the dictionary. Default: sensitive corpora NEVER train shared or published dictionaries (REQ-SEC-002).
3. **Conservative by default.** Where a handling question has no approved answer yet, choose the least-disclosure option and record the open question here rather than inventing permissions.
4. **Originals outlive archives.** Deletion of source files is never automatic; similarity between records must never trigger deletion (blueprint non-goals).

## Data classification tiers

| Tier | Description | Examples | Storage rules | Publication rules |
|---|---|---|---|---|
| P0 | Public, redistribution-cleared | Owner-published docs, permissively licensed texts | Normal | May seed shared dictionaries after owner sign-off |
| P1 | Internal / non-sensitive private | Project notes, synthetic test data | Local only, no special controls | Aggregates only; excerpts need clearance |
| P2 | Personal data present | Named individuals in letters/records | Encrypted-at-rest at OS level recommended (operator choice); never in shared dictionaries | No excerpts, no dictionary training without explicit owner decision + documented consent basis |
| P3 | Sensitive categories (clinical, health, special-category data per applicable law) | Medical OCR'd scans, clinical notes | Default-deny for any shared use; provenance record required; retention decided by owner (OQ-8) | Never published; benchmark results must be aggregate-only and reviewed against re-identification risk |

Classification is set per corpus manifest entry ([CORPUS_POLICY.md](CORPUS_POLICY.md)); unknown ⇒ treat as P2 minimum until classified.

## Lifecycle controls

| Stage | Control | Status |
|---|---|---|
| Ingest | Record source path, rights statement, tier in manifest before processing | Planned (Phase 1+) |
| Canonicalization | Rules never *add* external content; audit trail CAN-R01…R09 keeps transformations reviewable | Design frozen pending rule-table freeze |
| Compression | Round-trip verification guarantees what exists later equals what existed before — privacy-relevant because "recovery" is exact | Spec-mandated |
| Dictionary training | Tier gate: only P0 cleared for shared/publication; P2/P3 require owner decision recorded in DECISIONS.md | Policy active (paper) |
| Benchmarks | Publish totals/ratios + hashes; raw excerpts prohibited by default (TM-07) | Protocol drafted |
| Artifacts & logs | Logs MUST NOT echo document text bodies; identifiers/hashes only ([LOGGING_AND_DIAGNOSTICS.md](LOGGING_AND_DIAGNOSTICS.md)) | Policy active (paper) |
| Disposal | No silent deletion; removal = manifest event with date; originals kept until owner says otherwise | Policy active (paper) |

## Multilingual & cultural considerations

LEXORA targets English, Hindi (Devanagari), and Gujarati collections. Names, addresses, and honorifics in these scripts are personal data exactly like Latin-script equivalents; classification MUST not treat non-Latin scripts as "less identifying." Canonicalization rules that fold or normalize personal-name spellings are reviewed against the golden vectors so identity-bearing strings change predictably and auditably (ADR-0004 rule-audit metric applies).

## Incident handling (privacy)

A suspected disclosure (e.g., sensitive term found in a published dictionary) follows [runbooks/CORRUPTION_TRIAGE.md](runbooks/CORRUPTION_TRIAGE.md) intake steps first (contain, snapshot), then: revoke/replace the artifact (new dictionary ID — IDs never silently change meaning), document in SESSION_LOG, notify affected parties as directed by the owner. No notification SLA is promised here because contact obligations depend on jurisdiction and owner decisions.

## Open items blocking enforcement

- **OQ-8**: actual corpus sources, rights, and whether clinical material is in scope at all. Until answered, P3 rules remain default-deny but untestable.
- No code exists ⇒ all controls above are paper policy; they become binding when implemented behind REQ-SEC-002 verification (corpus-policy audit).
