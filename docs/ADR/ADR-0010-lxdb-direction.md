# ADR-0010: `.lxdb` direction — container-of-containers vs block pool (no byte layout)

> **Status:** **Proposed** — recommendation below; approval pending from the owner. This ADR deliberately does **not** specify a byte layout, and no `.lxdb` code may be written until it is Accepted *and* the corpus gate in [FORMAT_LXDB.md](../FORMAT_LXDB.md) is met.
> **Date:** 2026-10-29
> **Deciders:** Owner Dr Sohil Momin (pending); documentation architect (drafted, delegated)
> **Related:** [FORMAT_LXDB.md](../FORMAT_LXDB.md) (gate table, now updated with evidence) · [ADR-0007](ADR-0007-container-v0-freeze.md) (`.lxz` v0 freeze) · [COST_MODEL.md](../COST_MODEL.md) (REQ-CMP-004 accounting) · [RESOURCE_LIMITS.md](../RESOURCE_LIMITS.md) (LIM-01…10) · [FORMAT_LXZ.md](../FORMAT_LXZ.md) · [PHASES.md](../PHASES.md) · [BENCHMARK_PROTOCOL.md](../BENCHMARK_PROTOCOL.md)

## Context / Problem

`.lxz` v0 holds **one** logical stream split into blocks. That was the right freeze for Phase 1: it made the round-trip contract provable with the smallest possible surface. It is the wrong shape for the thing the blueprint actually describes — a *library* of documents where you want to append, address one document, and audit the whole thing.

The forces are now concrete rather than hypothetical, because the CLI has caught up with the format:

- `batch` produces **one `.lxz` per input file**, so a 10,000-document tree is 10,000 files, each paying 168 bytes of fixed container overhead (header + trailer) plus 56 bytes per block of index. Measured on real output: a 23-byte document produced a 256-byte archive, i.e. **91 % container**. That is not a defect in `.lxz` — it is `.lxz` doing exactly what it promises — but it is a poor fit for a library.
- `inspect --in DIR` exists precisely because users need a *run-level* view; that need is a symptom of the container being per-file.
- The corpus work (Sessions 42–43, 51) produced hundreds of small documents, which is the shape of the problem `.lxdb` is for.

Meanwhile [FORMAT_LXDB.md](../FORMAT_LXDB.md) is explicit that no design work may begin before its gates are met. Those gates were stale, so this ADR starts by re-measuring them:

| Gate | Condition | Status now | Evidence |
|---|---|---|---|
| G1 | Core pipeline round-trip validated | **Met** | P1 complete; round trip asserted by tests at every layer, and end-to-end by `canon → pack → unpack` producing a byte-identical tree (Session 51) |
| G2 | Frozen-corpus benchmark run completed (Phase 2 exit) | **Not met** | corpus is 587 files / 287.9 MB of a ≥1 GiB target (`benchmarks/provenance/gutenberg-cat-partial/`, `complete: false`); no protocol-scope revision exists |
| G3 | `.lxz` format ADR accepted | **Met** | [ADR-0007](ADR-0007-container-v0-freeze.md) Accepted 2026-10-16, implemented and exercised since |

So the *direction* question is legitimately open, and the *byte layout* question is still gated on G2. This ADR separates the two on purpose: choosing a shape now is cheap and reversible; freezing bytes before the benchmark exists is neither.

## Decision drivers

- **Reuse over invention.** `.lxz` v0's reader is frozen, tested and hardened; anything that lets it be reused verbatim removes a whole class of new attack surface (REQ-SEC-001, REQ-SEC-004).
- **Per-document overhead.** 168 B fixed + 56 B/block is 91 % of a small archive. A library of small documents needs that to stop dominating.
- **Bounded decode (REQ-CMP-005).** Extracting document *k* must not require decoding documents 0…k-1.
- **Cost accounting (REQ-CMP-004).** "Nothing is free": every byte a reader needs must be attributable, and the archive's total must reconcile against its own index — the identity `inspect` already checks for `.lxz`.
- **Determinism (REQ-CMP-003).** Same inputs ⇒ byte-identical archive, including the document order.
- **Update semantics are a separate decision.** FORMAT_LXDB.md's open questions (append-only segments vs in-place rewrite, journaling, crash recovery) are *not* answered here and should not be pre-empted.

## Options considered

### Option A — Container of containers ("zip of `.lxz`")

`.lxdb` = fixed header + N member blobs, each an ordinary `.lxz` v0 archive, + a document table (name, offset, length, member SHA-256) + trailer.

**Pros:** the v0 reader is reused verbatim per member, so a member is verifiable with today's `verify_stream`; bounded decode is trivial (seek to the member, decode it); the change is additive and the failure modes are already understood. Implementation is small enough to land with real tests.
**Cons:** per-document overhead is **unchanged** (each member still carries its 168 B + index), so it fixes *file count*, not the 91 %-overhead problem. No cross-document compression and no block dedupe — the two things that would make a library genuinely smaller. Two levels of index to keep consistent.

