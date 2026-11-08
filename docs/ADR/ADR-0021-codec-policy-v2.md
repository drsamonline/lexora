# ADR-0021: Codec policy v2 — PPMd is the max-ratio preset, CHCE becomes the extreme option

> **Status:** **WITHDRAWN 2026-11-08, hours after being accepted.** The measurement stands; the
> **codec does not**. `pyppmd`/`py7zr` PPMd **corrupts 3–8 % of real documents** depending on
> parameters, so `ppmd` was removed from the registry and **CHCE remains the max-ratio preset** per
> [ADR-0015](ADR-0015-codec-policy.md), which is un-superseded. The withdrawal evidence is at the
> end of this record — read it before proposing PPMd again.
> **Date:** 2026-11-08
> **Related:** [ADR-0015](ADR-0015-codec-policy.md) (the policy this amends) · [ADR-0014](ADR-0014-ziptastic-codec.md) (the registry) · [ADR-0020](ADR-0020-codec-id-naming.md) (why ids do not encode parameters) · [ECOSYSTEM_REVIEW_2026-11-08.md](../ECOSYSTEM_REVIEW_2026-11-08.md) (where PPMd came from)

## Context / Problem

ADR-0015 made CHCE (`ziptastic`) the documented max-ratio preset on the evidence available at
the time: **−19.75 % vs `xz -9`** on the project's own corpus class, against baselines of zstd,
xz and brotli.

The ecosystem review added a baseline that had never been measured — **PPMd**, which ADR-0003
names as a comparison point and which `pyppmd` exposes as a plain `pip install`. Measured per
file on the same 19-file / 18.5 MiB canonical corpus (per-file matters: concatenating lets one
model span every book and flatters every codec):

| codec | ratio | throughput | external binary |
|---|---|---|---|
| zstd-9 (default) | 0.3352 | 15.9 MiB/s | no |
| zstd-19 | 0.3059 | 1.4 MiB/s | no |
| `xz -9` | 0.3022 | 1.1 MiB/s | yes (CLI) |
| **PPMd order 6, 16 MiB** | **0.2283–0.2423** | **3.15–3.34 MiB/s** | **no** |
| CHCE `-9` | 0.2286–0.2425 | 0.48–0.50 MiB/s | yes |
| CHCE `-9 --max-ratio` | **0.2192** | **0.05 MiB/s** | yes |

(Ranges are two subsets of the same corpus; the ordering is identical in both.)

Three facts decide it:

1. **PPMd ties CHCE's default preset at ~7× the speed.** 0.2283 vs 0.2286 on the 4-file subset;
   0.2423 vs 0.2425 across all 19. That is not a ratio difference, it is measurement noise
   around a tie — and CHCE pays a 7× time penalty and a build dependency for it.
2. **CHCE's real edge is only in `--max-ratio`: 4 % smaller, at 0.05 MiB/s.** A 4 MB document
   takes 80 seconds; a 1 GB archive takes ~5.7 hours. That is an archival mode, not a preset.
3. **PPMd needs no external binary.** `pip install 'lexora[ppmd]'` and it works. The single
   biggest objection to CHCE — that it makes an external tool mandatory — does not apply.

ADR-0015's *principle* still holds and is untouched: **zstd stays the default**, because a
default must not cost 20× the encode time, and because the ratio case is a preset's job.

## Decision

The codec ladder becomes three points, each with a clear reason to exist:

| preset | codec | when | measured |
|---|---|---|---|
| **default** | `zstd` (level 9) | always; fast, no extras | 0.3352 @ 15.9 MiB/s |
| **max ratio** | **`ppmd`** (order 6, 16 MiB) | "smallest file, still usable" | **0.2283–0.2423 @ ~3.2 MiB/s** |
| **extreme** | `ziptastic --level 19` (CHCE `--max-ratio`) | archival, once, overnight | 0.2192 @ 0.05 MiB/s |

Concretely:

1. **PPMd is registered as codec `ppmd`, id `ppmd-1`** — a first-class codec, not a benchmark
   curiosity. It is an optional extra (`lexora[ppmd]`), like `pdf`, `ocr` and `gui`.
2. **The frame carries its model order.** PPMd decoded with the wrong order returns *wrong
   bytes without raising* (verified against `pyppmd`), so the order byte is part of the format
   and `mem_size` is fixed at 16 MiB for this id. Changing the memory budget is a **new codec
   id**, not a parameter — the same rule ADR-0020 established for the zstd id.
3. **CHCE is kept, not removed**, and documented as the extreme option. Deleting a working
   codec to make a table tidier is not a trade this project makes; demoting it is.
4. **`--level` means the model order for `ppmd`** (2..64, default 6) and the preset for
   `ziptastic` (9 or 19). Both are validated at the boundary as usage errors (ADR-0018).

