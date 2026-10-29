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

**Resumability, and the bug that taught us the rule.** A ≥1 GiB fetch spans many minutes and often many invocations, so `fetch_gutenberg_snapshot` checkpoints its sidecars during the run (`complete: true/false` in `sources.json`) and the next invocation reuses files already on disk (verified: 210 of 317 reused rather than re-downloaded). Before Session 42 the sidecars were written only at the end, which meant a killed fetch left texts on disk with no record and the next run re-downloaded everything.

Session 43 found the *second* half of that lesson: a checkpoint that rewrites the record from the current invocation's own progress **shrinks** the history when the invocation is killed. Observed for real — a 587-file directory was recorded as 232 files after two interrupted passes, with every text still on disk. Two changes follow:

1. **Checkpoints are supersets.** Prior records are seeded in and only the file just processed is upserted, so a checkpoint can add to the record and never remove from it. A failure for a file does remove its record (the manifest must not cite a text that is not there).
2. **`corpus-reconcile` is the way back.** `harness.py corpus-reconcile --root DIR` hashes the texts on disk and upserts a record for every file whose id belongs to the snapshot's requested set — no network, no re-walking 1400 ids. Files outside that set are counted as `orphaned` and deliberately **not** claimed. On the real snapshot it recovered 166 records in 12 s and brought the record to exact agreement with the disk (587 files, 287.9 MB).

Checkpoint cadence is every 25 files rather than every file: the sidecar grows to hundreds of KB, and per-file rewrites dominated a mostly-reuse pass (~0.8 s per id). The cost of the coarser cadence is that a kill can lose up to 25 recent entries — which is exactly what `corpus-reconcile` exists to repair.

**State at Session 58 (honest):** snapshot `gutenberg-cat-partial` — 1400 ids selected, **946 files / 502.1 MB fetched, 54 recorded failures** (404s and payloads under the 0.05 MB guard), `complete: false`. Manifest `e4b40cd8…` verifies with **0 problems**; split audit 667 train / 94 validation / 191 heldout with **no lineage straddling**. Five fetch passes this session took it from 287.9 MB to 502.1 MB (~43 MB per ~285 s pass, network-dependent). **≥1 GiB is still unmet: ~522 MB to go**, which is roughly a dozen more passes here — the shortfall is unattended runtime, not machinery. On a machine that can host it, the same command run in a loop finishes the job; here it advances ~40–50 MB per invocation.