### Option B — Block pool with a document map

One block pool for the whole archive, plus a document table mapping each document to a contiguous run of block indices; block payloads are ordinary zstd frames with per-block SHA-256 as today.

**Pros:** pays container overhead **once** (168 B + index entries), which is where the 91 % goes; enables **block-level dedupe** (identical blocks across documents stored once) and, later, a shared dictionary — the actual compression wins for a library; still supports bounded decode (decode only the blocks a document maps to).
**Cons:** a genuinely new layout to freeze and harden, with new refusal classes (overlapping or gapped block runs, a document referencing blocks twice); accounting becomes per-document *and* archive-total, so REQ-CMP-004 needs restating rather than copying; dedupe introduces a determinism question (does the writer's dedupe choice depend on insertion order? it must not).

### Option C — Segmented append log (closest to "incremental database")

Append-only segments, each a block run with its own index, plus a top-level segment directory; updates append a new segment and a tombstone/replacement entry.

**Pros:** the only option that natively answers the *update* half of FORMAT_LXDB.md's intent without rewriting the file.
**Cons:** brings journaling, crash-recovery semantics and a recovery runbook into scope **now**, which FORMAT_LXDB.md's own deferral rationale warns against ("must follow, not precede, the hardened single-file path"). Premature.

## Decision

**Recommend Option A now, as an explicitly interim step, with Option B named as the successor and the migration path stated.** Precisely:

1. **Shape decision (this ADR, pending approval):** `.lxdb` v0 is a *container of `.lxz` members* with a document table. It solves the file-count and addressing problem, reuses the frozen reader, and can be specified and tested in a fraction of B's risk.
2. **What it does not promise:** it does **not** reduce per-document overhead, does **not** dedupe, and does **not** support updates. Any documentation or UI text implying otherwise would be false.
3. **Successor condition for Option B:** when (a) the corpus gate G2 is met and (b) a measured sample shows per-document overhead or duplicate-block redundancy is materially costing bytes, Option B is designed as a **new format version** (`LXDB` major bump) rather than retrofitted into v0 — the same discipline ADR-0007 applied to `.lxz`.
4. **Byte layout remains gated.** No field widths, magic, ordering or trailer arithmetic are specified here. That work waits on G2, and will be its own ADR (proposed: **ADR-0012**) with its own test vectors, exactly as `.lxz` v0 had ADR-0007.
5. **Update semantics remain out of scope**, per FORMAT_LXDB.md — Option C is recorded as the eventual home for them.

## Consequences & trade-offs

**Positive:** the direction question stops blocking; the reader is reused rather than duplicated; the interim format is small enough to be specified honestly and tested thoroughly; and the successor condition is stated with a measurement attached instead of an opinion.

**Negative / accepted risks:** Option A leaves the 91 %-overhead problem in place, so a library of tiny documents stays inefficient until B lands — accepted because fixing it properly requires the benchmark that G2 is waiting on. There is a real risk that A becomes load-bearing and B never happens; the mitigation is item 3's explicit successor condition, and the refusal to promise overhead savings in A's documentation.

**Rejected now:** Option C (premature recovery machinery), and "do nothing" (the need is already visible in `batch`'s output shape).

## Impact analysis

| Dimension | Impact |
|---|---|
| Security | Option A adds no new decoder surface: each member is parsed by the frozen v0 reader. The new surface is the *document table* (validate-before-allocate: names bounded by LIM-08, count by LIM-03, offsets checked against file length) |
| Performance / memory | A: no change per document; file-count and directory-scan cost drop. B (later): measurable win on small documents, to be benchmarked not asserted |
| Compatibility (format/spec) | Additive: `.lxz` v0 unchanged. `.lxdb` gets its own magic and version; FORMAT_LXDB.md moves from DEFERRED to PROPOSED only when ADR-0011 freezes a layout |

## Implementation & test implications (when approved and ungated)

Files: new `src/lexora/db.py` (writer/reader), `docs/FORMAT_LXDB.md` (spec, after ADR-0011), `docs/CLI_REFERENCE.md` (new verbs), `tests/test_db_*.py`.

Tests that must exist before any of it is called done: member round-trip equality with the `.lxz` it wraps; bounded extraction of document *k* without decoding others (asserted with a counting reader, as `verify_stream` already does); document-table validation refusals (name too long, count over LIM-03, offset past EOF, duplicate names); accounting identity for the whole archive *and* per document; determinism (same inputs ⇒ identical bytes); and a corrupt member failing alone without hiding healthy neighbours — the same properties the `.lxz` surface already enforces.

Benchmark implications: none until G2, and Option B's size claims must go through [BENCHMARK_PROTOCOL.md](../BENCHMARK_PROTOCOL.md) like any other candidate — no ADR-0001 verdict is implied by this document.
