# `.lxz` v0 golden vectors

Normative layout: [../../../docs/ADR/ADR-0007-container-v0-freeze.md](../../../docs/ADR/ADR-0007-container-v0-freeze.md) (Accepted 2026-10-16, LXZ-0.1).

| File | Build recipe | SHA-256 |
|---|---|---|
| `golden_1byte.lxz` | `pack(b"x", level=19, generator_version="lexora-golden")` | `08288a397f920a12d23ab8269fd1f70b84edbbc234cf4554067847410ea69351` |
| `golden_1byte_legacy_l19.lxz` | the same bytes as written **before** ADR-0020, when the header id was `zstd-raw-l19` | `27877df54dcb024bb9cdc338f37539930c6dde534e7406219c402fb8c4b705e9` |

Regenerate ONLY alongside a format-version bump + superseding ADR (SPEC §10.2).
`tests/test_container_lxz.py::TestGoldenVectors` pins both the file bytes and the archive digest.

## ADR-0020 — the id changed, the layout did not (2026-11-08)

`codec_id` went from `zstd-raw-l19` to the level-neutral **`zstd-raw`**, because the old value
named a level the archive was not necessarily compressed at (ADR-0012 moved the default to 9).
**The byte layout is unchanged** — same 128-byte header, same 56-byte index entries, same
trailer — so this is a metadata change, not a format revision.

Both digests are recorded above on purpose. The legacy file is kept as a **fixture**, not
history: it is an archive written by the previous code, and a test asserts it still verifies
and still reports its own id. Deleting it would leave backward compatibility untested, and the
whole point of the alias is that old archives keep working.

Diff between the two files, for audit: 16 bytes inside the header (the id field) and the 32-byte
header checksum that covers them. Nothing else changes.
