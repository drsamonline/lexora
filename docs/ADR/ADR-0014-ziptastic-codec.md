# ADR-0014: A second codec — ziptastic (CHCE) behind a codec registry

> **Status:** **Accepted 2026-11-07** — implemented and tested in this change. The registry and the zstd default are settled; the *default-codec* question is deliberately **not** decided here (see "Not decided here").
> **Date:** 2026-11-07
> **Deciders:** Owner Dr Sohil Momin (delegated to this record, same pattern as ADR-0007/0010/0012)
> **Related:** [ADR-0007](ADR-0007-container-v0-freeze.md) (codec_id field) · [ADR-0002](ADR-0002-brotli-role.md) (codec_id space holds Zstd + promoted candidates) · [ADR-0012](ADR-0012-default-encode-level.md) (default level 9) · [ZIPTASTIC_NOTES.md](../ZIPTASTIC_NOTES.md) · [AUDIT_2026-11-07.md](../AUDIT_2026-11-07.md)

## Context / Problem

Three facts, each already measured in this project or its sibling:

1. **The ratio gap is structural, not a tuning problem.** R5 put LEXORA at ratio **0.3101** against zstd-19 **0.3120** (−0.60 %) and `xz -9` **0.3077** (+0.77 % *worse* than xz). BENCHMARK_RESULTS' own conclusion: "v0 is canonicalization + zstd, so it cannot pass xz by tuning zstd — which is what the roadmap's PPMd/Brotli/dictionary phases exist for."
2. **A stronger backend already exists and is ours.** ziptastic (CHCE) measures **11.83 % under `xz -9`** on a 10-file, 119,259,397-byte Silesia subset — and the per-file split shows where: `reymont` −22.2 %, `mr` −18.2 %, `osdb` −17.6 %, `xml` −17.3 %, `dickens` −16.8 %, `nci` −16.7 %. Text, prose and XML are exactly lexora's corpus class. `samba` −0.64 % and `sao` −0.001 % show the win is *concentrated*, not universal.
3. **The container was already codec-agnostic on paper and not in code.** `codec_id[16]` sits in the header (ADR-0007), but `container.py` hard-coded zstd in five places: the id written into the header, the reader's accept-list, and three separate `b"\x28\xB5\x2F\xFD"` frame-magic checks. "Swap the backend" was a claim, not a switch.

## Decision drivers

- **Ratio is the product's reason to exist**, and the backend is the largest single lever on it.
- **Reader safety first.** Any new codec id must be refused by older readers (that is what a must-understand field is for), and must never be silently substituted.
- **No new mandatory dependency.** A base install must keep working with zstd alone; the CHCE binary is optional.
- **Honesty in metadata.** An archive must say what compressed it, and a codec that lies about its identity is worse than no codec.
- **Reversibility.** Adding a codec must not change one byte of a default `pack`.

## Decision

1. **A codec registry** — `src/lexora/codec_registry.py` — is the single mapping from CLI name to header `codec_id` to implementation (`compress`/`decompress`/`magic`). `container.py` dispatches through it; no codec is named anywhere else.
2. **`CODEC_ID_ZIPTASTIC = "ziptastic-1"`** is registered alongside `CODEC_ID_ZSTD`. New id, never a reuse: the reader dispatches on this string, so an archive packed with CHCE says so, and an older reader refuses it with **E-CMP-006** rather than attempting a zstd decode.
3. **`--codec {zstd,ziptastic}`** on `pack` and `batch`. `unpack`, `verify`, `inspect` take **no flag** — the header already says which codec was used, and a flag that could disagree with the header would be a way to get the answer wrong.
4. **zstd stays the default.** Nothing about existing behaviour changes; `pack()` with no arguments produces byte-identical output to before (asserted by a test).
5. **The adapter shells out; it does not reimplement.** `src/lexora/ziptastic_core.py` runs `ziptastic c -9` / `ziptastic d` as stdin→stdout filters (contract read from `src/main.cpp`, not guessed), requires the `CHCE` magic on the way out, and refuses on a non-zero exit, a missing binary, or a wrong decode length.
6. **No silent fallback.** If the binary is absent, `--codec ziptastic` fails with a message naming `$LEXORA_ZIPTASTIC` and `--codec zstd`. Falling back would write an archive whose header lies.

## Consequences & trade-offs

**Positive.** The ratio lever is now a switch rather than a project. The "codec-agnostic container" claim is true of the code, not just the layout. Two codecs exercise the reader's dispatch path, which is where a format bug would otherwise sit untested until the second codec arrives.

**Negative / accepted risks.**

- **Speed.** CHCE runs at 0.3–0.6 MB/s at `-9`, one process per block: ~15–25 s for an 8 MiB block. This is a max-ratio path, not a default, and `--codec ziptastic` should be chosen deliberately.
- **Determinism is per binary, not per format.** LEXORA promises "same input + level ⇒ byte-identical archive". The adapter only ever uses CHCE's **serial** path (ziptastic's own assessment says the parallel path's determinism is unchecked), so the promise holds *for a pinned ziptastic binary*. The registry id `ziptastic-1` does **not** encode the binary version, so reproducibility across machines requires pinning the binary, and a future CHCE format change needs a new id (`ziptastic-2`).
- **`--level` semantics differ.** ziptastic has two presets, not a 1..22 scale: `level=9` → `-9`, `level=19` → `-9 --max-ratio`. Any other value is refused rather than rounded, because a silently-rounded level puts a false number in the benchmark record.
- **Unmeasured on this project's corpus.** The 11.83 % is ziptastic's number on a Silesia subset. Whether it transfers to lexora's Gutenberg corpus is a **hypothesis**, and the two largest Silesia files (`webster` 41 MiB, a dictionary; `mozilla` 51 MiB, binary) are unmeasured in ziptastic itself. No claim is made here about lexora's ratio with CHCE.

**Not decided here.** Whether ziptastic becomes the **default** codec, or a documented "max ratio" preset. That needs a measurement on lexora's own corpus through this seam — the same standard ADR-0012 applied to the level sweep. A default change is a one-line edit to `codec_registry.DEFAULT_CODEC` once the numbers exist.

## Impact analysis

| Dimension | Impact |
|---|---|
| Security | Positive: one dispatch point; unknown ids still refused (E-CMP-006); a wrong binary fails loudly instead of producing an undecodable archive |
| Performance / memory | Unchanged by default (zstd). With `--codec ziptastic`: ~15–25 s per 8 MiB block, memory still one block |
| Compatibility (format/spec) | `codec_id` gains a second legal value. Archives written with it are refused by pre-ADR-0014 readers — by design. Default archives are byte-identical |
| Operations | New optional external dependency, discoverable via `lexora doctor` |

## Implementation & test implications

Landed: `codec_registry.py`, `ziptastic_core.py`, `CODEC_ID_ZIPTASTIC`, container dispatch (pack, pack_stream, unpack, unpack_stream, verify_stream, `_build_header`, `_validate_header`), `--codec` on `pack`/`batch`, a `ziptastic codec` row in `doctor`, and `tests/test_ziptastic_codec.py` (25 tests). The real binary is not vendored, so the adapter is tested against a stub that speaks the documented contract; the one test that needs the real binary is `skipif`-guarded and says so when it skips. **The stub proves the seam, not the ratio** — no test here asserts anything about compression quality, and none could.
