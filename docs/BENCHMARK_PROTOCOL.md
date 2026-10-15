# LEXORA Benchmark Protocol

> **Status:** Draft v0 (methodology normative per SPEC §5.2 / ADR-0001…0003; **zero runs executed** — BENCHMARK_RESULTS.md holds no numbers)
> **Owner:** Documentation architect (delegated)
> **Last verified:** 2026-10-15
> **Related:** [CORPUS_POLICY.md](CORPUS_POLICY.md) · [BENCHMARK_RESULTS.md](BENCHMARK_RESULTS.md) · [COST_MODEL.md](COST_MODEL.md) · [ADR-0001](ADR/ADR-0001-gate-scope.md)

## Purpose & scope

Fully specified, reproducible procedure for measuring LEXORA against frozen baselines: corpus handling, splits, codec settings, accounting rules, run repetition, reporting schema, and revision control of the benchmark itself. Applies from P2 onward.

## 1. Corpus

- Composition, rights, privacy: see [CORPUS_POLICY.md](CORPUS_POLICY.md). Minimum ≥1 GiB canonicalized bytes covering English, Hindi, Gujarati plus structured categories (numeric/record-like) where available.
- **Frozen manifest:** file list with SHA-256 per document, source-lineage ID, category, language, split assignment. Manifest hash recorded in every results artifact. Changing any input ⇒ new benchmark revision (§7).

## 2. Splits (leakage control)

| Split | Share | Used for |
|---|---|---|
| Train | 70% | Dictionary/grammar/model induction only |
| Validation | 10% | Candidate selection, tuning, promotion screening |
| Held-out | 20% | Final verdict only; touched once per revision |

Splitting is by **source lineage** (documents from one book/report/PDF never straddle splits). Automated audit test fails the run if any lineage ID appears in two splits (REQ-EXP-002).

## 3. Frozen baselines (measurement-only per ADR-0002/0003)

| Baseline | Exact settings | Tool/version pinning |
|---|---|---|
| Zstandard | level 19, default block behavior, no dict | `zstd` + `python-zstandard` versions captured |
| Brotli | quality 11, window 24, default size hint | library version captured |
| XZ/LZMA | preset 9 (`-9e` documented variant noted separately) | xz utils version captured |
| PPMd | order used: documented default of pinned tool | 7-Zip/ppmd version captured |

Baselines compress the **same canonical byte streams** as LEXORA (apples-to-apples post-canonicalization). Baseline outputs are single-file totals including their own container overhead.

## 4. Cost accounting (normative, REQ-CMP-004)

`TotalCost(document or corpus) = Σ serialized bytes produced by the encoder`, including: container header/footer, block metadata, index entries, embedded side tables, grammar/dictionary bytes *when shipped inside the archive*, and external-dictionary bytes charged at full size when dictionary is required to decode (with a separate "shared-amortized" secondary view clearly labeled, never used for gates). Exclusions forbidden unless explicitly listed here. Harness asserts reported total == actual file size on disk, byte-exact.

## 5. Metrics

Primary: total stored size (bytes) per document, per category, per corpus; ratio vs best baseline. Secondary: encode/decode wall time, peak RSS, decode-without-full-archive flag honored (REQ-CMP-005), cleaning-quality report linkage (ADR-0004 — measured separately, not conflated with compression).

## 6. Run procedure

1. Pin environment: OS/distro, CPU model, RAM, Python version, all library/tool versions, compiler flags if relevant → captured automatically into `env.json`.
2. Verify manifest hashes match frozen revision.
3. Run each system N≥3 times fresh processes; record variance (min/median/max); median used for verdicts.
4. Compute verdict per ADR-0001: corpus held-out reduction vs best baseline → Pass ≥10% / Partial ≥3% / Fail <3%; per-category promotion screening on validation, reproduction check on held-out.
5. Produce report from template `docs/templates/BENCHMARK_REPORT_TEMPLATE.md`; append to BENCHMARK_RESULTS.md with revision number, date, git commit hash, manifest hash, env hash.

## 7. Revision rules

A new benchmark revision (renumbered R#) is mandatory when: corpus manifest changes, any baseline setting/version changes, canonicalizer rule table version changes, or cost-accounting rules change. Old revisions remain published; claims must cite a revision ID.

## 8. Honesty constraints

- No extrapolation from train/validation to held-out claims.
- No cherry-picked subsets presented as corpus results.
- Any failed/incomplete run recorded as such.
- Until first valid run, README and results page state **"No validated benchmark results yet."**
