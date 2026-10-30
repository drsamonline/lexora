# LEXORA Error Handling

> **Status:** Draft (taxonomy reconciled with the shipped CLI 2026-10-17, Session 25 — see Global rule 5; severity/recovery sections remain contract for future implementation)
> **Owner:** Documentation architect (delegated)
> **Last verified:** 2026-10-29 (Session 67 reconciliation: interruption table measured with real signals)
> **Related:** [SPECIFICATION.md](SPECIFICATION.md) · [CLI_REFERENCE.md](CLI_REFERENCE.md) · [LOGGING_AND_DIAGNOSTICS.md](LOGGING_AND_DIAGNOSTICS.md) · [RESOURCE_LIMITS.md](RESOURCE_LIMITS.md) · [THREAT_MODEL.md](THREAT_MODEL.md) TM-03/TM-04 · runbooks/

## Purpose & scope

Defines the error taxonomy, severity levels, and behavioral contract every LEXORA component MUST follow once implemented: what fails closed, what is recoverable, what may be retried, and what the user/operator sees. Goal: **no silent data loss, no partial output presented as success** (blueprint invariants; REQ-SEC-004).

## Interruption behaviour (measured, Session 57)

The atomic-write guarantee — *a crash leaves either the previous artifact or the new
one, never a hybrid* — was tested only with simulated failures until Session 57, when
a real `pack` was killed with real signals. What actually survives:

