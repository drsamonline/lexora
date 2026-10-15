# LEXORA Security Architecture

> **Status:** Draft (design-intent document; **no implementation exists**, so nothing here is enforced by code — verified 2026-10-15)
> **Owner:** Documentation architect (delegated)
> **Last verified:** 2026-10-15
> **Related:** [THREAT_MODEL.md](THREAT_MODEL.md) · [RESOURCE_LIMITS.md](RESOURCE_LIMITS.md) · [PRIVACY_AND_DATA_HANDLING.md](PRIVACY_AND_DATA_HANDLING.md) · [ENCRYPTION_PROFILE.md](ENCRYPTION_PROFILE.md) · [SPECIFICATION.md](SPECIFICATION.md) · root [SECURITY.md](../SECURITY.md) · blueprint §8

## Purpose & scope

Describes how security properties are *designed into* LEXORA's pipeline: which components are trusted, where hostile input enters, which invariants bound the damage, and how integrity/confidentiality requirements (REQ-SEC-001…004) map onto mechanisms. This is an architecture-of-record for future implementation, not a claim that any protection currently ships.

**No security guarantees are claimed.** Until code, tests, fuzzing, and review exist (see gap table at the end), every mechanism below is *intended*, not *provided*.

## Design posture

1. **The decoder is the attack surface.** Archives produced by others (or tampered copies of your own) are parsed by the decoder on low-resource machines (~4 GiB RAM). The decoder MUST treat every archive as hostile input: validate lengths, checksums, counts, and offsets *before* allocating or seeking (REQ-SEC-001, blueprint §8.1).
2. **Compression ≠ encryption.** LEXORA provides no confidentiality by default. Dictionary coding can *leak vocabulary* across documents; this is treated as a privacy hazard, not just a compression detail ([PRIVACY_AND_DATA_HANDLING.md](PRIVACY_AND_DATA_HANDLING.md)).
3. **Losslessness is a safety property.** A silent byte-loss bug corrupts user data at scale. Round-trip verification `decode(encode(C)) == C` is enforced at build time (blueprint invariants; SPEC §4), which doubles as a defense against crafted archives exploiting lenient readers.
4. **Fail closed.** Any integrity, limit, feature-negotiation, or (if ever enabled) AEAD check failure aborts the operation with an explicit error; partial or unauthenticated output MUST NOT be returned as valid (REQ-SEC-004; blueprint §8.2). Error semantics live in [ERROR_HANDLING.md](ERROR_HANDLING.md).
5. **Small trusted core, bounded extensions.** Codecs/dictionaries/grammars are declared in-archive with IDs and hashes; unknown *required* features ⇒ refuse to decode. Optional features degrade explicitly, never silently.

## Trust boundaries

| Boundary | Trusted side | Untrusted input crossing it | Controls intended |
|---|---|---|---|
| Source files → extraction | User's machine / document owner | Arbitrary TXT/PDF bytes, embedded fonts/scripts in PDFs | Parser hardening, resource caps, no code execution from data |
| Extraction → canonicalization | Internal | Extracted text (arbitrary Unicode, control chars) | Versioned rule whitelist CAN-R01…R09, deterministic UTF-8, script-safety mandate ([CANONICALIZATION.md](CANONICALIZATION.md)) |
| Canonical bytes → encoder | Archive producer (often = user) | n/a (encoder trusts its own corpus within limits) | Limit table enforcement before allocation |
| `.lxz` archive → decoder | Anyone hands you a file | **Fully hostile**: headers, index, dictionaries, grammars, token streams, block sizes/offsets | Pre-allocation validation, LIM-01…LIM-nn ceilings, checksum-before-use, bounded recursion/expansion |
| Keys/credentials → encryption profile (future) | User / OS credential store | Key material handling bugs | Vetted AEAD library only, nonce-uniqueness rules, no keys in archive ([ENCRYPTION_PROFILE.md](ENCRYPTION_PROFILE.md)) |
| Corpus → shared dictionaries | Project maintainers | Sensitive content leaking via dictionary vocab | Privacy classification gate, opt-in publication ([CORPUS_POLICY.md](CORPUS_POLICY.md), REQ-SEC-002) |

## Asset inventory

| Asset | Why valuable | Primary threats |
|---|---|---|
| User source documents (pre-canonicalization) | Irreplaceable originals | Overwrite/deletion during ingest; leakage via published artifacts |
| Canonical bytes & `.lxz` archives | Recoverable data + business value | Corruption, truncation attacks, tampering without detection |
| Shared dictionaries / grammars | Learned representations | Vocabulary leakage of sensitive text; silent meaning change (ID reuse) |
| Keys (if encryption ever ships) | Confidentiality root | Extraction from archives, weak derivation from public data, nonce reuse |
| The host running decode | Availability | Memory/CPU exhaustion via crafted archives |

## Mechanism map (requirements → design)

| Requirement | Mechanism (intended) | Spec location | Implementation status |
|---|---|---|---|
| REQ-SEC-001 hostile archives ⇒ bounded memory | Validate-before-allocate; [RESOURCE_LIMITS.md](RESOURCE_LIMITS.md) ceilings enforced by reader; streaming block processing | SPEC §4, FORMAT_LXZ reqs | Not started |
| REQ-SEC-002 no sensitive content in shared dictionaries | Corpus privacy classification, default-deny publication, dictionary provenance records | CORPUS_POLICY.md | Not started |
| REQ-SEC-003 optional AEAD encryption | ChaCha20-Poly1305 or AES-256-GCM, per-block scope, header-as-AEAD, durable nonce discipline | ENCRYPTION_PROFILE.md (Proposed) | Out of current scope |
| REQ-SEC-004 corruption detected on read | Per-block + whole-archive checksums; mismatch ⇒ refuse decode with explicit error | SPEC §4/§7, ERROR_HANDLING.md | Not started |
| Blueprint §8.1 fuzzing mandate | Fuzz headers, dictionaries, grammar, token streams, truncated files once decoders exist | TEST_STRATEGY.md layers | Not started |

## Non-goals (security-wise)

- Sandboxing the OCR stack or PDF parser OS-level (deployment concern, documented in runbooks as operator guidance only).
- Side-channel resistance of codec selection (cost-model timing leaks are acknowledged in THREAT_MODEL as out-of-profile for v1).
- Access control or multi-user database security (`.lxdb` deferred entirely).
- Anonymization of text: LEXORA stores what it is given; privacy depends on policy, not clever encoding.

## Gaps before any guarantee can be claimed

1. No code exists — all controls above are paper designs.
2. No fuzzing harness, crafted-archive corpus, or bit-flip test suite.
3. No third-party review performed.
4. Vulnerability-report intake channel pending owner contact details (root [SECURITY.md](../SECURITY.md) states process only).
5. Encryption profile awaits threat review + nonce design before leaving Proposed status (blueprint §9 step 13).

## Open questions touched here

OQ-5 (license ⇒ affects SECURITY.md legal wording minimally), OQ-8 (corpus rights/privacy class ⇒ REQ-SEC-002 audit), OQ-9 (OCR tooling supply chain), plus encryption scoping decision tracked in [ENCRYPTION_PROFILE.md](ENCRYPTION_PROFILE.md).
