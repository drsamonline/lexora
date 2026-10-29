# LEXORA CLI Reference

> **Status:** Implemented-scope reference — documents ONLY the subcommands that exist and are tested. No placeholders for planned commands (master-prompt rule: no misleading docs).
> **Owner:** Unassigned
> **Last verified:** 2026-10-16 against `src/lexora/cli.py` + `tests/test_cli.py` + `tests/test_container_lxz.py` (Session 24)
> **Related:** [CANONICALIZATION.md](CANONICALIZATION.md) · [SPECIFICATION.md §8](SPECIFICATION.md) · [FORMAT_LXZ.md](FORMAT_LXZ.md) (layout now normative per accepted [ADR-0007](ADR/ADR-0007-container-v0-freeze.md)) · [STATUS.md](STATUS.md)

## Installation & invocation

The CLI ships with the `lexora` package (`pyproject.toml`, `[project.scripts]`):

```text
pip install -e ".[dev]"        # editable dev install (Python >=3.12,<4.0, ADR-0005)
lexora --help                  # console script
python -m lexora.cli --help    # equivalent, no install required
```

Version string: `lexora --version` → `lexora 0.0.1.dev1` (prototype; no stable API — see [RELEASE_PROCESS.md](RELEASE_PROCESS.md), no releases exist).

## Scope honesty

Six subcommands exist: the three Phase-1 baseline flows (canonicalize + plain zstd frames), `pack`/`unpack` for the `.lxz` v0 container (unblocked by ADR-0007 acceptance, Session 24, under standing owner delegation), and `verify` (Session 47) for auditing an archive without producing payload bytes. The container is **experimental** (major 0): byte layout frozen per ADR-0007 but pre-release. Any command listed here exists and is covered by tests (`tests/test_cli.py`, `tests/test_container_lxz.py`).

## Subcommands

### `lexora canon` — canonicalize raw bytes → canonical UTF-8

**Memory behaviour (Session 45).** `canon` streams by default: one decoded chunk plus a one-character carry (for a CRLF split across the boundary), so peak RSS is flat in document size — measured 35.5 MiB at both a 16 MiB and a 64 MiB document. `--no-stream` restores the pre-Session-45 whole-file path (216.2 MiB at 64 MiB). Output is byte-identical either way and both raise the same `CanonicalizationError` text, so exit code 4 is unchanged.

Applies the v0 rule set CAN-R01 (encoding normalization), CAN-R02 (CRLF/CR → LF), CAN-R05 (soft-hyphen removal); version `lexcan-0.1`. All other byte classes pass through unchanged (whitelist contract, REQ-CAN-003).

```text
lexora canon --in RAW --out CANONICAL [--encoding DECLARED] [--meta]
```

| Flag | Required | Default | Meaning |
|---|---|---|---|
| `--in PATH` | yes | — | raw extracted-bytes file (`-` is not supported for input) |
| `--out PATH` | yes | — | output file; `-` writes to stdout (binary) |
| `--encoding NAME` | no | auto-detect | declared source codec; without it detection is BOM-sniff then strict UTF-8 — lossy guessing is refused (REQ-CAN-003) |
| `--meta` | no | off | print audit JSON (canonicalizer version, applied rules, input/output sizes, SHA-256 of both) to **stdout instead of payload bytes**; payload goes only to `--out` (with `--meta`, `--out -` suppresses payload entirely so stdout stays pure JSON) — added Session 25 |

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

### `lexora pack` — wrap canonical bytes into a `.lxz` v0 archive

Implements the ADR-0007 frozen layout (LXZ-0.1): 128-byte header (full SHA-256 over bytes [0,96)), blocks each exactly one complete zstd frame, 56-byte index entries `{u64 offset; u64 compressed; u64 uncompressed; sha256[32]}`, 40-byte trailer `{u64 index_offset; u64 index_bytes; sha256-prefix[24]}`. Every block is decode-verified before the archive is written (SPEC §8.1); the write itself is atomic (temp + fsync + rename).

```text
lexora pack --in CANONICAL --out ARCHIVE.lxz [--level N] [--block-size B]
```

| Flag | Required | Default | Meaning |
|---|---|---|---|
| `--in PATH` | yes | — | payload file (normally `canon` output; `pack` does not canonicalize) |
| `--out PATH` | yes | — | archive destination; `-` writes to stdout (binary) |
| `--level N` | no | 19 | zstd level 1..22 (same contract as `zround`) |
| `--block-size B` | no | 8388608 | max uncompressed bytes per block, legal range 1..8388608 (LIM-01); out-of-range → exit 2 before any read/write (Session 26 bounds messaging); declared in header and enforced by readers |
| `--no-stream` | no | off (streaming) | buffer the whole input in memory instead of streaming block-by-block. Same output bytes, far higher peak RSS (measured 196.9 MiB vs 126.1 MiB at a 32 MiB input, Session 39) — kept for A/B evidence runs only |