| Signal | Destination | Temp file (`.lxz-tmp-*`) |
|---|---|---|
| SIGINT (Ctrl-C) | untouched — never partially written | removed |
| SIGTERM | untouched | removed (a handler turns it into `SystemExit` so the writers' cleanup runs — added Session 57; before that it left debris) |
| SIGKILL | untouched | **left behind** — uncatchable, so debris is unavoidable |
| crash mid-write (exception) | untouched | removed |
| disk full / ENOSPC | untouched | removed, exit 3 |

The destination is safe in every case because it is only ever created by
`os.replace` once the temp file is complete. SIGKILL debris is the one residue: it
does not endanger an existing archive, and re-running the command overwrites the
destination normally — the stale temp file simply stays until removed by hand.

## Global rules

1. **Fail closed on integrity.** Checksum, AEAD (if ever enabled), hash-of-dictionary, or round-trip verification failure ⇒ abort with `E-INTEGRITY-*`; never emit partially recovered text as if valid.
2. **Fail bounded on resources.** Any limit breach ([RESOURCE_LIMITS.md](RESOURCE_LIMITS.md)) ⇒ abort *before* allocation where possible; report which LIM-id tripped and observed vs. allowed size.
3. **Determinism preserved.** Canonicalization is deterministic even under error: a document that fails rule validation is quarantined whole; it never produces partial canonical bytes.
4. **Errors are identifiers, not prose.** Machine-readable codes below; human text is generated at display time only. Log lines reference IDs + hashes, never document bodies ([PRIVACY_AND_DATA_HANDLING.md](PRIVACY_AND_DATA_HANDLING.md)).
5. **Exit codes stable per CLI contract** once CLI exists (CLI_REFERENCE.md, Batch E+): 0 success; 1 usage; 2 input error; 3 integrity; 4 resource limit; 5 internal bug; 6 environment/IO. (Proposed — freeze with first implemented CLI.) **Update 2026-10-16:** the first real CLI shipped with a *different* tested scheme (0/2/3/4/5/6 = ok/usage/file/canonicalization/codec/round-trip); [CLI_REFERENCE.md](CLI_REFERENCE.md) is now normative for the implemented commands and this taxonomy must be reconciled with it before any release. **Reconciliation adopted Session 25 (delegated):** the SHIPPED exit-code space stays frozen at `0/2/3/4/5/6/7` (ok / usage / file-IO / canonicalization / codec / round-trip / container-refusal) because it is already externally observable and test-locked (`tests/test_cli.py`, `tests/test_container_lxz.py`). The proposed families map onto it as follows — E-USAGE→2; E-INPUT-ENC & E-CAN→4; E-CMP decode-level→5; E-CMP-001 round-trip→6; E-FMT-HEAD/E-FMT-IDX/E-RES/E-INTEGRITY→7; E-IO→3; E-INT→5 (reserved-with-context-log). Proposed code *names* are retained verbatim in exception attributes (`ContainerError.code`) so family semantics survive even though they no longer dictate numeric exits. The original 0–6 proposal above is kept only as historical context.

## Severity levels

| Level | Meaning | User impact | Example |
|---|---|---|---|
| fatal | Operation cannot continue; nothing written as final | Hard stop | Archive header corrupt |
| error | Item rejected; operation continues for other items | Partial batch success, clearly reported | One document fails round-trip verify |
| warning | Accepted with deviation from ideal | Success, flagged | Optional feature absent, degraded codec chosen |
| info | Normal progress event | None | Block compressed |

## Error taxonomy (proposed codes)

| Code family | Specific codes (examples) | Trigger | Required behavior | Retryable? |
|---|---|---|---|---|
| E-USAGE | E-USAGE-001 missing arg; E-USAGE-002 conflicting flags | Bad invocation | Usage text, exit 1 | After fix |
| E-INPUT-ENC | E-INPUT-ENC-001 undetectable encoding; E-INPUT-ENC-002 invalid UTF-8 sequence after declared decode | Ingestion | Quarantine file, list in report | No (manual re-encode) |
| E-INPUT-PDF | E-INPUT-PDF-001 no text layer & OCR unavailable/disabled; E-INPUT-PDF-002 encrypted PDF w/o password | Extraction | Per-page record; page marked extracted-empty ONLY with explicit operator opt-in flag, else error | Yes (supply creds/OCR) |
| E-CAN | E-CAN-001 rule precondition failed; E-CAN-002 script-safety violation | Canonicalization | Quarantine document whole; increment audit counter feeding ADR-004 metric | No |
| E-CMP | E-CMP-001 round-trip verify failed (encoder bug class); E-CMP-002 no codec meets budget | Compression | Abort archive write; preserve prior state; E-CMP-001 additionally dumps repro case | No (bug — file issue) |
| E-FMT-HEAD | E-FMT-HEAD-001 bad magic/version; E-FMT-HEAD-002 unknown required feature bit | Decode open | Refuse; name the feature | No |
| E-FMT-IDX | E-FMT-IDX-001 offset out of range; E-FMT-IDX-002 count mismatch; E-FMT-IDX-003 truncation detected | Index parse | Refuse archive | No |
| E-FMT-DICT | E-FMT-DICT-001 dictionary hash mismatch; E-FMT-DICT-002 dictionary too large (LIM-05) | Dictionary load | Refuse | No |
| E-RES | E-RES-001..0nn mapped 1:1 to each LIM-id | Limit breach | Abort before allocation where feasible | Sometimes (raise limits only within documented envelope) |
| E-IO | E-IO-001 disk full; E-IO-002 permission denied; E-IO-003 file vanished mid-run | OS layer | Clean message, preserve temp files for forensics unless cleanup-safe | Yes |
| E-INT | E-INT-001 invariant violated (should-be-impossible) | Internal | Panic-with-context log; exit 5; ask user to attach log (minus content) | No |

## Recovery semantics

- **Atomic archive write**: encode writes to temp + fsync + rename; a crash leaves either the old artifact or the new one, never a hybrid (mirrors blueprint §7.4 discipline ahead of `.lxdb`).
- **Batch runs**: per-item quarantine means one bad document never aborts a corpus run; the run's final report MUST enumerate accepted / quarantined / failed with codes.
- **Decode**: refusal is always all-or-nothing for integrity errors; there is deliberately **no `--ignore-checksums` flag** in the design (any such tool must be external, e.g., hex surgery guided by [runbooks/CORRUPTION_TRIAGE.md](runbooks/CORRUPTION_TRIAGE.md)).

## What is NOT an error

- Incompressible data growing slightly above baseline expectation → recorded cost outcome, not error.
- Optional-features-absent degradation when the feature was *optional*-flagged → warning.
- Canonicalization intentionally dropping formatting fidelity → by-design information policy (README invariant), tracked by quality metrics, not runtime errors.

## Implementation note

Codes above are a *contract draft*; they freeze with SPECIFICATION approval and first CLI implementation. Until then no software emits them — do not cite these codes as shipped behavior.
