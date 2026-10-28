"""LEXORA prototype CLI (Phase 1 baseline + .lxz v0 container per ADR-0007).

Subcommands:
  lexora canon   --in RAW --out CANONICAL [--encoding DECLARED]
  lexora zround  --in CANONICAL [--out FRAME] [--level N]
  lexora pipe    --in RAW --out FRAME [--encoding DECLARED] [--level N]
                 (end-to-end baseline flow: canonicalize -> compress ->
                  verify byte-exact round-trip; writes frame only on success)
  lexora pack    --in CANONICAL --out ARCHIVE.lxz [--level N] [--block-size B]
                 (.lxz v0 per accepted ADR-0007; every block verified before
                  the archive is written; atomic write: temp file + rename,
                  ERROR_HANDLING recovery semantics)
  lexora unpack  --in ARCHIVE.lxz --out CANONICAL [--block N] [--meta]
                 (writes ONLY verified bytes; refuses with a specific error
                  and zero output on integrity/limit/format failure)

Exit codes (tested in tests/test_cli.py):
  0 success
  2 usage error (argparse default)
  3 input/output file error
  4 canonicalization error (bad/undeclared encoding)
  5 codec error (corrupt frame, bad level, str input)
  6 round-trip verification failure (REQ-CMP-001 violation -> blocker)
  7 container refusal (E-FMT/E-RES/E-INTEGRITY per ADR-0007 reader) — kept
    distinct from 5 so callers can tell "codec library failed" from "archive
    refused by format rules"; documented in docs/CLI_REFERENCE.md.
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile

from lexora import __version__
from lexora.canonicalize import CanonicalizationError, canonicalize
from lexora.container import ContainerError, read_index
from lexora.container import pack as lxz_pack, pack_stream as lxz_pack_stream, unpack as lxz_unpack
from lexora.zstd_core import CodecError, compress, decompress

# LIM-01 ceiling for the pack CLI surface (docs/RESOURCE_LIMITS.md; mirrors
# container.DEFAULT_MAX_BLOCK_UNCOMPRESSED). Values above this are refused up
# front with a clear message instead of being silently clamped by the library.
MAX_BLOCK_SIZE = 8 * 1024 * 1024

EXIT_OK = 0
EXIT_FILE = 3
EXIT_CANON = 4
EXIT_CODEC = 5
EXIT_ROUNDTRIP = 6
EXIT_CONTAINER = 7


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
        if args.meta:
            # Audit mode: JSON metadata (sizes + SHA-256 hashes + rule list)
            # to stdout INSTEAD of payload bytes; payload goes to --out only.
            import json

            from lexora.canonicalize import canonicalize_with_meta

            meta = canonicalize_with_meta(raw, declared_encoding=args.encoding)
            out = meta.pop("canonical")
            if args.outfile != "-":
                _write(args.outfile, out)
            print(json.dumps(meta, indent=2, sort_keys=True))
            print(
                f"canon: {meta['input_bytes']} -> {meta['output_bytes']} bytes "
                f"(rules CAN-R01,R02,R05; lexcAN-0.1; --meta audit)",
                file=sys.stderr,
            )
            return EXIT_OK
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


def cmd_pipe(args: argparse.Namespace) -> int:
    """End-to-end baseline flow: raw bytes -> canonicalize -> compress -> verify.

    This is the Phase-1 pipeline without a container format (the `.lxz` pack
    path stays blocked on OQ-11/ADR-0007 acceptance). The frame is written
    only if the byte-exact round-trip check passes (SPEC §8.1 spirit applied
    at the flow level).
    """
    raw = _read(args.infile)
    try:
        canon = canonicalize(raw, declared_encoding=args.encoding)
    except CanonicalizationError as exc:
        print(f"canonicalization error: {exc}", file=sys.stderr)
        return EXIT_CANON
    try:
        blob = compress(canon, level=args.level)
    except CodecError as exc:
        print(f"codec error: {exc}", file=sys.stderr)
        return EXIT_CODEC
    try:
        back = decompress(blob, expected_original_size=len(canon))
    except CodecError as exc:
        print(f"codec error on decode: {exc}", file=sys.stderr)
        return EXIT_CODEC
    exact = back == canon
    ratio_raw = (len(blob) / len(raw)) if raw else 1.0
    ratio_canon = (len(blob) / len(canon)) if canon else 1.0
    print(
        f"pipe: raw={len(raw)} canonical={len(canon)} compressed={len(blob)} "
        f"ratio_vs_raw={ratio_raw:.4f} ratio_vs_canonical={ratio_canon:.4f} "
        f"roundtrip_exact={exact}",
        file=sys.stderr,
    )
    if not exact:
        return EXIT_ROUNDTRIP  # REQ-CMP-001 violation: blocker severity
    if args.outfile != "-":
        _write(args.outfile, blob)
    return EXIT_OK


def _write_atomic(path: str, data: bytes) -> None:
    """temp file + fsync + rename (ERROR_HANDLING recovery semantics): a crash
    leaves either the previous artifact or the new one, never a hybrid."""
    d = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".lxz-tmp-")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except OSError as exc:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        print(f"error: cannot write {path}: {exc}", file=sys.stderr)
        raise SystemExit(EXIT_FILE)


def _write_atomic_stream(path: str, writer) -> None:
    """temp file + fsync + rename, where `writer(fh)` streams bytes in.

    Same recovery guarantee as _write_atomic() — a crash leaves either the old
    artifact or the new one, never a hybrid — but without ever holding the
    whole archive (or the whole input) in memory. Opened w+b because the
    streamed writer backfills the header and re-reads it to self-check.
    """
    d = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".lxz-tmp-")

    def _discard() -> None:
        try:
            os.unlink(tmp)
        except OSError:
            pass

    try:
        with os.fdopen(fd, "wb+") as fh:
            writer(fh)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except OSError as exc:
        _discard()
        print(f"error: cannot write {path}: {exc}", file=sys.stderr)
        raise SystemExit(EXIT_FILE)
    except BaseException:
        _discard()  # never leave a half-written .lxz-tmp-* behind
        raise


def cmd_pack(args) -> int:
    # --block-size bounds messaging (Session 26 polish sweep): the library
    # silently clamps block_size to LIM-01 (8 MiB); the CLI refuses up front
    # instead of hiding that clamp behind a successful-looking exit.
    if args.block_size < 1:
        print(
            f"usage error: --block-size must be >= 1 (got {args.block_size})",
            file=sys.stderr,
        )
        return 2
    if args.block_size > MAX_BLOCK_SIZE:
        print(
            f"usage error: --block-size {args.block_size} exceeds LIM-01 ceiling "
            f"{MAX_BLOCK_SIZE} bytes (8 MiB); readers enforce this cap",
            file=sys.stderr,
        )
        return 2
    # Default path is STREAMING: one block resident at a time, so peak RSS is
    # flat in input size (PERFORMANCE_BUDGET "Encode block" row). --no-stream
    # keeps the pre-streaming buffered path available for A/B evidence runs and
    # for the case where the whole payload must be resident anyway.
    # stdout can only take the buffered path (pack_stream needs a seekable dst).
    streaming = not args.no_stream and args.outfile != "-"

    if not streaming:
        payload = _read(args.infile)
        try:
            archive = lxz_pack(payload, level=args.level, block_size=args.block_size)
        except ContainerError as exc:
            print(f"container refusal on pack: {exc}", file=sys.stderr)
            return EXIT_CONTAINER
        except CodecError as exc:
            print(f"codec error on pack: {exc}", file=sys.stderr)
            return EXIT_CODEC
        if args.outfile == "-":
            sys.stdout.buffer.write(archive)
        else:
            _write_atomic(args.outfile, archive)
        info, _, _ = read_index(archive)
        in_bytes, archive_bytes = len(payload), len(archive)
    else:
        try:
            src = open(args.infile, "rb")
        except OSError as exc:
            print(f"error: cannot read {args.infile}: {exc}", file=sys.stderr)
            return EXIT_FILE
        with src:
            in_bytes = os.fstat(src.fileno()).st_size
            captured: dict = {}

            def _writer(fh) -> None:
                captured["info"] = lxz_pack_stream(
                    src, fh, level=args.level, block_size=args.block_size
                )

            try:
                _write_atomic_stream(args.outfile, _writer)
            except ContainerError as exc:
                print(f"container refusal on pack: {exc}", file=sys.stderr)
                return EXIT_CONTAINER
            except CodecError as exc:
                print(f"codec error on pack: {exc}", file=sys.stderr)
                return EXIT_CODEC
            info = captured["info"]
        archive_bytes = os.path.getsize(args.outfile)

    print(
        f"pack: in={in_bytes} blocks={len(info.blocks)} "
        f"archive={archive_bytes} ratio={(archive_bytes/in_bytes) if in_bytes else 1.0:.4f} "
        f"verified=yes (LXZ-{info.format_major}.{info.format_minor})",
        file=sys.stderr,
    )
    return EXIT_OK


def cmd_unpack(args) -> int:
    archive = _read(args.infile)
    try:
        info, _, _ = read_index(archive)
        out = lxz_unpack(archive, only_block=args.block)
    except ContainerError as exc:
        # refusal is all-or-nothing; NO output bytes written (REQ-SEC-004)
        print(f"container refusal: {exc}", file=sys.stderr)
        return EXIT_CONTAINER
    if args.meta:
        # --meta prints index metadata to stdout INSTEAD of payload bytes.
        import json
        meta = {
            "format": f"LXZ-{info.format_major}.{info.format_minor}",
            "codec_id": info.codec_id,
            "canonicalizer_version": info.canonicalizer_version,
            "generator_version": info.generator_version,
            "limits": {
                "max_block_uncompressed": info.max_block_uncompressed,
                "max_block_compressed": info.max_block_compressed,
                "max_total_uncompressed": info.max_total_uncompressed,
            },
            "blocks": [
                {"index": i, "offset": b.offset, "compressed_size": b.compressed_size,
                 "uncompressed_size": b.uncompressed_size, "sha256": b.hexdigest}
                for i, b in enumerate(info.blocks)
            ],
        }
        print(json.dumps(meta, indent=2))
    elif args.outfile == "-":
        sys.stdout.buffer.write(out)
    else:
        _write_atomic(args.outfile, out)
    print(
        f"unpack: archive={len(archive)} out={len(out)} "
        f"blocks_decoded={1 if args.block is not None else len(info.blocks)} verified=yes",
        file=sys.stderr,
    )
    return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="lexora",
        description=(
            "LEXORA prototype CLI (Phase 1 baseline + .lxz v0 container, LXZ-0.1 experimental)."
        ),
    )
    p.add_argument("--version", action="version", version=f"lexora {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("canon", help="canonicalize raw bytes -> canonical UTF-8")
    c.add_argument("--in", dest="infile", required=True)
    c.add_argument("--out", dest="outfile", required=True, help="'-' for stdout")
    c.add_argument("--encoding", default=None, help="declared source encoding")
    c.add_argument("--meta", action="store_true",
                   help="print audit JSON (sizes, SHA-256s, rules) to stdout instead of payload")
    c.set_defaults(func=cmd_canon)

    z = sub.add_parser("zround", help="zstd compress + verify byte-exact roundtrip")
    z.add_argument("--in", dest="infile", required=True)
    z.add_argument("--out", dest="outfile", default="-", help="'-' to skip writing")
    z.add_argument("--level", type=int, default=19)
    z.set_defaults(func=cmd_zround)

    pp = sub.add_parser(
        "pipe",
        help="end-to-end baseline: canonicalize -> compress -> verify roundtrip",
    )
    pp.add_argument("--in", dest="infile", required=True)
    pp.add_argument("--out", dest="outfile", default="-", help="'-' to skip writing")
    pp.add_argument("--encoding", default=None, help="declared source encoding")
    pp.add_argument("--level", type=int, default=19)
    pp.set_defaults(func=cmd_pipe)

    pk = sub.add_parser("pack", help="wrap canonical bytes into a .lxz v0 archive (ADR-0007)")
    pk.add_argument("--in", dest="infile", required=True)
    pk.add_argument("--out", dest="outfile", required=True, help="'-' for stdout")
    pk.add_argument("--level", type=int, default=19)
    pk.add_argument("--no-stream", action="store_true",
                    help="buffer the whole input in memory instead of streaming "
                         "block-by-block (same output bytes, much higher peak RSS)")
    pk.add_argument("--block-size", type=int, default=8 * 1024 * 1024,
                    help="max uncompressed bytes per block, 1..8388608 "
                         "(LIM-01 ceiling; out-of-range -> exit 2)")
    pk.set_defaults(func=cmd_pack)

    up = sub.add_parser("unpack", help="decode a .lxz v0 archive (refuses unverified output)")
    up.add_argument("--in", dest="infile", required=True)
    up.add_argument("--out", dest="outfile", default="-", help="'-' to skip writing")
    up.add_argument("--block", type=int, default=None,
                    help="bounded decode of a single block index (REQ-CMP-005)")
    up.add_argument("--meta", action="store_true",
                    help="print index metadata as JSON (stdout) instead of payload")
    up.set_defaults(func=cmd_unpack)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
