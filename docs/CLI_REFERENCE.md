# LEXORA CLI Reference

> **Status:** Implemented-scope reference — documents ONLY the subcommands that exist and are tested. No placeholders for planned commands (master-prompt rule: no misleading docs).
> **Owner:** Unassigned
> **Last verified:** 2026-10-16 against `src/lexora/cli.py` + `tests/test_cli.py` (Session 23)
> **Related:** [CANONICALIZATION.md](CANONICALIZATION.md) · [SPECIFICATION.md §8](SPECIFICATION.md) · [FORMAT_LXZ.md](FORMAT_LXZ.md) (PROPOSED — not implemented) · [STATUS.md](STATUS.md)

## Installation & invocation

The CLI ships with the `lexora` package (`pyproject.toml`, `[project.scripts]`):

```text
pip install -e ".[dev]"        # editable dev install (Python >=3.12,<4.0, ADR-0005)
lexora --help                  # console script
python -m lexora.cli --help    # equivalent, no install required
```

Version string: `lexora --version` → `lexora 0.0.1.dev1` (prototype; no stable API — see [RELEASE_PROCESS.md](RELEASE_PROCESS.md), no releases exist).

## Scope honesty

These three subcommands expose only the Phase-1 baseline flow (canonicalize + plain zstd frames). **There is no `pack`/`unpack` yet**: the `.lxz` container is blocked on owner acceptance of [ADR-0007](ADR/ADR-0007-container-v0-freeze.md) (tracked as OQ-11 in [DECISIONS.md](DECISIONS.md)); policy forbids implementing from PROPOSED FORMAT_LXZ (SPEC §7.2). Any command listed here exists and is covered by tests in `tests/test_cli.py`.

## Subcommands

### `lexora canon` — canonicalize raw bytes → canonical UTF-8

Applies the v0 rule set CAN-R01 (encoding normalization), CAN-R02 (CRLF/CR → LF), CAN-R05 (soft-hyphen removal); version `lexcan-0.1`. All other byte classes pass through unchanged (whitelist contract, REQ-CAN-003).

```text
lexora canon --in RAW --out CANONICAL [--encoding DECLARED]
```

| Flag | Required | Default | Meaning |
|---|---|---|---|
| `--in PATH` | yes | — | raw extracted-bytes file (`-` is not supported for input) |
| `--out PATH` | yes | — | output file; `-` writes to stdout (binary) |
| `--encoding NAME` | no | auto-detect | declared source codec; without it detection is BOM-sniff then strict UTF-8 — lossy guessing is refused (REQ-CAN-003) |

Behavior notes:
- Output is always UTF-8 without BOM, LF newlines (REQ-CAN-002).
- A summary line (`canon: N -> M bytes (rules ...; lexcAN-0.1)`) goes to **stderr**; data goes to the file/stdout only.

### `lexora zround` — zstd compress + verify byte-exact round-trip

Compresses a (already canonical) payload into one plain zstd frame (magic `28 B5 2F FD`), decompresses it back, and asserts byte equality before writing anything.

```text
lexora zround --in CANONICAL [--out FRAME] [--level N]
```

| Flag | Required | Default | Meaning |
|---|---|---|---|
| `--in PATH` | yes | — | payload file (bytes; normally canonical UTF-8) |
| `--out PATH` | no | `-` | frame destination; `-` skips writing |
| `--level N` | no | 19 | zstd level, enforced range 1..22 (outside range → exit 5) |

Behavior notes:
- The frame is written **only if** the decode-back comparison passes.
- Empty input is valid (exit 0; ratio reported as 1.0).
- `zround` compresses whatever bytes `--in` contains — it does not canonicalize. Feed it canonical output (`canon`/`pipe`) when the losslessness contract applies.
- Summary line (`zround: in=… compressed=… ratio=… roundtrip_exact=…`) goes to stderr.

### `lexora pipe` — end-to-end baseline flow

`raw bytes → canonicalize → compress → verify-decompress` in one command. This is the deliberate container-free pipeline (Session 20); cost accounting is printed so downstream audits can replay sizes.

```text
lexora pipe --in RAW [--out FRAME] [--encoding DECLARED] [--level N]
```

| Flag | Required | Default | Meaning |
|---|---|---|---|
| `--in PATH` | yes | — | raw file |
| `--out PATH` | no | `-` | zstd-frame destination; `-` skips writing |
| `--encoding NAME` | no | auto-detect | same semantics as `canon --encoding` |
| `--level N` | no | 19 | same semantics as `zround --level` |

Behavior notes:
- The frame contains the **canonical** bytes, not the raw bytes (decompressing yields `canonicalize(raw)`).
- Frame written only on byte-exact round-trip success.
- Cost line on stderr: `pipe: raw=N canonical=M compressed=K ratio_vs_raw=… ratio_vs_canonical=… roundtrip_exact=…`.

## Exit codes

Stable per this contract (all paths exercised by `tests/test_cli.py`):

| Code | Meaning | When |
|---|---|---|
| 0 | success | output written (or stdout) and round-trip verified where applicable |
| 2 | usage error | unknown/missing subcommand or missing required flag (argparse default) |
| 3 | input/output file error | cannot open/read input or write output (OSError) |
| 4 | canonicalization error | undecodable input without declaration, bad declared codec |
| 5 | codec error | corrupt/truncated frame, str-instead-of-bytes misuse, level outside 1..22 |
| 6 | round-trip verification failure | `decode(encode(C)) != C` — REQ-CMP-001 violation, blocker severity |

Note: these codes belong to the *implemented* CLI. The earlier proposed taxonomy in [ERROR_HANDLING.md](ERROR_HANDLING.md) predates the first real CLI; aligning that document with these codes is an open documentation item (this file is now the normative statement for the shipped commands).

## Planned but NOT implemented

| Command | Blocker |
|---|---|
| `lexora pack` / `lexora unpack` (`.lxz` container, P1-T3/P1-T5) | OQ-11 / [ADR-0007](ADR/ADR-0007-container-v0-freeze.md) owner decision |
| encryption, dictionaries, index/random-access flags | later phases per [ROADMAP.md](ROADMAP.md) |

Do not script against anything not listed above; anything else does not exist.
