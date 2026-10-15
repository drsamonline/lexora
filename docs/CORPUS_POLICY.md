# LEXORA Corpus Policy

> **Status:** Draft (policy normative; **no corpus assembled** — OQ-8 open, verified 2026-10-15)
> **Owner:** Documentation architect (delegated); owner Dr. Sohil Momin accountable for data rights
> **Related:** [BENCHMARK_PROTOCOL.md](BENCHMARK_PROTOCOL.md) · PRIVACY_AND_DATA_HANDLING.md *(Batch D)* · [ADR-0004](ADR/ADR-0004-cleaning-error-metric.md)

## Purpose & scope

Rules for selecting, classifying, splitting, storing, and using benchmark/corpus data so results are meaningful, legal, privacy-safe, and leakage-free. Covers benchmark corpus, ADR-0004 review samples, and test fixtures.

## Composition targets (REQ-BMK-001)

- ≥1 GiB canonicalized bytes total.
- Languages: English, Hindi, Gujarati (each with a minimum share to be set when sources are known — recorded in manifest header, not guessed here).
- Categories: prose/books, web/news, technical docs, numeric/record-like tables, OCR-derived text (from P3), plus any domain the project claims for `.lxdb`.
- Sources must have documented distribution rights permitting private research use and derived-statistic publication.

## Provenance & classification

Every document gets: source ID, lineage ID (same work/publication ⇒ same lineage), license/rights note, privacy class:

| Class | Meaning | Dictionary training | Publication of excerpts |
|---|---|---|---|
| P0 public | openly licensed | ✅ train split only | ✅ |
| P1 internal | owner-controlled, non-sensitive | ✅ train split only | ❌ |
| P2 sensitive/clinical | personal or clinical content | ❌ **by default excluded from shared dictionaries and any published artifact**; separate opt-in experiments require explicit owner decision record | ❌ |

Clinical documents never enter shared dictionaries by default (REQ-SEC-002). P2 content may still be measured locally with results reported as aggregates only.

## Splits

70/10/20 train/validation/held-out **by lineage**, per BENCHMARK_PROTOCOL §2. Held-out touched once per revision. Split assignment stored in the frozen manifest; audit script enforces no-crossing rule.

## Sampling for cleaning-quality review (ADR-0004)

Stratified random sample ≥200 documents per language, seed recorded in manifest; two reviewers; disagreements adjudicated and logged; worksheets retained under `benchmarks/reviews/` (created at first run).

## Storage & hygiene

- Corpus lives outside the git repository (path recorded in `benchmarks/MANIFEST.json` once created); repo stores hashes/metadata only unless size allows tiny fixtures.
- Test fixtures in-repo must be P0-class or synthetic.
- Backups follow PRIVACY_AND_DATA_HANDLING retention rules (Batch D).

## Manifest format (v0 sketch — finalized when corpus exists)

```json
{
  "revision": "R0",
  "created": null,
  "docs": [{ "sha256": "...", "bytes": 0, "lineage": "...", "lang": "en|hi|gu",
             "category": "...", "rights": "P0|P1|P2", "split": "train|val|held" }],
  "seed": 0,
  "total_bytes_canonical": 0
}
```

Values above are schema placeholders, **not** data.

## Current status

No corpus exists. No rights survey done. Blocking question tracked as OQ-8 in [DECISIONS.md](DECISIONS.md). Until resolved, all benchmark statements remain "No validated benchmark results yet."