## Consequences & trade-offs

**Positive.** The max-ratio preset is now 7× faster for the same bytes, needs no external
binary, and is one `pip install` away. Three codecs with three genuinely different
cost/ratio points, each defensible. The baseline table now contains the comparator the charter
always named.

**Negative / accepted risks.**

- **A third codec is a third surface.** Three ids, three sets of parameters, three failure
  modes. Mitigated by the registry (one dispatch point) and by the same test shape for each.
- **`pyppmd` is a compiled extension** (LGPL-2.1, wheels for common platforms). It is *not*
  pure Python, so a platform without a wheel needs a build toolchain — the same class of
  problem as `pyside6`, and the same answer: an optional extra with a clear refusal.
- **PPMd's parameters are inside the frame, so tuning is a format decision.** Order can be
  chosen per archive (it is recorded); memory cannot (it is fixed). That is deliberate and
  documented, but it does mean "PPMd with 256 MiB of memory" is a future codec id, not a flag.
- **CHCE keeps a 4 % edge nobody will usually take.** Fine: it is labelled with its speed, and
  the option exists for archives that are written once.

## Impact analysis

| Dimension | Impact |
|---|---|
| Security | One more decoder parsing untrusted input; per-block SHA-256 and the magic check both apply |
| Performance | max-ratio preset goes from 0.48 to ~3.2 MiB/s at the same ratio |
| Compatibility | Additive: a new id `ppmd-1`. Old readers refuse it (E-CMP-006) by design; no existing archive changes |
| Operations | New optional extra; `lexora doctor` should report whether it is present |

## Implementation & test implications

`src/lexora/ppmd_core.py` (frame = `PPMD` + order byte + stream; `validate_level` for the
2..64 range; `verify_roundtrip`), registered in `codec_registry` as `ppmd-1`, exposed as
`--codec ppmd`, extra `lexora[ppmd]`. `tests/test_ppmd_codec.py` — 22 tests, including the two
that matter: that a wrong order silently returns wrong bytes (asserted against `pyppmd`, so the
design constraint is re-checked rather than remembered), and that a **tampered order byte is
refused** rather than decoded into plausible garbage.

---

## WITHDRAWAL (2026-11-08, same day)

The codec was implemented, merged, and **withdrawn within the hour**, because testing it on a real
88-file library — not on a fixture — showed the library underneath it is broken.

**What failed.** Packing 88 canonicalised Gutenberg books, the container's own round-trip gate
refused the archive on **3 files**. Isolating the cause showed it is not my frame and not a
parameter choice — it is `pyppmd` itself:

| order (mem fixed 16 MiB) | files failing round-trip (of 88) |
|---|---|
| 6 | **7** |
| 9 | **3** |
| 16 | **7** |

Raw `pyppmd.compress` → `pyppmd.decompress` with identical parameters returns **corrupt data or
raises** on those inputs, with no frame of mine in the path. `py7zr`'s PPMd path — a different
wrapper around the same library — round-tripped 6 of 7 known-bad files and still failed one, so
routing through it is not a fix.

**The mistake, stated plainly.** The ratio measurements (0.2283–0.2423) are real — compressed
*size* is size — but I verified only sizes and never round-tripped the codec across varied real
input. The one fixture in the test file was 400 repetitions of the same sentence, which is
precisely the input least likely to expose a model-state bug. The container's verify-before-use
gate is what caught it, on the first realistic library anyone packed.

**What survives, and what does not.**

- **Survives:** PPMd as a *ratio baseline* — `ppmd-7z` in the harness, now with a **round-trip
  verification** so a ratio from a codec that cannot decode its own output is never recorded. The
  finding that PPMd is 18.4 % under `xz -9` and ~7× faster than CHCE at the same ratio is
  unaffected, and it is why OQ-18 is still worth someone's attention.
- **Does not survive:** PPMd as a shipped codec. `ppmd` is removed from the registry, the
  `lexora[ppmd]` extra is gone, and a test asserts it is not registered so it cannot come back
  without this record being read.
- **OQ-18 returns to "open, blocked"**: PPMd would be the better max-ratio preset *if a correct
  implementation existed*. Candidates for that: `7z` itself (the C++ binary, via subprocess — the
  same pattern as ziptastic), or PPMd in ziptastic. Both are real options; `pyppmd` is not.

**A second lesson, about the harness.** Its baselines measure **raw** file bytes while lexora
packs **canonicalised** bytes, so the corruption did not reproduce in the harness row for the
same file — canonicalisation changes the exact input. That is correct by design (baselines see
raw input) but it means a baseline can pass verification while the codec path fails. Worth
knowing before anyone reads a green harness row as proof the codec is sound.