Behavior notes: empty input packs as one zero-length block (exit 0); summary line on stderr.

**Memory behaviour (Session 39).** `pack` streams by default: `container.pack_stream()` holds one block plus its compressed frame, so peak RSS is flat in document size (measured plateau ≈126 MiB at zstd-19/8 MiB blocks, from one full block upward — `benchmarks/results-rss-core.json`). The pre-Session-39 buffered path grew ~4.8 MiB of peak RSS per MiB of input, which put the 512 MiB encode budget (PERFORMANCE_BUDGET.md) at risk on a ~95 MiB document. `--out -` (stdout) still takes the buffered path, because streaming needs a seekable destination for the header backfill.

### `lexora unpack` — decode a `.lxz` archive, refusing unverified output

**Memory behaviour (Session 41).** `unpack` streams by default: the index is validated up front, then blocks are decoded one at a time and written as they verify, so peak RSS is flat in archive size (measured ≈34 MiB at both 32 MiB and 64 MiB archives — `benchmarks/results-rss-core.json`). `--no-stream` restores the pre-Session-41 whole-archive path (~2.8 MiB peak per MiB of archive). Either way the refusal guarantee is intact: nothing reaches `--out` (or stdout) unless every block verified, because the payload is staged in a temp file and only then renamed or copied.

Validates header hash → limits/index consistency → per-block zstd decode → per-block SHA-256, all *before* any output byte is emitted (REQ-SEC-001/004). Any refusal ⇒ exit 7, **no output file created**.

```text
lexora unpack --in ARCHIVE.lxz [--out CANONICAL] [--block N] [--meta] [--no-stream]
```

| Flag | Required | Default | Meaning |
|---|---|---|---|
| `--in PATH` | yes | — | archive file |
| `--out PATH` | no | `-` | decoded payload destination; `-` writes to stdout |
| `--block N` | no | all | bounded single-block decode (REQ-CMP-005) |
| `--meta` | no | off | print index metadata JSON to stdout instead of payload bytes; index only — no block is read or decoded (Session 41) |
| `--no-stream` | no | off (streaming) | buffer the whole archive and output in memory instead of decoding block-by-block; same output bytes, ~3.3× the peak RSS at a 32 MiB archive |

### `lexora verify` — audit an archive without writing payload bytes

Answers "is this archive intact?" without producing output, and without holding the archive in memory: the index is validated first (header checksum, flags, codec id, index/trailer consistency, limit checks), then every block is decoded and its SHA-256 checked against the index. Verification is **best-effort per block** — one corrupt block does not stop the report, because an audit should tell you how much is salvageable, not merely that something is wrong (ADR-0007 per-block semantics).

```text
lexora verify --in ARCHIVE.lxz [--block N] [--json]
```

| Flag | Required | Default | Meaning |
|---|---|---|---|
| `--in PATH` | yes | — | archive to audit |
| `--block N` | no | all | verify a single block (bounded, REQ-CMP-005) |
| `--json` | no | off | print the full per-block report to stdout |

Exit codes: **0** everything verified; **7** a refusal (bad header/index/limits) or any failed block — the same code the reader uses, so scripts can treat "bad archive" uniformly; **3** unreadable input. Nothing is ever written to `--out`, because there is no `--out`.

Library equivalent: `container.verify_stream(handle)` — and `verify_archive(bytes)` is now a thin wrapper over it, so a verification costs one pass over the archive instead of one pass *per block*.

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
| 7 | container refusal | `.lxz` format/integrity/limit refusal with specific `E-*` code (ADR-0007 reader); distinct from 5 so "codec library failed" ≠ "archive refused by format rules" |

Reconciliation note (Session 24; **formally adopted into [ERROR_HANDLING.md](ERROR_HANDLING.md) global rule 5, Session 25**): that file's originally proposed taxonomy (0/1/2/3/4/5/6) predates the real CLI; this file's table is normative for shipped behavior. Adopted mapping: E-USAGE→2, E-IO→3, E-INPUT-ENC/E-CAN→4, E-CMP(decode-level)→5, E-CMP-001 round-trip→6, E-FMT-*/E-RES-*/E-INTEGRITY-*→7, E-INT→5 reserved-with-context-log. Codes are carried verbatim in `ContainerError.code`. One deliberate deviation from the original proposal: argparse emits exit 2 for usage errors (not 1), so the shipped space has no exit 1.

## Planned but NOT implemented

| Feature | Status |
|---|---|
| encryption, dictionaries, multi-document indexes, random access | later phases per [ROADMAP.md](ROADMAP.md) — must-understand flag bits reserved (ADR-0007) |
| batch/quarantine semantics (per-document runs) | needs SPEC rule-table freeze; `unpack_blocks()` library API already gives per-block granularity |

Do not script against anything not listed above; anything else does not exist.
