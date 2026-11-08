# ADR-0015: Codec policy — zstd stays the default, CHCE is the max-ratio preset

> **Status:** **Accepted 2026-11-07** — explicit owner decision ("zstd default and chce max ratio"), not a delegation. Closes **OQ-16**.
> **Date:** 2026-11-07
> **Deciders:** Owner Dr Sohil Momin
> **Related:** [ADR-0014](ADR-0014-ziptastic-codec.md) (the seam this policy steers) · [ADR-0012](ADR-0012-default-encode-level.md) (the same shape of decision, for level) · [CHCE_SMOKE_2026-11-07.md](../CHCE_SMOKE_2026-11-07.md) (the measurement) · [BENCHMARK_RESULTS.md](../BENCHMARK_RESULTS.md) (R4/R5, the position CHCE changes)

## Context / Problem

ADR-0014 added a second codec and deliberately left the default alone, because the only
ratio evidence for CHCE was ziptastic's own Silesia subset — not this corpus. That left
**OQ-16** open: should CHCE become the default, or stay an opt-in preset?

The measurement that answers it (Session 71, smoke scope — `docs/CHCE_SMOKE_2026-11-07.md`):
on 19 Gutenberg texts, 19,432,350 canonical bytes, every codec on identical input,

| codec | total | ratio | measured throughput |
|---|---|---|---|
| zstd-9 (shipped default) | 6,514,541 | 0.3352 | 15.9 MiB/s |
| zstd-19 | 5,944,104 | 0.3059 | — |
| `xz -9` | 5,871,796 | 0.3022 | 1.08 MiB/s |
| **CHCE `-9`** | **4,712,272** | **0.2425** | **0.50 MiB/s** |

CHCE is **−19.75 % vs `xz -9`** and −27.67 % vs zstd-9, smaller on **19 of 19** files.
Against the project's own published position (R5: +0.77 % *worse* than `xz -9`) that is a
swing of roughly twenty points, and about twice ADR-0001's ≥10 % Pass threshold.

So the ratio argument for making CHCE the default is strong. The counter-arguments are
not about ratio at all.

## Decision drivers

- **A base install must not need an external binary.** Today `pip install lexora` needs
  only `zstandard`, a wheel. CHCE as a *default* would make a 2.2 MB platform-specific
  binary, built elsewhere, on `PATH` a precondition for the tool working at all — on every
  OS lexora supports, including ones ziptastic does not build for.
- **A default must be the safe choice, not the best choice.** A default that silently
  costs 30× the encode time is a bad first impression for the 90 % of uses that are
  "compress this file now".
- **The evidence is smoke scope.** 19 files, one corpus class, no held-out split. A
  default change is the one codec decision that cannot be undone for archives already
  written, so it should follow the protocol run, not precede it.
- **Discoverability beats silent substitution.** A user who wants 20 % more compression
  should be able to ask for it, and should know the time cost before they do.

## Decision

1. **`DEFAULT_CODEC` stays `zstd`.** `lexora pack` with no flag behaves exactly as it did
   before ADR-0014 — no new dependency, no new failure mode, byte-identical output.
2. **CHCE is the documented max-ratio preset**: `--codec ziptastic` on `pack` and
   `batch`, named as such in `CLI_REFERENCE.md`, in `--help`, and reported by
   `lexora doctor`.
3. **No automatic codec selection in v0.** lexora will not pick a codec for the user by
   inspecting the input; the choice is explicit and recorded in the archive header.
4. **The default is revisited only after a protocol-scope CHCE run** on the R4/R5 corpus,
   and then by amending this ADR — not by editing a constant.

## Consequences & trade-offs

**Positive.** The base install stays dependency-free and fast. The ratio lever is
available, documented, and honest about its cost. The archive header always says which
codec was used, so a max-ratio archive opened on a machine without the binary fails with
a message naming the codec rather than a decode error.

**Negative / accepted risks.**

- **The better codec is not the default**, so most users will never see the 20 %. Accepted:
  discoverability is a documentation problem, and `--codec ziptastic` is one flag.
- **Two codecs to keep working.** The reader dispatches on `codec_id`, and both paths are
  covered by the suite — but a future format change now has two implementations to migrate.
- **Reproducibility is per binary.** A CHCE archive is byte-identical for a pinned
  ziptastic binary only; the registry id `ziptastic-1` does not encode the binary version
  (ADR-0014 records this). zstd archives do not have this caveat, which is a quiet
  argument for the default staying where it is.

## Impact analysis

| Dimension | Impact |
|---|---|
| Security | None new: the default path gains no subprocess. The opt-in path already refuses a missing/foreign binary |
| Performance / memory | Default unchanged (zstd-9, ~16 MiB/s). Opt-in: ~0.5 MiB/s, memory still one block |
| Compatibility | None — default archives are byte-identical to pre-ADR-0014 output |
| Operations | `lexora doctor` reports the binary; absence is INFO, not a fault |

## Implementation & test implications

No code change: this ADR ratifies what ADR-0014 already shipped (`codec_registry.DEFAULT_CODEC
= "zstd"`, `--codec` on `pack`/`batch`, a `ziptastic codec` row in `doctor`). The tests that
hold it: `test_default_codec_is_zstd` (the constant), `test_default_pack_is_still_byte_identical_zstd`
(no byte drift in default output), and the CLI help/`doctor` surfaces that make the preset
discoverable. **The next change to `DEFAULT_CODEC` should fail this ADR's review, not just
a test.**

## Post-decision note (2026-11-08)

This ADR chose CHCE as the max-ratio preset on the evidence available: **−19.75 % vs `xz -9`**,
measured on the project's own corpus class. A later measurement added a baseline that was not in
the table — **PPMd** via `py7zr`/`pyppmd`, which the charter named (ADR-0003) and nobody had
measured:

| codec | ratio | throughput | external binary |
|---|---|---|---|
| PPMd (7z) | 0.2466 | 2.43 MiB/s | none (`pip install`) |
| CHCE `-9` | 0.2425 | 0.50 MiB/s | yes |

CHCE is **1.7 % smaller for 5× the encode time** and a build dependency. That does not make this
ADR wrong — the decision was sound for its evidence — but it does mean the preset question is
open again as **OQ-18**, and `ppmd-7z` is now a harness system so the protocol run settles it.
