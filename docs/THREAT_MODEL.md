# LEXORA Threat Model

> **Status:** Draft (first-pass STRIDE-style model over the *design*, not a reviewed product assessment; no implementation exists — verified 2026-10-15)
> **Owner:** Documentation architect (delegated)
> **Last verified:** 2026-10-15
> **Related:** [SECURITY_ARCHITECTURE.md](SECURITY_ARCHITECTURE.md) · [SPECIFICATION.md](SPECIFICATION.md) · [RESOURCE_LIMITS.md](RESOURCE_LIMITS.md) · [FORMAT_LXZ.md](FORMAT_LXZ.md) · [PRIVACY_AND_DATA_HANDLING.md](PRIVACY_AND_DATA_HANDLING.md) · blueprint §8

## Purpose & scope

Enumerate assets, entry points, attacker profiles, and concrete threats against LEXORA's design, then map each threat to intended mitigations and residual risk. Scope covers: ingestion of hostile source files, encoding of user corpora, distribution and decoding of `.lxz` archives, shared dictionaries, and (future, out-of-scope-until-gated) encryption. `.lxdb` is deferred and excluded.

## Attacker profiles

| ID | Profile | Capability | Motivation |
|---|---|---|---|
| AT-1 | Malicious archive author | Crafts arbitrary bytes claiming to be `.lxz`; ships file to victim via any channel | Code execution avoidance research, DoS, data corruption, privacy probing |
| AT-2 | Man-in-the-middle / tamperer | Flips bits in transit or at rest in an archive the victim trusts | Silent corruption, downgrade of codec/features |
| AT-3 | Untrusted document source | Supplies TXT/PDF designed to exploit extraction/canonicalization | Same as AT-1 but upstream of compression |
| AT-4 | Curious dictionary/artifact consumer | Obtains a published shared dictionary or benchmark artifact | Reconstruct vocabulary / infer corpus content |
| AT-5 | Operator error | Not adversarial: misconfigured limits, wrong split of train/validation, deleted originals | Data loss, invalid benchmark claims |

## Entry points

1. Source file paths given to ingest (AT-3).
2. `.lxz` file handed to decode (AT-1, AT-2).
3. Dictionary/grammar files referenced by an archive (AT-1/AT-4).
4. Published project artifacts: dictionaries, benchmark results, corpora (AT-4).
5. Configuration inputs: limit overrides, codec toggles, corpus manifests (AT-5).

## Threat register

Numbering `TM-nn`. "Mitigation status" reflects *design intent only* until code exists — nothing is implemented (see STATUS.md).

