# LEXORA Encryption Profile

> ## ⚠️ PROPOSED — OUT OF CURRENT SCOPE (blueprint Phase 9; gated by REQ-SEC-003)
> **Status:** Draft design notes. **No encryption exists, is enabled, or is scheduled to ship before a threat review + nonce design are accepted.** Do not implement from this document. Do not cite any cipher choice here as decided.
> **Owner:** Unassigned
> **Last verified:** 2026-10-15
> **Related:** [THREAT_MODEL.md](THREAT_MODEL.md) TM-11 · [SECURITY_ARCHITECTURE.md](SECURITY_ARCHITECTURE.md) · [SPECIFICATION.md](SPECIFICATION.md) · [FORMAT_LXZ.md](FORMAT_LXZ.md) · blueprint §8.2 · REQ-SEC-003

## Purpose & scope

Records the *shape* of the optional encryption profile so future design work starts from the blueprint's constraints instead of improvising. Encryption is **optional**, per-block, and only ever added after: (a) threat review updated, (b) nonce scheme proven crash-safe, (c) format freeze allows an authenticated-envelope extension ([FORMAT_LXZ.md](FORMAT_LXZ.md) is itself PROPOSED).

## Hard rules carried from the blueprint (§8.2 — these are non-negotiable prerequisites, not options)

1. **Vetted AEAD library only; never a custom cipher** (master-prompt rule 16).
2. Candidate algorithms: ChaCha20-Poly1305 (256-bit key, 96-bit nonce) **or** AES-256-GCM (256-bit key, 96-bit nonce). Final selection = future ADR; both listed because blueprint lists both.
3. Scope: per compressed block. Header fields that affect interpretation MUST be authenticated as associated data (AAD). Navigation metadata/indexes must be authenticated directly or covered by an authenticated integrity structure.
4. Authentication failure ⇒ abort decoding. Unauthenticated plaintext MUST NOT be returned as valid, even partially.
5. Keys come from the user/OS credential store/documented KMS. Never derived from document text or public hashes; never stored in plaintext inside the archive.

## Nonce discipline (the part most likely to sink a real implementation)

| Scheme | Requirement set | Failure posture |
|---|---|---|
| Durable per-key counter (preferred candidate) | Counter survives crashes/restores monotonically; rollback detection; usage limit per key enforced | If durability cannot be guaranteed on the host ⇒ **encryption stops**; no "probably fine" writes |
| Random nonce with collision budget | Explicit birthday-bound budget per key; strict per-key block/byte ceiling defined *before release*; entropy source audited | Budget exhausted or uniqueness unprovable ⇒ stop and rekey via rotation |

Key rotation: new key identity + fresh nonce space; re-encryption verifies the new representation before discarding the old one. Compression and dictionary coding provide **no confidentiality**; shared dictionaries may leak vocabulary and must be weighed alongside this profile (see [PRIVACY_AND_DATA_HANDLING.md](PRIVACY_AND_DATA_HANDLING.md)).

## Open design items (must close before status leaves Proposed)

- E-1: which AEAD becomes default and why (ADR required).
- E-2: envelope layout interaction with unfrozen `.lxz` block framing (defer until format freeze).
- E-3: counter storage location + crash semantics on target OSes.
- E-4: known-answer test (KAT) vector format for the profile (REQ-SEC-003 verification method).
- E-5: per-key usage ceilings (blocks/bytes) with arithmetic tied to chosen AEAD limits.

## Entry gate

This profile moves from *Proposed/out-of-scope* to *in-design* only when: Phase ≥9 planning begins (blueprint sequence), owner confirms demand, THREAT_MODEL gains reviewed rows for the encrypted-archive attacker model, and an ADR accepts E-1/E-3 decisions. Until then, treat LEXORA archives as **integrity-protected but not confidential**.
