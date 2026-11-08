# ADR-0020: The `codec_id` names a level it does not use — fix at v0→v1

> **Status:** **PROPOSED.** Awaiting one decision from the owner: rename now, or at the v0→v1
> boundary. Everything else in this record is measured and ready.
> **Date:** 2026-11-08
> **Deciders:** Owner Dr Sohil Momin
> **Related:** [ADR-0007](ADR-0007-container-v0-freeze.md) (the frozen field) · [ADR-0012](ADR-0012-default-encode-level.md) (which moved the default to 9) · [ADR-0014](ADR-0014-ziptastic-codec.md) (the registry that made this visible) · [AUDIT_2026-11-07.md](../AUDIT_2026-11-07.md) finding F1

## Context / Problem

Every archive carries `codec_id[16]`, frozen by ADR-0007 as the literal string
`zstd-raw-l19`. Then ADR-0012 changed the default encode level to **9**, and nobody revisited
the string. Measured on `main` today:

```
lexora pack --in x --out y            # default level 9
lexora inspect --in y                 # codec zstd-raw-l19
```

Three consequences, in increasing order of seriousness:

1. **The metadata lies.** `inspect`, `--meta` and the GUI's About/inspect view all report a
   level that was not used.
2. **Level 9 and level 19 archives are indistinguishable.** Both carry the identical id, so
   "what produced this file?" cannot be answered from the file.
3. **It will get worse.** The registry (ADR-0014) now holds two codecs; an id that encodes a
   parameter of one of them is a precedent for the other to do the same.

## Decision drivers

- The field is **frozen by an accepted ADR**, so changing it is a format change and needs a
  record — this one — not an edit.
- **Archives already exist** (golden vectors, benchmark artifacts, anything a user packed), so
  the reader must keep accepting the old string. A rename that breaks old archives is
  unacceptable.
- **Determinism is a promise**: same input + level ⇒ byte-identical archive. Regenerating the
  golden vectors is therefore part of the change, not an accident of it.
- Cheap now, expensive later: the number of archives in the world grows monotonically.

## Options considered

- **A. Rename to a level-neutral id (`zstd-raw`) and read the old one as an alias.** *(recommended)*
  The id stops claiming a parameter; the reader accepts both, so nothing written yesterday
  breaks. Cost: golden vectors regenerate, one compatibility branch in `codec_registry`.
- **B. Keep the id, record the level in a spare header byte.** More information, but it means
  touching the frozen header layout and inventing a second source of truth about the level.
- **C. Document that the id is a codec *family* label, not a level.** Cheapest, honest, and
  still leaves two different archives looking identical.
- **D. Do nothing.** The status quo: every new archive repeats a false statement.

## Recommendation

**Option A, and now rather than at v0→v1.** "At the boundary" sounds free but is not: every
archive written between now and then carries the wrong id, and the migration code has to exist
either way. Doing it while `main` is pre-release and the golden vectors are one commit old is
strictly cheaper.

The mechanism, if accepted:

1. `codec_registry` gains `zstd-raw` as the writer's id, keeping `zstd-raw-l19` as a
   **read-only alias** — `by_registry_id` maps both to the same spec, so old archives decode.
2. `pack` writes the new id. **This changes archive bytes**, so it is a deliberate break of
   "byte-identical to before" and the test that asserts that must be updated to say *which*
   bytes changed and why.
3. Golden vectors regenerate; their README records the old and new digests side by side, so the
   change is auditable rather than a silent replacement.
4. `inspect` stops implying a level it cannot know.

## Consequences & trade-offs

**Positive.** The archive stops lying. Old archives keep working. One fewer parameter baked into
an identity field, which is what lets the registry grow.

**Negative / accepted risks.**

- **New archives differ from old ones byte-wise**, which matters to anyone comparing digests.
  Mitigated by recording both digests in the vectors README.
- **A compatibility branch lives forever** (or until v1 drops old reads). That is the normal
  cost of a frozen field, and it is smaller than the alternative of a second header field.
- **The level is still not recoverable from the archive** — renaming removes a false claim
  without adding a true one. If "what level produced this?" is wanted later, that is Option B's
  job and needs its own record.

## Impact analysis

| Dimension | Impact |
|---|---|
| Security | None |
| Performance | None |
| Compatibility | **New archives carry a new id.** Old archives stay readable. Any tool matching on the exact string must accept both |
| Operations | Golden vectors regenerate; CHANGELOG records a format-metadata change |

## Implementation & test implications

Not implemented — this record exists so the decision is one word away. When accepted: registry
alias + writer change + `_build_header` uses `spec.registry_id` (already true), vectors
regenerated, the byte-identity test rewritten to assert *which* bytes changed, and a test that an
archive written before the change still verifies.
