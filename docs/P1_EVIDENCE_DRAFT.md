# P1 Closure Evidence Draft (NOT published — awaiting owner verdict)

> **Status:** DRAFT for owner review (2026-10-17, Session 37). This page exists to close the two evidence gaps blocking PHASES P1 → Complete. It is deliberately separate from `BENCHMARK_RESULTS.md`: per QUALITY_PLAN, nothing enters the published register without owner sign-off, and no ADR-0001 verdict may be issued while the corpus is below BENCHMARK_PROTOCOL scope.
> **Related:** [PHASES.md](PHASES.md) · [PERFORMANCE_BUDGET.md](PERFORMANCE_BUDGET.md) · [BENCHMARK_RESULTS.md](BENCHMARK_RESULTS.md) · [TASK_BREAKDOWN.md](TASK_BREAKDOWN.md)

## Evidence item 1 — Editable install (`pip install -e .`) — VERIFIED ✓

Captured live in-container on 2026-10-17:

```
$ python3 -m pip install -e .          # succeeds (editable, src-layout; ADR-0005 pins 3.12)
$ python3 -c "import lexora; print(lexora.__file__)"
/workspace/src/lexora/__init__.py      # resolves to the working tree, not site-packages copy
$ lexora --help                        # rc 0
$ printf 'line1\r\nline2  spaced\ttab\r\n' > t.txt
$ lexora canon --in t.txt --out o.txt  # rc 0, stderr: "canon: 26 -> 24 bytes (rules CAN-R01,R02,R05; lexcAN-0.1)"
$ od -c o.txt | head -1
0000000   l   i   n   e   1  \n   l   i   n   e   2     s   p   a ...    # CRLF->LF applied (CAN-R02); interior spaces/tabs preserved (CAN-R03 NOT in v0 scope)
$ lexora-gui --help                    # rc 0 on bare headless box (regression-tested)
```

**Verdict candidate:** P1-T1 acceptance criterion ("`pip install -e .` works") — MET. TASK_BREAKDOWN P1-T1 can move from *Started* to *Landed*.

## Evidence item 2 — Peak RSS vs PERFORMANCE_BUDGET — PASS with caveats ⚠

Raw material: `benchmarks/results-r3.json` (harness artifact dated 2026-10-16; method: forked child runs the identical encode call, parent samples `/proc/<pid>/status` VmHWM until exit; measured once per system on the largest manifest file, `gutenberg-1184.txt`, 2,787,124 bytes; corpus tier **T1-gutenberg-p0**, ~7.1 MB total).

| System | Measured peak RSS | Budget row it maps to | Budget | Result |
|---|---|---|---|---|
| zstd19 (baseline) | 85,956 KiB ≈ **84 MiB** | "Encode block … ≤ 512 MiB" | 512 MiB | **PASS** (~16% of budget) |
| xz9 (baseline) | 35,348 KiB ≈ **35 MiB** | tool-dependent, recorded separately | — | informational |

Caveats that must survive into any published form:

1. **These are BASELINE-tool numbers, not LEXORA Core numbers.** The budget table's rows bind our own pipeline; the harness measures external reference systems. Closest Core-path analogue available today: the full pytest suite process peaks well under the same envelopes, but a dedicated streaming-Core RSS measurement is not yet automated. Owner options: (a) accept baseline-vs-budget as sufficient P1 evidence (Core uses the same zstandard engine at lower levels ⇒ strictly less memory than level-19), or (b) require a Core-specific RSS run first.
2. **Reference machine deviation:** measured in a cloud container, not the proposed REF-4G profile (REF-4G itself still awaits owner confirmation, OQ-7-related). Per PERFORMANCE_BUDGET compliance procedure §1, deviation is allowed when recorded — this document is that record.
3. **Corpus scope:** results carry the mandatory T1-gutenberg-p0 tier label; they do NOT qualify as protocol-scope measurements and still support **no ADR-0001 verdict** (same argument as R1/R2 notes).

**Verdict candidate:** peak-RSS-documented-under-budget — PASS on the data available, subject to caveat 1 choice by owner.

## What closing P1 would then look like

- PHASES.md P1 status → *Complete (evidence: this page + commit hashes)*.
- TASK_BREAKDOWN P1-T1 → Landed; P1-T6 note updated to point here.
- STATUS/PROGRESS posture lines adjusted (Phase 1 closed; remaining open items = benchmark publication policy + owner review backlog only).
- Corpus growth toward ≥1 GiB stays an OPEN track for a future *published* revision R3+ (OQ-8) — independent of P1 closure.