| ID | Category (STRIDE) | Threat scenario | Impact | Likelihood | Intended mitigation | Mitigation status | Residual risk |
|---|---|---|---|---|---|---|---|
| TM-01 | Denial of service | Header declares 4 GiB block; decoder allocates before validating → OOM on 4 GiB machine | Crash/exhaustion | High | Validate sizes against LIM-01…LIM-nn *before* allocation; stream blocks ([RESOURCE_LIMITS.md](RESOURCE_LIMITS.md)) | Design-only | Low if enforced + fuzzed; unknown today |
| TM-02 | Denial of service | Compressed block expands exponentially (zip-bomb style) | Disk/memory exhaustion | High | Per-block expansion-ratio cap checked during streaming; abort past cap | Design-only | Medium — ratio cap value unmeasured |
| TM-03 | Tampering | Bit flip in index offset passes unnoticed; decoder returns wrong document bytes | Silent data corruption | Medium | Per-block checksums + whole-archive digest; mismatch ⇒ refuse (REQ-SEC-004); bit-flip test suite planned | Design-only | Low once tests exist |
| TM-04 | Tampering | Truncated archive read as complete | Partial output accepted | Medium | Explicit EOF checks vs declared counts; fail closed ([ERROR_HANDLING.md](ERROR_HANDLING.md)) | Design-only | Low |
| TM-05 | Repudiation | Producer claims encoder corrupted data; no evidence either way | Trust loss | Low | Build-time round-trip verification logs (`decode(encode(C))==C`) recorded per archive; version stamps (canonicalizer `lexcan-x.y`, codec IDs) | Design-only | Medium — log format undefined |
| TM-06 | Information disclosure | Published shared dictionary leaks rare words from clinical corpus (names, diagnoses) | Privacy breach | Medium-high | REQ-SEC-002 default-deny; privacy classification gate; rare-token scrubbing review before publication ([CORPUS_POLICY.md](CORPUS_POLICY.md), [PRIVACY_AND_DATA_HANDLING.md](PRIVACY_AND_DATA_HANDLING.md)) | Policy-only | Medium — needs audit procedure once corpora exist (OQ-8) |
| TM-07 | Information disclosure | Benchmark artifacts (samples, hashes) leak corpus excerpts | Privacy breach | Medium | Publish aggregates + hashes only; sample excerpts require explicit owner clearance | Policy-only | Low-medium |
| TM-08 | Elevation of privilege | PDF embedded JavaScript/actions executed by a permissive parser during extraction | Host compromise | Medium | Choose parser without active-content execution; disable JS; OCR pipeline runs as subprocess with resource caps ([OCR_PIPELINE.md](OCR_PIPELINE.md)) | Design-only | Depends on library choice (unmade) |
| TM-09 | Elevation of privilege | Grammar/token-stream recursion or cyclic dictionary references cause unbounded work | DoS/code-execution foothold | Medium | Acyclicity check before use; bounded rule depth (LIM-06 area); malformed-reference rejection | Design-only | Low if fuzzed |
| TM-10 | Spoofing | Codec/dictionary ID reused after semantic change; decoder applies wrong representation | Corruption | Medium | Immutable ID→hash binding; hash mismatch ⇒ refuse decode | Design-only | Low |
| TM-11 | Tampering (future) | If encryption ships: nonce reuse under same key | Catastrophic AEAD failure | n/a today | Durable per-key counter or strict random-nonce budget; stop-on-uncertainty rule ([ENCRYPTION_PROFILE.md](ENCRYPTION_PROFILE.md)) | Proposed, gated | Deferred with feature |
| TM-12 | DoS | Cost-model candidate search explores unbounded combinations at encode time | CPU exhaustion | Medium | Candidate set fixed by registry; per-candidate budgets; selection is measured-cost, not heuristic search explosion ([COST_MODEL.md](COST_MODEL.md)) | Design-only | Low |
| TM-13 | Repudiation/Integrity | Supply-chain: tampered dependency silently changes canonical bytes | Corpus-wide corruption | Medium | Pinned baselines + lockfile discipline (planned, Batch E CI); golden vectors catch drift ([CANONICALIZATION.md](CANONICALIZATION.md)) | Planned | Medium until CI exists |

## Explicitly out of profile (v1)

- Multi-tenant access control (no server, no `.lxdb`).
- Timing/side-channel analysis of codec selection against adversary who can measure encode times.
- Cryptographic strength claims (encryption out of current scope; REQ-SEC-003).
- Physical security, OS hardening beyond operator-guidance runbook notes.

## Cross-references to requirements

TM-01/02/09/12 → REQ-RES-* + REQ-SEC-001; TM-03/04/10 → REQ-SEC-001/004 + REQ-FMT-002; TM-06/07 → REQ-SEC-002; TM-11 → REQ-SEC-003; TM-13 → TEST_STRATEGY golden-vector layer. Full chain in [REQUIREMENTS_TRACEABILITY.md](REQUIREMENTS_TRACEABILITY.md).

## What must happen before this model can be called "addressed"

1. Implementation of decoder validation path (Phase ≥1) with crafted-archive tests.
2. Fuzzing campaign per blueprint §8.1; findings logged here as new TM rows or mitigated-status updates.
3. Owner answers OQ-8 so TM-06/TM-07 policies become auditable.
4. Independent review (none performed).
