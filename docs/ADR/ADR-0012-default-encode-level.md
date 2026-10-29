# ADR-0012: Default zstd level = 9

> **Status:** **Accepted 2026-10-29** under owner delegation — asked which level was "better practically", the owner left the choice to this record rather than picking (same delegation pattern as ADR-0007 and ADR-0010).
> **Date:** 2026-10-29
> **Deciders:** Owner Dr Sohil Momin (delegated to this record)
> **Related:** [PERFORMANCE_BUDGET.md](../PERFORMANCE_BUDGET.md) (the sweep table + throughput rows) · `benchmarks/results-level-sweep.json` · [COST_MODEL.md](../COST_MODEL.md) (size merit is governed by ADR-0001, not by this) · [ADR-0008](ADR-0008-gui-toolkit-architecture.md) (GUI settings) · [CLI_REFERENCE.md](../CLI_REFERENCE.md)

## Context / Problem

Session 45 measured encode throughput for the first time and found the project's only measured budget miss: **0.30–0.71 MiB/s at zstd-19** against a soft target of ≥2 MB/s. Session 46 priced the curve on 8 MiB of real Gutenberg prose so the choice would be a decision rather than an argument:

| level | speed | ratio | peak RSS |
|---|---|---|---|
| 3 | 12.8 MiB/s | 0.3393 | 44.5 MiB |
| 6 | 9.4 MiB/s | 0.3146 | 45.6 MiB |
| **9** | **6.2 MiB/s** | **0.3043** | **51.5 MiB** |
| 15 | 1.1 MiB/s | 0.2873 | 102.9 MiB |
| 19 (was default) | 0.7 MiB/s | 0.2678 | 120.1 MiB |

The same session also surfaced an inconsistency that made this urgent rather than theoretical: **the three surfaces disagreed about the default**. The CLI and library defaulted to 19, the GUI settings default was hardcoded to 3, and a comment claimed that value "matches the CLI `pack --level` default" — which it did not. Two surfaces of the same application were producing different archives from the same input.

## Decision drivers

- **Meet the budget.** The soft ≥2 MB/s target exists to keep the tool usable on a 4 GiB laptop; 19 misses it by 3–7×.
- **Keep the size story.** This is a compression tool; a level that halves speed for 3 % of bytes is a bad trade.
- **One source of truth.** Any default must be the same number in the library, the CLI and the GUI.
- **Reversibility.** The level is a per-invocation choice; nothing in the format depends on it.

## Options considered

- **A. Keep 19, revise the soft target downward.** Honest about archival priorities, but it writes off the ≥2 MB/s goal instead of meeting it, and leaves the CLI/GUI disagreement to be fixed separately.
- **B. Default to 6** (9.4 MiB/s, 0.3146). Meets the target with 1.5× the speed of 9 at +3.4 % bytes versus 9.
- **C. Default to 9** (6.2 MiB/s, 0.3043) — **chosen.**
- **D. Keep 19 and document a fast preset.** No behaviour change, but a documented preset nobody passes is not a default.

## Decision

**`lexora.DEFAULT_LEVEL = 9`**, and every surface reads it:

- library: `container.pack()` / `pack_stream()` default to `DEFAULT_LEVEL`;
- CLI: `zround`, `pipe`, `pack` and `batch` default to `DEFAULT_LEVEL`;
- GUI: `gui.service.DEFAULT_SETTINGS["level"]` is `DEFAULT_LEVEL` (the hardcoded 3 and its false comment are gone).

Level 9 sits at the knee of the curve: it clears the ≥2 MB/s target with ~3× headroom, costs 13.6 % more bytes than 19, and the returns flatten beyond it (12/15/19 buy 3–6 % more bytes for a 3–9× slowdown). Level 19 remains available explicitly — `--level 19` — for archival work where size is the only metric.

## Consequences & trade-offs

**Positive.** The one measured budget miss becomes a pass (6.2 MiB/s ≥ 2 MB/s). Archives produced by default are ~13.6 % larger than at 19 and arrive ~9× faster. The CLI/GUI inconsistency is closed by construction, with a test that fails if any surface drifts.

**Negative / accepted risks.** Existing users' default output changes size — every archive packed from now on differs from one packed before, which matters for reproducibility of *artifacts* (not of the format: the level is not recorded as semantics, and old archives decode unchanged). Benchmarks published as R1/R2 used zstd-19 as the *baseline tool* and are unaffected; future LEXORA revisions must state the level they used, which `benchmarks/env.json` and the probe already record. Peak RSS at 9 is 51.5 MiB versus 120.1 MiB at 19 — an improvement, but the encode budget row's 512 MiB was never the binding constraint.

**Not decided here:** the ADR-0001 compression-merit gate. This ADR chooses a *default speed/size operating point*; it makes no claim about whether LEXORA beats any baseline on size.

## Impact analysis

| Dimension | Impact |
|---|---|
| Security | None |
| Performance / memory | ~9× faster default encode; peak RSS ~69 MiB lower at 8 MiB input |
| Compatibility (format/spec) | None — level is not part of the `.lxz` byte layout or semantics; archives remain readable and verifiable. Artifact bytes change for new packs |

## Implementation & test implications

Landed with this ADR: `DEFAULT_LEVEL` in `lexora/__init__.py` with the sweep summarised in a comment; library, CLI and GUI wired to it; the stale `level: 3` setting and its comment removed; `tests/test_level_default.py` asserting that all four CLI subcommands, both library entry points and the GUI settings agree with the constant, and that a default-level `pack` equals an explicit `level=DEFAULT_LEVEL` pack. PERFORMANCE_BUDGET's encode row and CLI_REFERENCE's `--level` defaults were updated in the same change.
