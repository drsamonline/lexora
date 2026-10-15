# LEXORA Troubleshooting Guide

> **Status:** Draft (symptom→cause→action map for the *designed* system; no CLI exists yet, so none of these symptoms can occur today — verified 2026-10-15)
> **Owner:** Documentation architect (delegated)
> **Last verified:** 2026-10-15
> **Related:** [ERROR_HANDLING.md](ERROR_HANDLING.md) · [LOGGING_AND_DIAGNOSTICS.md](LOGGING_AND_DIAGNOSTICS.md) · runbooks/ · [INSTALLATION.md](INSTALLATION.md) · [RESOURCE_LIMITS.md](RESOURCE_LIMITS.md)

## How to use this guide

Match the symptom, follow the action ladder from cheapest check to runbook escalation. Error codes referenced here are the proposed contract in [ERROR_HANDLING.md](ERROR_HANDLING.md); they only become real once implemented. **Never post raw document text** when asking for help — share hashes, codes, and sanitized logs ([PRIVACY_AND_DATA_HANDLING.md](PRIVACY_AND_DATA_HANDLING.md)).

## Installation & environment

| Symptom | Likely causes | Actions |
|---|---|---|
| Package/CLI not found after install | Wrong Python version (OQ-7 unresolved), PATH, venv not activated | Confirm interpreter version vs documented support range; re-run per [INSTALLATION.md](INSTALLATION.md); check `which`/PATH |
| OCR step skipped unexpectedly | Tesseract absent or Hindi/Gujarati traineddata missing (OQ-10) | Verify `tesseract --version` and installed language packs; enable verbose ingest log |
| Works on one machine, OOMs on another | Memory budget (~4 GiB target) exceeded by block/dictionary sizes | Compare against [PERFORMANCE_BUDGET.md](PERFORMANCE_BUDGET.md) envelope; escalate to [runbooks/PERFORMANCE_TRIAGE.md](runbooks/PERFORMANCE_TRIAGE.md) |

## Ingestion & canonicalization

| Symptom | Likely causes | Actions |
|---|---|---|
| Many files quarantined with E-INPUT-ENC-* | Mixed legacy encodings, mojibake sources | Re-detect encoding explicitly per file; fix at source; do NOT force-decode |
| PDF pages report E-INPUT-PDF-001 | Scanned page without text layer and OCR disabled/unavailable | Enable OCR path ([OCR_PIPELINE.md](OCR_PIPELINE.md)) or mark pages intentionally skipped with opt-in flag |
| Cleaning looks "too aggressive" / data seems lost | Expected: canonicalization is lossy-by-design upstream of compression | Check CAN-Rnn rule table + golden vectors; if a rule misfires on your script (Devanagari/Gujarati), file a bug with doc hash + rule id |
| Same input yields different bytes across runs | Violates determinism invariant ⇒ implementation bug | Freeze versions, rerun with DEBUG log, compare hashes per stage; escalate as integrity issue → [runbooks/CORRUPTION_TRIAGE.md](runbooks/CORRUPTION_TRIAGE.md) |

## Compression / decompression

| Symptom | Likely causes | Actions |
|---|---|---|
| Archive refused: bad magic/version (E-FMT-HEAD-*) | Truncated download, wrong extension, newer format version | Re-obtain archive; compare digest vs source-of-truth manifest |
| Dictionary hash mismatch (E-FMT-DICT-001) | Dictionary swapped/renamed silently; ID reuse violation | Restore dictionary matching the recorded hash; never rename-and-reuse IDs |
| Decode aborts mid-way (E-RES-*/expansion cap) | Hostile or pathological archive; limits set too tight | Run [runbooks/CORRUPTION_TRIAGE.md](runbooks/CORRUPTION_TRIAGE.md); treat unknown-source archives as hostile by default |
| Round-trip verify failure at encode time (E-CMP-001) | Codec bug | Stop; preserve repro corpus + logs; file bug; do not ship that archive |
| Compression much worse than expected | Wrong split used for dictionary training; incompressible/random data; candidate selection fell back | Check run manifest (which codec won, which dict); see [runbooks/BENCHMARK_RUNBOOK.md](runbooks/BENCHMARK_RUNBOOK.md) ablation section |

## Benchmarks

| Symptom | Likely causes | Actions |
|---|---|---|
| Results differ between machines/runs | Unpinned baseline versions, thermal/frequency drift, corpus drift | Re-check protocol pins ([BENCHMARK_PROTOCOL.md](BENCHMARK_PROTOCOL.md)); repeat N times, report spread; [runbooks/BENCHMARK_RUNBOOK.md](runbooks/BENCHMARK_RUNBOOK.md) |
| Candidate beats baseline on train split only | Overfitting dictionary to train data | Verify held-out reproduction gate (ADR-0001); protocol requires both |
| Any number appearing outside BENCHMARK_RESULTS.md | Process violation | Numbers are invalid until produced by frozen-protocol runs; correct the record honestly |

## Escalation ladder

1. Re-read the relevant table above; gather: error code, run manifest, hashes, sanitized logs.
2. Pick the matching runbook in [runbooks/](runbooks/).
3. If unresolved or suspected security/integrity: follow root [SECURITY.md](../SECURITY.md) reporting instructions.
4. Record outcome in project docs (SESSION_LOG for maintainer-side issues) — honest closure required.
