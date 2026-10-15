"""Minimal real CLI for the Phase-1 baseline: canonicalize + zstd round-trip.

Honesty note: this is NOT the `.lxz` pack/unpack CLI (P1-T5, not started —
FORMAT_LXZ.md is PROPOSED and must not be implemented from). These two
subcommands expose only what is actually implemented and tested:
  lexora canon  --in RAW --out CANONICAL [--encoding DECLARED]
  lexora zround --in CANONICAL [--level N] [--check]

Exit codes (tested in tests/test_cli.py):
  0 success
  2 usage error (argparse default)
  3 input/output file error
  4 canonicalization error (bad/undeclared encoding)
  5 codec error (corrupt frame, bad level, str input)
  6 round-trip verification failure (REQ-CMP-001 violation -> blocker)
"""

from __future__ import annotations

import argparse
import sys

from lexora import __version__
from lexora.canonicalize import CanonicalizationError, canonicalize
from lexora.zstd_core import CodecError, compress, decompress

EXIT_OK = 0
EXIT_FILE = 3
EXIT_CANON = 4
EXIT_CODEC = 5
EXIT_ROUNDTRIP = 6


def _read(path: str) -> bytes:
    try:
        with open(path, "rb") as fh:
            return fh.read()
    except OSError as exc:
        print(f"error: cannot read {path}: {exc}", file=sys.stderr)
        raise SystemExit(EXIT_FILE)


def _write(path: str, data: bytes) -> None:
    try:
        with open(path, "wb") as fh:
            fh.write(data)
    except OSError as exc:
        print(f"error: cannot write {path}: {exc}", file=sys.stderr)
        raise SystemExit(EXIT_FILE)


def cmd_canon(args: argparse.Namespace) -> int:
    raw = _read(args.infile)
    try:
        out = canonicalize(raw, declared_encoding=args.encoding)
    except CanonicalizationError as exc:
        print(f"canonicalization error: {exc}", file=sys.stderr)
        return EXIT_CANON
    if args.outfile == "-":
        sys.stdout.buffer.write(out)
    else:
        _write(args.outfile, out)
    print(
        f"canon: {len(raw)} -> {len(out)} bytes "
        f"(rules CAN-R01,R02,R05; lexcAN-0.1)",
        file=sys.stderr,
    )
    return EXIT_OK


def cmd_zround(args: argparse.Namespace) -> int:
    payload = _read(args.infile)
    try:
        blob = compress(payload, level=args.level)
    except CodecError as exc:
        print(f"codec error: {exc}", file=sys.stderr)
        return EXIT_CODEC
    try:
        back = decompress(blob, expected_original_size=len(payload))
    except CodecError as exc:
        print(f"codec error on decode: {exc}", file=sys.stderr)
        return EXIT_CODEC
    exact = back == payload
    ratio = (len(blob) / len(payload)) if payload else 1.0
    print(
        f"zround: in={len(payload)} compressed={len(blob)} "
        f"ratio={ratio:.4f} roundtrip_exact={exact}",
        file=sys.stderr,
    )
    if not exact:
        return EXIT_ROUNDTRIP  # REQ-CMP-001 violation: blocker severity
    if args.outfile != "-":
        _write(args.outfile, blob)
    return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="lexora",
        description=(
            "LEXORA prototype CLI (Phase 1 baseline only; no .lxz container yet)."
        ),
    )
    p.add_argument("--version", action="version", version=f"lexora {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("canon", help="canonicalize raw bytes -> canonical UTF-8")
    c.add_argument("--in", dest="infile", required=True)
    c.add_argument("--out", dest="outfile", required=True, help="'-' for stdout")
    c.add_argument("--encoding", default=None, help="declared source encoding")
    c.set_defaults(func=cmd_canon)

    z = sub.add_parser("zround", help="zstd compress + verify byte-exact roundtrip")
    z.add_argument("--in", dest="infile", required=True)
    z.add_argument("--out", dest="outfile", default="-", help="'-' to skip writing")
    z.add_argument("--level", type=int, default=19)
    z.set_defaults(func=cmd_zround)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
