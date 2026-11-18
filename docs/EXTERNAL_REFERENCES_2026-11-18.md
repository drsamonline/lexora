# External references, assessed against this project

2026-11-18. A set of compression links was triaged for the CHCE fleet
(`audit/docs/compression-links-2026-11-18.md`). This is the subset that applies to **lexora**, and
what it says about what this project already does well — which turns out to be most of it.

**Status: proposed.** Nothing here is implemented, and no gate is claimed to be met. Under
AC-G-1, a document may not claim a feature unless code and passing tests exist in-repo.

## What lexora already does better than the source of these ideas

The 2026 AIT Data Compression Challenge's methodological lessons are: a **public training set and a
hidden test set**, **external datasets** for generalisation, and **Pareto reporting** rather than a
single number.

Three of those four are already normative here:

| AIT practice | lexora |
|---|---|
| hidden test set | **already** — splits by source lineage, held-out verdicts, `REQ-EXP-002` fails the run if a lineage straddles splits |
| no extrapolation to held-out | **already** — §8 honesty constraints |
| reproducible artifact per number | **already** — frozen manifest hash, `env.json`, N≥3 with variance, revision IDs, AC-G-5 |
| **external dataset** | **missing** — the corpus is this project's own selection |
| **Pareto reporting** | **missing** — size is primary, time secondary, never a frontier |

So the honest summary is that lexora's benchmark discipline is ahead of the fleet it shares an owner
with, and the two gaps are the reporting shape and the absence of an outside dataset.

## 1. OpenZL as a baseline — the missing control

`facebook/openzl` is BSD, in production at Meta, and **format-aware without a canonicaliser**: it
builds a specialised compressor from a description of the data's structure, and ships one universal
decompressor.

Every frozen baseline in `BENCHMARK_PROTOCOL.md` §3 is a *generic* codec — zstd-19, brotli-11,
xz-9e, PPMd. LEXORA's claim is that **conservative canonicalisation plus compression beats a generic
codec**. A format-aware *generic* competitor is the control that claim has never faced:

- If LEXORA beats OpenZL by a wide margin, the canonicaliser is doing work no structural compressor
  can do.
- If LEXORA only ties it, the value is in the container and the byte-exactness guarantee, not in the
  canonicalisation — which is a different product claim.

**Proposed:** add OpenZL to §3 as a *candidate* baseline, not yet measured, with its version pinned
per ADR-0002/0003 and its licence recorded in `DEPENDENCY_LICENCE_REVIEW.md`. It is measurement-only,
so BSD is sufficient; it is not linked.

## 2. Pareto reporting

§5 makes size primary and time secondary. The AIT challenge ranked 117 compressors on a **Pareto
frontier** and concluded that "no single compressor dominates across all criteria" — a finding that
is invisible in a size-only table.

**Proposed:** a Pareto section in the report template: for each system, the (total stored size,
median encode time) pair, and the frontier drawn through them. A verdict that cites a size must
still cite the time at which it was obtained, and the frontier makes that unavoidable.

This is cheap — the harness already records both numbers — and it changes what a result *means*
rather than what it measures.

## 3. An external dataset

§1 requires ≥1 GiB of this project's own selection with documented rights, and the corpus is not yet
assembled (OQ-8). An **external** validation set answers a different question: does the canonicaliser
generalise beyond the text this project chose?

**Proposed:** `enwik8` (the first 10^8 bytes of the 2006 English Wikipedia dump, CC-BY-SA) as an
**external validation set**, never in the training split, recorded in the manifest with its lineage
and rights note.

Two things make it worth its 100 MB:

1. It is the dataset behind Matt Mahoney's Large Text Compression Benchmark, which lists enwik8 and
   enwik9 sizes for hundreds of compressors — so a lexora number on enwik8 has an **external
   reference table** immediately, without running anyone else's tool.
2. It is text nobody here selected, which is precisely the property every single-fixture mistake in
   the fleet this week lacked.

Rights: Wikipedia text is CC-BY-SA; the derived-statistic publication the protocol requires is
permitted, and the excerpt-publication column in `CORPUS_POLICY.md` applies.

## 4. Column encodings as canonicalisation rules — a gap in the rule table

`CORPUS_POLICY.md` lists "numeric/record-like tables" as a required corpus category, and the rule
table in `CANONICALIZATION.md` has **no rule that touches numbers** — it trims whitespace and
normalises line endings, and that is the conservative set.

The ClickHouse article gives the taxonomy for what is missing: a column-aware encoding — dictionary,
run-length, delta, delta-of-delta, Gorilla, frame-of-reference — stacked *under* a general-purpose
codec, with the observation that "encodings know patterns codecs cannot see, and codecs catch entropy
encodings leave behind".

**Proposed, not adopted:** a candidate rule family for TSV/CSV-shaped text that rewrites a numeric
column into deltas or a frame-of-reference before the codec sees it. It is attractive and it is also
the first rule that would stop being *conservative* — it must be byte-exactly invertible, versioned,
and gated by the same golden vectors as the existing nine. It belongs in the rule table only after a
measured win on the numeric corpus category, and that category does not exist yet.

## 5. MinerU: rejected on licence, 2026-11-18

MinerU (`opendatalab/MinerU`) was the other candidate for scanned, layout-heavy PDFs. Its licence is
**Apache-2.0 plus additional terms**, read in full:

- a separate commercial licence is required above **100 million MAU or USD 20 million monthly
  revenue** — neither applies here, so **no fee is due**;
- online services built on it must **attribute** it;
- failing that attribution **terminates the licence automatically**.

So the cost is not money, it is legal surface: a licence with thresholds and a tripwire, which
`DEPENDENCY_LICENCE_REVIEW.md` has no category for and which buys nothing that docling — plain MIT —
does not already do for text. Rejected.

**docling's weight, since that was the other objection:** its core dependencies are pydantic,
docling-core, pydantic-settings, filetype, requests, certifi, pluggy, tqdm and langcodes. **No
torch, no model weights.** Layout analysis and OCR are optional extras, which is the same shape as
this project's own GUI decision (ADR-0008 decision 1: *"core install stays Qt-free"*).

**Proposed shape:** `lexora[pdf]` as an opt-in extra. The base install is `zstandard` alone and stays
that way. Not added to `pyproject.toml` yet — under AC-G-1 a dependency should arrive with the code
that uses it, not before.

## 6. Not applicable here

- **lzbench's speed tiers** — lexora compresses with zstd, which is already in the medium tier; the
  positioning question belongs to the engine, not this project.
- **PeaZip's maximum-compression numbers, SPEC 801.xz_s** — engine-side references.
- **Carpentieri, "Data Compression with a Time Limit"** — assigning files to compressors under a
  time budget. Lexora's `batch` verb is the natural home for that one day, but it is a scheduling
  feature with no consumer yet, and the paper's experiments are on images.
