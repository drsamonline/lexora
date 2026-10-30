# LEXORA Phases

> **Status:** Living plan. **P0 complete · P1 complete (owner-accepted) · P2 in progress · P3–P5 not started**
> **Owner:** Documentation architect (delegated)
> **Last verified:** 2026-10-30 — P1 complete and tested (510 tests); P2 harness operational and the corpus at 1.05 GiB; the protocol-scope run and verdict generator are what remain
> **Related:** [ROADMAP.md](ROADMAP.md) · [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) · [SPECIFICATION.md](SPECIFICATION.md) · [ACCEPTANCE_CRITERIA.md](ACCEPTANCE_CRITERIA.md)

## Purpose

One entry per executable phase with prerequisites, scope, expected artifacts, exit criteria, evidence, risks, and rollback. A phase is **Complete** only when every exit criterion has recorded evidence.

## Scope

Phases P0–P7 map to milestones M0–M7 in [ROADMAP.md](ROADMAP.md). Statuses follow the legend there.

---

## P0 — Foundations & freeze gates — **In progress**

- **Objective:** Documentation system complete enough to build against; decisions frozen where they block code.
- **Prerequisites:** None.
- **Done so far (evidence):** Batch A governance docs (`07c1564`), Batch B architecture/spec drafts + ADRs (`91cfbb6`, `5001ab3`), ADR-0001…0004 Accepted via delegation (this branch, commit `86e6b55`). Link checker green.
- **In scope now:** Batch C (this file set), Batch D, Batch E; canonicalization rule-table freeze + golden vectors; spec approval pass.
- **Out of scope:** Any compression/ingestion code.
- **Exit criteria:**
  1. Batches A–E committed, link-clean. *(A, B done; C in progress)*
  2. OQ-5…OQ-10 answered by owner or delegated decision records created. *(Open)*
  3. CANONICALIZATION rule table frozen with version ID and golden-vector test plan. *(Open)*
  4. SPECIFICATION promoted from draft to approved via ADR. *(Open)*
- **Risks:** Delegated ADR acceptance may be overturned by owner → superseding ADRs absorb changes; docs drift from future code → traceability matrix enforces updates.
- **Rollback:** Docs are additive; revert commits.

## P1 — Core Zstd pipeline (TXT only) — **Complete (owner-accepted 2026-10-17, Session 38)**

- **Closure basis:** owner directive "accept and next phase" (in-chat, Session 38). Both evidence gaps closed via [P1_EVIDENCE_DRAFT.md](P1_EVIDENCE_DRAFT.md): item 1 editable install VERIFIED live; item 2 peak RSS 84 MiB vs 512 MiB encode budget = PASS with three recorded caveats (baseline-tool mapping, non-REF-4G machine, T1 smoke-scope corpus ⇒ no ADR-0001 verdict from these numbers). Exit criteria met: round-trip equality + invariant fuzz (P1-T2), `.lxz` v0 frozen via ADR-0007 (P1-T3), CLI pack/unpack tested (P1-T5), README quick-start matches real commands (CLI_REFERENCE.md). Caveat: the RSS figure is zstd-19 baseline-tool memory mapped to the Core encode row — accepted as sufficient under owner delegation; a stricter Core-path streaming measurement remains possible post-P2 if desired.
- **Objective:** `lxz pack/unpack` for TXT: ingest → canonicalize → blocked Zstd → `.lxz` v0; byte-exact decode of canonical bytes.
- **Prerequisites:** P0 exit; **OQ-7** (Python version); offline-installable `zstandard` confirmed.
- **Expected changes:** New package (e.g., `lexora/`), CLI entry points, unit + property tests, format test vectors.
- **Exit criteria:** Round-trip equality on smoke corpus; invariant `decode(encode(C)) == C` fuzz-tested at block level; peak RSS documented under budget; README quick-start matches real commands.
- **Evidence:** Test run logs committed; CI (once OQ-6 enables it) or local recorded output.
- **Risks:** Format churn late → freeze `.lxz` v0 layout *before* writing encoder (FORMAT_LXZ.md is PROPOSED until then).
- **Rollback/fallback:** Keep canonicalizer independent of container so a format revision doesn't invalidate cleaning outputs.

