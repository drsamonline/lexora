# Runbook: Corruption Triage

> **Status:** Draft (procedure for the designed system; usable today only for *design review* of hypothetical incidents — verified 2026-10-15)
> **Owner:** Documentation architect (delegated)
> **Related:** [../ERROR_HANDLING.md](../ERROR_HANDLING.md) · [../THREAT_MODEL.md](../THREAT_MODEL.md) TM-03/TM-04 · [../SECURITY_ARCHITECTURE.md](../SECURITY_ARCHITECTURE.md) · [RECOVERY_RUNBOOK.md](RECOVERY_RUNBOOK.md) · root [../../SECURITY.md](../../SECURITY.md)

## When to use

Any of: decode refuses an archive (E-FMT-*, checksum mismatch), recovered text differs from expectation, determinism broken (same input → different canonical bytes), dictionary hash mismatch, or suspicion of tampering in transit/at rest.

## Golden rules

1. **Stop writing.** Freeze the affected storage location; no re-runs that overwrite artifacts before triage completes.
2. **Never bypass integrity checks** to "get the data out" inside LEXORA tooling (no `--ignore-checksums` exists by design). If partial recovery is attempted, it happens on a *copy*, outside the pipeline, and its output is labeled untrusted.
3. **Compression ≠ encryption**: if the incident involves an archive of sensitive data being mishandled, this runbook hands off to [../PRIVACY_AND_DATA_HANDLING.md](../PRIVACY_AND_DATA_HANDLING.md) incident section immediately after containment.

## Steps

1. **Contain & snapshot.** Copy the failing archive, referenced dictionaries/grammars, run manifest, and logs (level ≥ WARN) to an incident folder. Record SHA-256 of every file at intake. Work only on copies thereafter.
2. **Classify the failure surface** using the error code / log events:
   - Header/magic/version ⇒ file identity problem (wrong, truncated, or newer format).
   - Index offsets/counts ⇒ structural damage.
   - Block checksum ⇒ payload damage (bit flip, truncation, substitution).
   - Dictionary hash ⇒ sidecar mismatch, not necessarily archive damage.
   - Round-trip verify at encode time ⇒ encoder bug — highest severity; preserve repro corpus.
3. **Localize non-destructively.** Compare observed vs declared sizes; check EOF position against index's last block end; diff two copies of the same logical archive (if one exists) to find differing byte ranges. Record offsets only — do not paste content into tickets.
4. **Determine cause bucket:** media/storage fault, transport truncation, concurrent-write corruption, deliberate tamper (multiple inconsistent fields, hostile values ⇒ treat as security event per [../SECURITY_ARCHITECTURE.md](../SECURITY_ARCHITECTURE.md)), or software bug (reproducible with clean inputs).
5. **Recover or rebuild:**
   - Source originals still exist ⇒ **rebuild is always preferred over repair.** Re-ingest → re-canonicalize → re-encode with pinned versions; verify round-trip; replace artifact and update manifest.
   - Originals gone ⇒ attempt documented external byte-surgery on a copy; any recovered bytes must be independently verified (human review + hash comparison against manifest where possible); label results "unverified recovery."
   - `.lxdb`-style committed-state questions ⇒ see [RECOVERY_RUNBOOK.md](RECOVERY_RUNBOOK.md) (note: `.lxdb` itself is deferred/not designed).
6. **Close honestly.** Incident note appended to [../SESSION_LOG.md](../SESSION_LOG.md): what was lost (exact byte counts if unknown recovery), root cause status (confirmed/suspected/open), corrective action, and any new TM-nn row added to [../THREAT_MODEL.md](../THREAT_MODEL.md). No "resolved" without evidence.

## Escalation

- Suspected vulnerability (crafted archive causing crash/unbounded memory even when refusing correctly) ⇒ root [../../SECURITY.md](../../SECURITY.md) reporting instructions; do not disclose details publicly first.
- Suspected privacy disclosure ⇒ [../PRIVACY_AND_DATA_HANDLING.md](../PRIVACY_AND_DATA_HANDLING.md) incident handling.
