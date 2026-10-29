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

**R0 snapshot assembled (Session 17, 2026-10-16):** no owner-supplied corpus yet (`data/raw/` empty); the tiered fallback in `benchmarks/corpus.py` fetched a Tier-1 P0 public-domain snapshot — 6 Project Gutenberg English books, 7,124,095 B. First smoke-baseline numbers published as Revision R1 in [BENCHMARK_RESULTS.md](BENCHMARK_RESULTS.md) with mandatory tier label. **Manifest regenerated Session 18 (Revision R2):** per-file rights/language/category now folded in from provenance sidecars (hash `a32240d7…`, supersedes R1's `7d65d09d…`); provenance evidence chain committed under `benchmarks/provenance/gutenberg-r0/` (raw texts stay gitignored). **Full-corpus targets remain unmet** (≥1 GiB, category mix) and OQ-8 stays open until owner input or a compliant assembly. **Owner directive (2026-10-16, Session 19):** build the app rapid-first using English only; Hindi/Gujarati corpus coverage is a future capability, no longer a requirement gating Phase-1→app delivery; ADR-0001 verdicts are still withheld. Benchmark statements beyond R1/R2's scope remain "No validated benchmark results yet."

## Bulk selection from the Project Gutenberg catalog (Session 42)

The curated id lists in `benchmarks/corpus.py` are small by design (64 English, 8 Hindi, 8 Gujarati) — they were built for smoke snapshots, and they cap out around 70 MB. Reaching the ≥1 GiB target (OQ-8) needs a selection rule that is reproducible without hand-curating a thousand ids, so the harness now derives ids from **Project Gutenberg's own catalog**.

**Rule** (`select_ids_from_catalog`, deliberately boring): keep catalog rows whose `Type` is `Text` and whose `Language` contains `en`; drop any id passed in `--exclude-ids`; order by PG id **ascending**; take the first `--catalog-limit`. Ordering by id rather than by popularity or title means the selection does not reshuffle when the catalog is regenerated — new downloads append at the end, so a snapshot can be resumed and grown rather than rebuilt.

**Reproducibility.** The catalog is downloaded once (21,271,171 B, cached under the gitignored `corpus/_catalog/`), and its SHA-256 is recorded in the snapshot's `selection` block alongside the filter, the order and the limit. Snapshot `gutenberg-cat-partial` was selected from catalog `3cece81ad3a9261f1b2fbfd2db1e1819cf0c4d3bcffc02ef74ccb8865b46895c`; with the same digest and the same filter the id list is identical, which `select_ids_from_catalog` is tested to guarantee.

**Rights — the caveat that must not be glossed.** The catalog has **no rights column**. Selection therefore inherits Gutenberg's US-public-domain hosting posture, and each downloaded file carries its own licence statement (the sidecar's rights class P0 rests on that, exactly as it did for the curated lists). A **per-item RDF rights check is an open item**, not something this rule implies. If publication ever depends on per-item rights evidence, the selection needs that check added before it is trusted.

**Resumability.** A ≥1 GiB fetch spans many minutes and often many invocations, so `fetch_gutenberg_snapshot` now **checkpoints its sidecars after every file** (`complete: true/false` in `sources.json`). An interrupted run therefore keeps its provenance and the next run reuses the files already on disk (verified: 210 of 317 files reused rather than re-downloaded) instead of starting over. Before Session 42 the sidecars were written only at the end, which meant a killed fetch left texts on disk with no record and the next run re-downloaded everything.

**State at Session 42 (honest):** snapshot `gutenberg-cat-partial` — 1400 ids selected, **317 files / 165.3 MB fetched, 29 recorded failures** (404s and payloads under the 0.05 MB guard), `complete: false`. Manifest `a2af8ae9…` verifies with 0 problems; split audit 215 train / 38 validation / 65 heldout with no lineage straddling. **≥1 GiB is still unmet** — the shortfall is fetch time, not machinery, and the same command resumes it (see NEXT_SESSION.md).
