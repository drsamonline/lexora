# ADR-0018: An out-of-range codec parameter is a usage error (exit 2), on every surface

> **Status:** **Accepted 2026-11-07** — decided under owner delegation ("p2.3a u decide").
> **Date:** 2026-11-07
> **Deciders:** Owner Dr Sohil Momin (delegated to this record)
> **Related:** [ADR-0011](ADR-0011-gui-process-separation.md) (the parity claim this makes true) · [ADR-0012](ADR-0012-default-encode-level.md) (the level itself) · [CLI_REFERENCE.md](../CLI_REFERENCE.md) (exit-code table) · [PATH_TO_V1.md](../PATH_TO_V1.md) P2.3a

## Context / Problem

Moving the GUI onto the CLI (P2.3, the open half of ADR-0011) requires the two surfaces to
agree on what a failure *is*. They did not. Measured on 2026-11-07:

```
lexora pack --in x --out y --level 99     -> exit 5   (codec error)
AppService.run_pack(b"...", level=99)     -> exit 2   (usage error)
```

`gui/service.py` carried the comment "mirrors `lexora zround/pipe/pack --level`" next to code
that returned 2 — so the comment described an intention the CLI never implemented. Nobody had
noticed because no test compared the two, and because the GUI's value was only ever exercised
with valid levels.

Three facts decided it rather than taste:

1. **The same command already disagreed with itself.** `pack --block-size 0` returns **2**.
   `pack --level 99` returned **5**. Two out-of-range flags, one command, two codes.
2. **Exit 5 asserts something false.** `EXIT_CODEC` means "the codec failed". With `--level 99`
   the codec was never called with a level it could accept — the failure happened before any
   codec work, and no archive was attempted.
3. **The user's action is the same either way:** fix the flag. That is what a usage error is
   for, and 2 is what this CLI already means by it everywhere else.

## Decision

1. **An illegal `--level` exits 2** on every verb that accepts it — `pack`, `batch`, `zround`,
   `pipe` — and on both codecs.
2. **The codec owns the rule, the CLI applies it.** `CodecSpec` gained `validate_level`, supplied
   by each codec module: zstd accepts 1..22, ziptastic accepts only its two presets (9, 19).
   Putting the range in one place is what stops the CLI and the GUI drifting again.
3. **Validation happens at the boundary, before any I/O** — the same ordering `--block-size`
   already had.
4. **The GUI keeps returning 2**, so no GUI code changes: this ADR moves the CLI to where the
   GUI already was, which is the direction that removes work rather than adding it.
5. **`EXIT_CODEC` (5) keeps its meaning** for genuine codec failures: a corrupt frame, a level
   the *library* rejects mid-operation, a missing ziptastic binary.

## Consequences & trade-offs

**Positive.** One answer per mistake. The GUI↔CLI parity claim in ADR-0011 becomes true rather
than aspirational, so P2.3 is now mechanical. Scripts that branched on `5` for a typo'd level
will now see `2` — which is the more accurate signal, and no released version exists to break.

**Negative / accepted risks.**

- **A behaviour change for anyone scripting the CLI.** Mitigated by there being no release yet
  and by the change making the code *more* correct; recorded in the CHANGELOG as a change, not a
  fix, because callers may notice.
- **Two validation layers.** The codec still refuses a bad level internally (`CodecError`); the
  CLI now also refuses it earlier. That is deliberate belt-and-braces — the library must not
  depend on its caller having validated — but it means the message exists in two forms, and the
  tests assert both paths.

## Impact analysis

| Dimension | Impact |
|---|---|
| Security | None |
| Performance | One integer comparison before I/O |
| Compatibility | CLI exit code changes 5 → 2 for an illegal `--level`; no format or archive change |
| Operations | Scripts checking for 5 on a typo must check 2; the exit-code table in CLI_REFERENCE is unchanged in structure |

## Implementation & test implications

`CodecSpec.validate_level` (registry), `zstd_core.validate_level`, `ziptastic_core.validate_level`,
`cli._level_usage_error` applied in `cmd_pack`, `cmd_batch`, `cmd_zround`, `cmd_pipe`.
`tests/test_level_usage.py` — 23 tests: every verb × out-of-range values, valid levels still
work, ziptastic presets enforced, `--block-size` and `--level` now agree within one command, and
a parity test asserting the CLI and `AppService` return the same code for the same bad level.
