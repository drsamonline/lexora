# ADR-0026: Cost-based selection is a whole-archive trial behind a flag — not a per-block search

- **Status:** **Proposed** — the owner's call. Nothing here is implemented, and by this project's
  own rule an implementation does not start from a Proposed ADR.
- **Date:** 2026-11-23
- **Related:** [COST_MODEL](../COST_MODEL.md) rule 2 · [ADR-0015](ADR-0015-codec-policy.md) (the
  preset it would replace) · [ADR-0007](ADR-0007-container-v0-freeze.md) (one `codec_id` per
  archive) · [ADR-0012](ADR-0012-default-encode-level.md) · REQ-CMP-003
- **Evidence:** `benchmarks/selector_probe.py` → `benchmarks/results-selector-probe.json`

## Context

REQ-CMP-003 says *"encoding selects codecs/candidates by cost; selection is reproducible given
pinned settings"*. `COST_MODEL.md` rule 2 says how: per block, the argmin of total serialized bytes
over the enabled candidates, ties broken by a fixed priority order. Neither is implemented. v0 takes
a pinned preset ([ADR-0015](ADR-0015-codec-policy.md)): `zstd` at level 9 by default, CHCE
(ziptastic) as the max-ratio preset, and the level is the only knob.

Two things changed on 2026-11-23 that make this decidable now rather than later:

1. **"Total serialized bytes" became computable.** `benchmarks/cost_audit.py` (REQ-CMP-004)
   decomposes an `.lxz` into the model's terms and closes exactly against the file, so a candidate's
   cost is a number this project can obtain rather than estimate.
2. **The container's constraint was re-read.** `.lxz` v0 carries **one** `codec_id` for the whole
   archive ([ADR-0007](ADR-0007-container-v0-freeze.md), frozen). Per-*block* selection is
   therefore not a policy change; it is a format revision.

## What the choice is worth, measured

`benchmarks/selector_probe.py` on `tests/vectors/real_text/gutenberg_slices.txt` (720,983 B, 3
reps): the only comparison v0 can make without an external binary is level against level.

| Candidate | Stored | Ratio | Median encode | Throughput |
|---|---|---|---|---|
| zstd level 9 (shipped default) | 271,004 B | 0.3759 | 73 ms | 9.9 MiB/s |
| zstd level 19 | 253,155 B | 0.3511 | 438 ms | 1.6 MiB/s |

**A selector would pick level 19: 6.59 % smaller for 6.0× the time.** That is the entire value
available from cost-based selection on the shipped codec — not a rounding error, and not free.

**The candidate it cannot compare is the one that matters most.** ziptastic (CHCE) is the max-ratio
preset and was measured 18.5 % under `xz -9` at R6 scale, but the binary is absent from this
container, so the probe records it as *not measured* rather than estimating. Any decision that
assumes the CHCE comparison is available is assuming something this evidence does not support.

## Options

**A. Keep the preset (status quo).** Reproducible, fast, and honest — but REQ-CMP-003 stays unmet,
and a user who wants the 6.59 % has to know to pass `--level 19`.

**B. Whole-archive trial selection, opt-in.** Encode the archive once per enabled candidate, keep
the smallest **total serialized size** (payload + index + header + trailer, i.e. the auditor's
number, not the payload alone), and record every candidate's cost in a report. Opt-in via
`--select`. The chosen codec still goes in the single `codec_id` field, so **the format does not
change**.

**C. Per-block selection.** The design `COST_MODEL.md` rule 2 literally describes, and the best
ratio of the three. It needs a codec id per block, which is a v1 format — and this project's rule is
*no format bytes before the gate*, with gate G2 still open.

**D. Sampled prediction.** Encode a sample, extrapolate, pick. Fast, and the wrong answer for
REQ-CMP-003: the requirement demands reproducibility "given pinned settings", and a choice that
depends on which bytes the sampler happened to take is reproducible only by accident.

## Decision (proposed)

**Adopt B**, as an opt-in flag, with these properties pinned:

1. **Cost is the auditor's number**, not the payload's: a candidate that shrinks payload by 200
   bytes and grows the index by 400 has not won. This is the one place the REQ-CMP-004 work pays
   off directly.
2. **Ties break by fixed priority** — `zstd-raw` before `ziptastic`, lower level before higher — so
   an equal-size outcome is decided by the candidate list's order, not by dictionary iteration.
3. **The losers are recorded**, with their totals, in the same report the audit already produces.
   A selection nobody can re-derive is a coin toss with a log line.
4. **The default does not move.** No `--select` means today's bytes, exactly (ADR-0015 stands). A
   default that silently costs 6× the time would be a regression dressed as a feature.
5. **Unmeasurable candidates are refused, not skipped.** If `--select` is asked to consider
   ziptastic and the binary is absent, that is an error naming the binary — silently choosing from a
   smaller candidate set would report a selection that was never made.

## Why not C now

C is the better design and this ADR does not dispute it. It is also a format revision: `.lxz` v0's
header has one `codec_id`, frozen by [ADR-0007](ADR-0007-container-v0-freeze.md), and the standing
rule is that a layout is not revised before the benchmark that judges it. C belongs to v1, after
gate G2, and it should be judged on the R5-scale numbers this project does not yet have.

## Consequences

- (+) REQ-CMP-003 becomes implementable without touching a stored byte of the format, and the
  selector's decisions are auditable.
- (+) The 6.59 %/6.0× trade becomes a user's choice instead of a hidden preset, which is what
  "cost-based" should mean.
- (−) Encoding with `--select` costs the sum of all candidates' time — 6× in the measured pair, more
  with CHCE.
- (−) It does not close REQ-CMP-003 on its own. The requirement is met when the flag exists **and**
  is tested against the auditor; until then the row stays Open with this ADR named as its design.
- (−) It buys nothing on the default path, which is where most archives will be written. The honest
  framing: this makes the *option* cost-based, not the product.

## What this ADR does not decide

- **Whether to do it at all.** The measured 6.59 % may not be worth a second encode pass to this
  project, and the owner may reasonably say the preset is the right answer for v0. That is the
  question this ADR puts in front of them, with the numbers attached.
- **The tie-break list's final order** — `COST_MODEL.md` still lists that as open decision 3. This
  ADR proposes an order; it does not claim it is the only defensible one.
- **Any throughput claim.** The timings are from a shared container and are indicative; the sizes
  are exact.
