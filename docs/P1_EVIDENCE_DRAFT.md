# P1 Closure Evidence Draft (NOT published — awaiting owner verdict)

> **Status:** DRAFT for owner review (2026-10-17, Session 37; **item 2 replaced with live Core-path measurements 2026-10-28, Session 38**). This page exists to close the two evidence gaps blocking PHASES P1 → Complete. It is deliberately separate from `BENCHMARK_RESULTS.md`: per QUALITY_PLAN, nothing enters the published register without owner sign-off, and no ADR-0001 verdict may be issued while the corpus is below BENCHMARK_PROTOCOL scope.
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

## Evidence item 2 — Core-path peak RSS vs PERFORMANCE_BUDGET — MEASURED ✓

**Updated 2026-10-28 (Session 39).** The Session-37 version of this section could only offer *baseline-tool* numbers (zstd19/xz9 from `benchmarks/results-r3.json`) and listed "a dedicated streaming-Core RSS measurement is not yet automated" as caveat 1. That gap is now closed: `benchmarks/rss_probe.py` measures the real CLI (`lexora pack` / `lexora unpack`) as a fresh child process and reads peak RSS from `os.wait4()`'s `ru_maxrss` — the kernel high-water mark, not a sampling estimate. Artifact: `benchmarks/results-rss-core.json`.

Method: deterministic seeded English-like input (synthetic — reproducible on any box, needs no corpus); one run per size; zstd level 19 (CLI default), 8 MiB blocks. **Synthetic input carries no corpus tier and supports no ADR-0001 verdict.**

| Input | `pack` streaming (default) | `pack --no-stream` (pre-Session-39) | `unpack` | Encode budget | Decode budget |
|---|---|---|---|---|---|
| 1 MiB | 45.0 MiB | 43.5 MiB | 28.3 MiB | 512 MiB | 256 MiB |
| 4 MiB | 83.9 MiB | 81.0 MiB | 38.4 MiB | PASS | PASS |
| 16 MiB | 118.6 MiB | 156.4 MiB | 70.3 MiB | PASS | PASS |
| 32 MiB | 126.1 MiB | 196.9 MiB | 117.3 MiB | PASS | PASS |
| 64 MiB | **126.2 MiB** | not run (projected ~320 MiB) | 188.6 MiB | PASS | PASS |

**What the numbers say**

1. **The buffered encoder was a genuine budget risk, and it is now fixed.** `pack()` needs the whole payload in memory and slices it into blocks (a second full copy), so its peak grew ~4.8 MiB per MiB of input; the linear fit put the 512 MiB encode budget breach at a **~95 MiB document**. Session 38 added `container.pack_stream()` (one block resident at a time, header backfilled, byte-identical output) and made it the CLI default. Streaming peak **plateaus at ~126 MiB from one full block upward** (32 MiB and 64 MiB differ by 0.1 MiB), i.e. the encode budget no longer depends on document size.
2. **Wall-clock is inconclusive and is not claimed.** This 2-CPU container was noisy across passes: an early pass had streaming faster at 16 MiB (16.8 s vs 37.5 s buffered), the final pass had it slower (42.0 s vs 28.3 s buffered). Both paths compress the same blocks at the same level, so the expected difference is I/O ordering, not CPU; a throughput claim needs the REF-4G-class machine and repeated runs under BENCHMARK_PROTOCOL §6.3. **Memory, not speed, is what this evidence establishes.**
3. **Decode was buffered when this item was first measured; that is fixed (Session 41).** The original reading held the whole archive plus the whole output (~2.8 MiB peak per MiB; 116.1 MiB at a 32 MiB archive, 188.6 MiB at 64 MiB). `unpack` now streams block-by-block and holds a flat **~34 MiB** (34.8 MiB at 32 MiB, 34.1 MiB at 64 MiB), so the 256 MiB decode budget no longer depends on archive size. Rows in `benchmarks/results-rss-core.json` carry `decode_path` (`buffered` / `stream`) so the two readers are never confused.

**Caveats that must survive into any published form**

1. **Reference-machine deviation:** measured in a 2 GiB cloud container, not the proposed REF-4G profile (still unconfirmed, OQ-7 related). Deviation recorded here per PERFORMANCE_BUDGET compliance §1. Peak-RSS numbers are machine-robust; wall-clock numbers are not.
2. **Synthetic input, one rep per size.** Compression *ratios* from this probe mean nothing (synthetic text is unrealistically compressible). Peak RSS is the quantity of interest and is stable to a few MiB across the repeats that were run in earlier passes.
3. **Corpus scope unchanged:** no ADR-0001 verdict, no publication into BENCHMARK_RESULTS.md without owner sign-off.

**Verdict candidate:** encode peak RSS — **PASS**, on our own Core path, with the streaming default; decode — PASS at measured sizes with a documented scaling limit.

## What closing P1 would then look like

- PHASES.md P1 status → *Complete (evidence: this page + commit hashes)*.
- TASK_BREAKDOWN P1-T1 → Landed; P1-T6 note updated to point here.
- STATUS/PROGRESS posture lines adjusted (Phase 1 closed; remaining open items = benchmark publication policy + owner review backlog only).
- Corpus growth toward ≥1 GiB stays an OPEN track for a future *published* revision R3+ (OQ-8) — independent of P1 closure.
