# `.lxz` v0 golden vectors

Normative layout: [../../../docs/ADR/ADR-0007-container-v0-freeze.md](../../../docs/ADR/ADR-0007-container-v0-freeze.md) (Accepted 2026-10-16, LXZ-0.1).

| File | Build recipe | SHA-256 |
|---|---|---|
| `golden_1byte.lxz` | `pack(b"x", level=19, generator_version="lexora-golden")` (zstandard library version recorded in env capture) | 27877df54dcb024bb9cdc338f37539930c6dde534e7406219c402fb8c4b705e9 |

Regenerate ONLY alongside a format-version bump + superseding ADR (SPEC §10.2).
`tests/test_container_lxz.py::TestGoldenVectors` pins both the file bytes and the archive digest.
