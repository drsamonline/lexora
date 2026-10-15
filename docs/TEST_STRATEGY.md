# LEXORA Test Strategy

> **Status:** Draft (strategy defined ahead of implementation; **no test tooling exists in the repository yet** — verified 2026-10-15)
> **Owner:** Documentation architect (delegated)
> **Related:** [QUALITY_PLAN.md](QUALITY_PLAN.md) · TESTING_GUIDE.md *(Batch E)* · [ACCEPTANCE_CRITERIA.md](ACCEPTANCE_CRITERIA.md) · [IMPLEMENTATION_MATRIX.md](IMPLEMENTATION_MATRIX.md)

## Purpose & scope

Define test layers, their entry points, and which requirements each layer verifies. Commands are listed as *planned* until `pyproject.toml`/`pytest` exist (P1-T1); no fake commands are presented as working.

## Layers

| # | Layer | What it proves | Key reqs | Runs when | Status |
|---|---|---|---|---|---|
| 1 | Unit | Canonicalizer rules byte-exact vs golden vectors; format field codecs; cost accounting math | CAN-002/003/005, FMT-001 | every commit (local now, CI later) | Planned |
| 2 | Integration | Full TXT→canonicalize→pack→unpack→verify on fixture archives incl. provenance round-trip | ING-001/004, CMP-002 | every commit | Planned |
| 3 | Property-based | `decode(encode(C)) == C` for generated canonical byte strings (hypothesis-style): empty, block boundaries ±1, pathological runs, random UTF-8 sequences that survive canonicalization | **CMP-001 (invariant)**, CMP-003 | nightly / pre-release | Planned |
| 4 | Golden-vector corpus | Frozen input→canonical→archive-hash triples per canonicalizer version; any drift fails loudly | CAN-001/004, FMT-001 | every commit | Planned |
| 5 | Corruption/negative | Truncated headers, bit-flips, unknown codec IDs, must-understand flags, oversized declared limits ⇒ refusal with specific error, zero output bytes | CMP-006, FMT-002/003, SEC-004 | every commit | Planned |
| 6 | Fuzzing | Structured archive fuzz (e.g., AFL++/atheris once decoder exists); crash = security bug even if "impossible" | SEC-001 | continuous after P1; campaign before P6/P7 | Planned |
| 7 | Compatibility | Decoder of version N reads archives of all earlier supported versions; test vectors per format revision | FMT-001, COMPAT policy (Batch D) | release gate | Planned |
| 8 | Performance/memory | Peak RSS + wall time on reference machine for encode/decode/benchmark paths vs PERFORMANCE_BUDGET numbers | RES-001, CMP-005 | per phase exit + benchmark revisions | Planned |
| 9 | Cleaning quality | ADR-0004 protocol: seeded stratified sample review, two reviewers, bootstrap bound; automated invariant checks over 100% archived content | CAN-006/007 | P3 exit, each rule-table change | Planned |
| 10 | Recovery | `.lxdb` corruption scenarios per RECOVERY_RUNBOOK (Batch D) fixtures | FMT-004 (later) | P5 exit | Deferred |

## Determinism rules

- All randomized tests use seeds recorded in the test file or CI log.
- Benchmark-adjacent tests pin library versions via manifest hashes (see BENCHMARK_PROTOCOL).
- Time/locale/env-dependent behavior is forbidden in canonicalization outputs; tests assert under varied `TZ`, `LANG`.

## Data & fixtures

- Fixtures live in `tests/fixtures/` (created at P1-T1), never contain personal/clinical data (CORPUS_POLICY applies to test data too).
- hi/gu script fixtures include combining marks, ZWJ/ZWNJ, digits, and rupee-sign cases specifically (REQ-CAN-005).

## Coverage & metrics policy

Coverage measured only after suite exists; target set in QUALITY_PLAN. No coverage badge until a real service publishes it (master-prompt §6).

## Planned tooling (pending OQ-7/OQ-9)

`pytest` (+ property plugin chosen at P1-T1), `atheris` or equivalent Python fuzzer, external baseline CLIs for benchmark harness. Selection rationale will be recorded in an ADR when adopted.

## Entry-point commands (template — NOT yet runnable)

```text
# after P1-T1 creates the package:
python -m pytest tests/            # layers 1,2,4,5
python -m pytest tests/property    # layer 3 (longer)
```

Until then, the only verification command that exists is `python3 scripts/linkcheck.py` (documentation integrity).
