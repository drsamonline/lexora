# LEXORA Normative Specification

> **Status:** `LEXORA-SPEC-1.0-draft` — PROPOSED, NOT APPROVED. Sections marked *(Proposed)* depend on ADRs not yet accepted.
> **Owner:** Unassigned
> **Last verified:** 2026-10-15 (no implementation exists; nothing herein is validated by code)
> **Related:** [MASTER_BLUEPRINT.md](MASTER_BLUEPRINT.md) · [PRODUCT_REQUIREMENTS.md](PRODUCT_REQUIREMENTS.md) · [DECISIONS.md](DECISIONS.md)

## Purpose & Scope

Normative, testable requirements for LEXORA behavior and data representations. Keywords **MUST**, **MUST NOT**, **SHOULD**, **MAY** are interpreted strictly. This document does not define the `.lxz` byte layout (see [FORMAT_LXZ.md](FORMAT_LXZ.md), which is explicitly unfrozen).

Earlier informal "v2.2" notes are *not* versions of this specification.

---

## 1. Layering contract

1.1 The pipeline MUST be separable into: extraction → canonicalization → compression → archival → verification.
1.2 Canonicalization MAY discard information relative to the extracted source text. Recovering the original source or raw OCR output from an archive is **out of scope** and MUST NOT be claimed.
1.3 For every canonical byte string `C`, the compressor MUST satisfy `decode(encode(C)) == C` byte-exactly. Any deviation is a defect of severity blocker. `[REQ-CMP-001]`

## 2. Canonicalization

2.1 **Determinism.** Same input bytes + same canonicalizer version ⇒ identical output bytes. Implementations MUST expose the canonicalizer version string. `[REQ-CAN-001]`
2.2 **Encoding.** Output MUST be UTF-8 without BOM unless a future versioned rule set explicitly includes one. Newline policy is fixed per canonicalizer version and recorded in the version identifier. `[REQ-CAN-002]`
2.3 **Whitelist rule.** Only transformations listed in the approved rule table MAY alter bytes; all other bytes pass through unchanged. `[REQ-CAN-003]`
   - Rule table itself: [CANONICALIZATION.md](CANONICALIZATION.md) *(Proposed — rules not yet frozen; Phase 0 exit criterion)*.
2.4 **Versioning.** Every archive MUST record the canonicalizer version; decoders/verifiers MUST check and report it. `[REQ-CAN-004]`
2.5 **Script safety.** Rules MUST NOT decompose or reorder combining marks, ZWJ/ZWNJ in Devanagari or Gujarati sequences. Golden vectors REQUIRED before any rule ships. `[REQ-CAN-005]`
2.6 **OCR corrections.** Corrections apply only above configured confidence thresholds and MUST be logged with position and before/after values. `[REQ-CAN-006]`
2.7 **Cleaning quality.** Error rate ≤ 1% under the metric defined in [ADR-0004](ADR/ADR-0004-cleaning-error-metric.md). *(Proposed — ADR pending; requirement currently untestable.)* `[REQ-CAN-007]`

## 3. Tokenization (candidate layer)

3.1 Tokenizers used by experimental candidates MUST define deterministic boundaries with a literal fallback covering every byte not matched by a token rule. No byte may be unrepresentable.
3.2 Tokenizer version participates in codec profile identity. Full rules: [TOKENIZER_SPEC.md](TOKENIZER_SPEC.md) *(Proposed)*.

## 4. Compression