## P2 — Benchmark harness & first numbers — **In progress**

- **Opening state:** harness mechanics already landed in P1 (env capture, manifest/verify, split audit, cost accounting, N-repeat runner, peak-RSS sampling — `benchmarks/harness.py`); smoke-scope artifacts R0/R3 exist. Load-bearing gap: **OQ-8 corpus ≥1 GiB** (en/hi/gu per BENCHMARK_PROTOCOL) and the ADR-0001 verdict run at protocol scope. Container network egress to Gutenberg mirrors is unverified (S37 note) — first task is a live fetch probe; if blocked, document precisely which step fails.
- **Objective:** Reproducible measurement of Core vs frozen baselines.
- **Prerequisites:** P1; **OQ-8** (corpus rights/assembly); external tools for Brotli/XZ/PPMd baselines installed per BUILD_GUIDE.
- **Exit criteria:** Frozen manifest + config hashes; 70/10/20 lineage split audited; per-category and corpus totals reported; verdict Pass/Partial/Fail per ADR-0001 written to BENCHMARK_RESULTS.md (replacing "No validated benchmark results yet").
- **Risks:** Corpus licensing/privacy; baseline tool version drift → pin versions in manifest hash.
- **Rollback:** Results are additive; harness rerunnable.

## P3 — PDF ingestion & optional OCR — **Not started**

- **Prerequisites:** P1; **OQ-10** (Tesseract/traineddata availability).
- **Scope:** PDF text-layer extraction; scanned-page OCR path; page ordering; header/footer dedup (CAN-R08); confidence-gated correction (CAN-R09).
- **Exit criteria:** Golden documents reproduce canonical bytes; ADR-0004 sample review executed ≤ thresholds; memory-bounded streaming verified on largest test PDF.
- **Risks:** OCR quality variance across scripts (hi/gu); dedup false positives destroying content → conservative defaults + invariant checks.
- **Fallback:** OCR stays optional flag; TXT/PDF-text-layer path unaffected.

## P4 — Optional compression candidates — **Not started**

- **Prerequisites:** P2 harness operational.
- **Scope:** Per-candidate sub-phases: dictionary training, Re-Pair, bounded token PPM, numeric/record coding, template+residual. Each behind cost-driven selection; each requires its own promotion evidence (ADR-0001) before becoming selectable.
- **Exit criteria per candidate:** ≥10% category win on validation, reproduced held-out; serialized cost fully counted; ablation table updated; losers retired with notes.
- **Risks:** Overfitting to corpus → lineage-split audit; complexity creep on 4 GiB target → RAM profile required per candidate.
- **Rollback:** Candidates are opt-in codec IDs; removing one never breaks decoding of archives that don't use it.

## P5 — `.lxdb` repository layer — **Not started**

- **Prerequisites:** P1 stable; FORMAT_LXDB promoted from proposal via ADR after byte layout review.
- **Scope:** Multi-document store, index/search, incremental update, recovery flow.
- **Exit criteria:** Recovery runbook steps proven against simulated corruption fixtures; search correctness tests; size overhead measured.

## P6 — Security hardening & encryption profile — **Not started**

- **Scope:** Decoder limits enforcement, fuzz campaign, threat-model mitigation verification; AEAD encryption only if owner confirms scope (ENCRYPTION_PROFILE.md is proposed).
- **Exit criteria:** Fuzz runs with recorded crash triage; no open high findings in THREAT_MODEL mitigations table; security docs free of unverified claims.

## P7 — First release — **Not started**

- **Prerequisites:** OQ-5 license, OQ-6 repo/remote, OQ-9 versioning adoption; CI workflows real.
- **Exit criteria:** Tagged release, artifacts reproducible, CHANGELOG cut, migration guide status updated, earned badges only.
