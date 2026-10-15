# LEXORA Quality Plan

> **Status:** Draft (processes defined; quality metrics currently unmeasurable — no code, verified 2026-10-15)
> **Owner:** Documentation architect (delegated)
> **Related:** [TEST_STRATEGY.md](TEST_STRATEGY.md) · [ACCEPTANCE_CRITERIA.md](ACCEPTANCE_CRITERIA.md) · [BENCHMARK_PROTOCOL.md](BENCHMARK_PROTOCOL.md) · [DECISIONS.md](DECISIONS.md)

## Purpose & scope

Define quality objectives, measurable indicators, gates, roles, and defect handling for LEXORA. Scope: correctness (losslessness), data-quality (cleaning), performance/memory, documentation integrity, security posture.

## Quality objectives → indicators

| Objective | Indicator | Target | Measured by | Current value |
|---|---|---|---|---|
| Byte-exact recovery | Round-trip failure count | **0** (hard) | Property/fuzz layers | Not yet measured (no code) |
| Cleaning safety | ADR-0004 error rate (point / bootstrap UB) | ≤1% / ≤2% | Sample review + invariant checks | Not yet measured |
| Compression merit | Corpus total-size reduction vs best frozen baseline | Pass ≥10%, Partial ≥3% | Benchmark harness | No validated results |
| Memory discipline | Peak RSS on reference machine | ≤ RESOURCE_LIMITS numbers | Perf layer runs | Not yet measured |
| Determinism | Re-run output hash equality | 100% | Golden vectors | N/A pre-code |
| Doc integrity | Broken internal links | 0 | `scripts/linkcheck.py` | 0 ✅ (2026-10-15) |
| Honesty of claims | Fabricated-status findings in audit | 0 | Session checklist (§9 master prompt) | 0 known ✅ |

## Gates

1. **Commit gate:** link checker green; docs updated with code changes (traceability rule).
2. **Phase-exit gate:** every AC-P#-* criterion met with evidence (see ACCEPTANCE_CRITERIA.md).
3. **Release gate:** all mandatory REQs Verified; fuzz campaign complete; CHANGELOG cut; no Proposed formats shipped as stable.

## Defect handling

- Severity S1 = lossless-invariant violation or silent data corruption ⇒ blocks everything until fixed; root cause added as regression test *and* new golden vector.
- S2 = wrong benchmark methodology/result reproducibility ⇒ freeze affected claims in BENCHMARK_RESULTS.md until re-run.
- S3/S4 normal backlog via issue templates (Batch E).
- Every S1/S2 gets a post-fix entry in SESSION_LOG.md; if it changes semantics, an ADR.

## Reviews

- Format/spec changes: two-reviewer rule (author cannot approve); recorded in PR or DECISIONS.md when no PR system exists.
- ADR acceptance basis is always written down (owner reply text or delegation directive) — see delegation note pattern established 2026-10-15.

## Continuous improvement

Each benchmark revision includes ablation review (REQ-EXP-003): features that no longer pay their cost are retired candidates, documented in COST_MODEL retirement log. Quality plan itself amended via this doc's changelog line in CHANGELOG.md when targets change.
