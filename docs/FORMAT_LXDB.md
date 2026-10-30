# `.lxdb` Incremental Database Mode

> ## ⚠️ DEFERRED — DIRECTION PROPOSED, NO LAYOUT
> **Status:** Deferred by policy (REQ-FMT-004) for any *byte layout*. The **direction** question is settled in [ADR-0010](ADR/ADR-0010-lxdb-direction.md) (**Accepted 2026-10-29**): a container of `.lxz` members as an interim v0, with a block-pool successor named and its trigger stated. No field widths, magic, ordering or semantics exist below.
> **Owner:** Unassigned
> **Last verified:** 2026-10-29 (gate table re-measured in Session 52)
> **Related:** [FORMAT_LXZ.md](FORMAT_LXZ.md) · [SPECIFICATION.md §7.3](SPECIFICATION.md) · [ADR-0010](ADR/ADR-0010-lxdb-direction.md) · [ADR-0007](ADR/ADR-0007-container-v0-freeze.md)

## Purpose & Scope (intent level only)

`.lxdb` is the blueprint's envisioned incremental/update mode: append documents, update entries, and rebuild indexes without rewriting whole archives, while preserving the same byte-exact contract on canonical bytes.

## Why it is deferred

1. `.lxz` static container is not even frozen; update semantics over an unfrozen base format would be designed twice.
2. Recovery/consistency machinery (journaling, index rebuild) multiplies decoder attack surface — must follow, not precede, the hardened single-file path.
3. Benchmark gates for update-mode overhead require a validated baseline to compare against.

## Questions the eventual design ADR must answer (none answered today)

- Update granularity: append-only segments vs. in-place block rewrite?
- Journal/WAL strategy and crash-recovery semantics (see future `DATABASE_RECOVERY.md`, Batch D).
- Index maintenance cost accounting under [COST_MODEL.md](COST_MODEL.md) rules.
- Interaction with dictionaries/grammars when training data grows incrementally (lineage rules REQ-EXP-002 still apply).
- Concurrency expectations (currently: none assumed; prototype is single-process).

## Status gate

| Gate | Condition | Met? | Evidence (re-measured 2026-10-29, Session 52) |
|---|---|---|---|
| G1 | Core pipeline round-trip validated (Phase 1 exit) | ✅ **Met** | P1 complete; round trip asserted at every layer, and end-to-end `canon → pack → unpack` returns a byte-identical tree (Session 51) |
| G2 | Frozen-corpus benchmark run completed (Phase 2 exit) | ❌ **Not met** — but for a different reason than before | **Corpus size is satisfied:** 2395 files / 1.054 GiB (`benchmarks/provenance/gutenberg-cat-partial/sources.json`, manifest `c92cf578…`). What remains is a **protocol-scope benchmark run** (all three splits at full size, 3 reps, `xz9` via the CLI, second machine class) and **owner sign-off**; R4/R5 are bounded subsets |
| G3 | `.lxz` format ADR accepted (Phase 4) | ✅ **Met** | [ADR-0007](ADR/ADR-0007-container-v0-freeze.md) Accepted 2026-10-16 and exercised ever since |

**What the gates now allow, and what they still forbid.** G1 and G3 are met, so the *direction* decision is open and is recorded in [ADR-0010](ADR/ADR-0010-lxdb-direction.md) (Accepted). G2 is not met, so **no byte layout, no magic, no field widths, and no `.lxdb` code** — a layout frozen before the benchmark that would judge it is exactly the sequencing error ADR-0007 avoided for `.lxz`. When G2 closes, the layout becomes its own ADR (proposed: ADR-0013) with its own test vectors.

**Why the direction question was worth opening before G2:** `batch` produces one `.lxz` per document, and each pays 168 bytes of fixed container overhead plus 56 bytes per block of index — measured, a 23-byte document became a 256-byte archive (91 % container). That is `.lxz` behaving correctly; it is simply the wrong shape for a library, and the shape can be chosen cheaply before any bytes are frozen.
