# `.lxdb` Incremental Database Mode

> ## ⚠️ DEFERRED — NOT DESIGNED
> **Status:** Deferred by policy (REQ-FMT-004): work begins only after the `.lxz` baseline is implemented and validated. No layout, no semantics, no claims.
> **Owner:** Unassigned
> **Last verified:** 2026-10-15
> **Related:** [FORMAT_LXZ.md](FORMAT_LXZ.md) · [SPECIFICATION.md §7.3](SPECIFICATION.md)

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

| Gate | Condition | Met? |
|---|---|---|
| G1 | Core pipeline round-trip validated (Phase 1 exit) | ❌ Not started |
| G2 | Frozen-corpus benchmark run completed (Phase 2 exit) | ❌ Not started |
| G3 | `.lxz` format ADR accepted (Phase 4) | ❌ Not started |

**No `.lxdb` design work may begin before G3.** This file exists solely to record that constraint and the open questions; it contains zero specification.