4.1 **Core codec.** Zstandard at declared level/profile is the Core baseline. Archives MUST store codec ID + profile ID sufficient for independent decoding. `[REQ-CMP-002]`
4.2 **Selection.** Codec/candidate selection MUST be a function of measured serialized cost under pinned settings; re-encoding the same input with the same settings MUST produce identical archive bytes. `[REQ-CMP-003]`
4.3 **Total-cost accounting.** Selection and reporting MUST count every serialized byte: headers, side tables, embedded dictionaries, grammar stores, block metadata. `[REQ-CMP-004]`
4.4 **Bounded decode.** Decoding a single document/block MUST NOT require loading the entire archive into memory. `[REQ-CMP-005]`
4.5 **Unknown features.** An unknown codec ID or unsupported must-understand feature flag MUST cause refusal with a specific error code; partial or best-effort output is FORBIDDEN. `[REQ-CMP-006]`
4.6 **Baselines vs. codecs.** Brotli q11, XZ, PPMd are measurement baselines only and MUST NOT be emitted as selectable archive codecs. *(Proposed — [ADR-0002](ADR/ADR-0002-brotli-role.md), [ADR-0003](ADR/ADR-0003-ppmd-role.md).)*

## 5. Experimental candidates

5.1 Candidates (shared dictionaries, Re-Pair grammar, bounded token PPM, numeric/record coding, template+residual) enter the default pipeline only after passing the promotion gate. `[REQ-EXP-001]`
5.2 **Gate scope.** *(Proposed — [ADR-0001](ADR/ADR-0001-gate-scope.md): promotion = ≥10% total-size win per category on validation, reproduced on held-out; corpus verdict = Pass ≥10% / Partial ≥3% / Fail <3%.)*
5.3 Learned structures MUST be induced only from the training split (lineage separation). `[REQ-EXP-002]`
5.4 Each candidate MUST carry a documented retirement threshold and be re-ablated each benchmark revision. `[REQ-EXP-003]`

## 6. Dictionary identity

6.1 A dictionary reference in an archive MUST resolve to exact content identified by (dictionary ID, SHA-256 of dictionary bytes, dictionary format version). Decoder MUST verify the hash before use; mismatch ⇒ refusal.
6.2 Embedded dictionaries count toward total-cost accounting (§4.3).

## 7. Archive semantics (`.lxz`)

7.1 Requirements: magic, version fields, codec/profile IDs, checksums, indexes, resource-limit declarations, must-understand/may-ignore feature flags. `[REQ-FMT-001..003]`
7.2 **The byte layout is NOT FROZEN.** No offsets, field widths, or test vectors are normative until an accepted format ADR commits them. See [FORMAT_LXZ.md](FORMAT_LXZ.md) (`PROPOSED — NOT A STABLE FORMAT`).
7.3 `.lxdb` incremental mode is deferred until `.lxz` baseline is validated. `[REQ-FMT-004]`

## 8. Verification & corruption handling

8.1 On write, the tool MUST verify round-trip equality for 100% of archived content before reporting success.
8.2 Checksum failure on read ⇒ refuse decode, explicit error, no output bytes emitted for the affected block. `[REQ-SEC-004]`
8.3 Truncated/hostile archives MUST NOT cause unbounded allocation: validate lengths/checksums before allocating buffers proportional to declared limits. `[REQ-SEC-001]`

## 9. Resource limits

9.1 Target machine class: ~4 GiB RAM. Peak RSS budget and block-size ceilings: [RESOURCE_LIMITS.md] *(planned, Batch C/D — numbers not yet measured; none are asserted here)*.
9.2 Offline operation after dependency installation is REQUIRED. `[REQ-RES-003]`

## 10. Compatibility rules

10.1 Format minor versions MUST remain readable by declaring new optional features only via may-ignore flags.
10.2 Changing canonicalization/tokenization/format/decoder semantics requires: ADR + version identifier bump + updated golden tests, in the same change.

## Open decisions blocking approval of this spec

| Blocker | Section(s) | ADR |
|---|---|---|
| Gate scope | §5.2 | ADR-0001 (Proposed) |
| Baseline roles | §4.6 | ADR-0002, ADR-0003 (Proposed) |
| Cleaning metric | §2.7 | ADR-0004 (Proposed) |
| Rule table freeze | §2.3 | Pending Phase 0 work |
| Byte layout | §7.2 | Pending format ADR |

**Until these close, `LEXORA-SPEC-1.0` cannot move from draft to Approved.**
