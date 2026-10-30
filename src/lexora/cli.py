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
  lexora verify  --in ARCHIVE.lxz [--block N] [--json]
  lexora inspect --in ARCHIVE.lxz [--verify] [--json] [--blocks N]
  lexora doctor  [--json]
  lexora batch   --in DIR --out-dir DIR [--op canon|pack|unpack] [--pattern G] [--report F]
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
import json
import os
import shutil
import signal
import sys
import tempfile
from pathlib import Path

from lexora import DEFAULT_LEVEL, __version__
from lexora.canonicalize import CanonicalizationError, canonicalize, canonicalize_stream
from lexora.container import ContainerError, read_index
from lexora.container import (
    pack as lxz_pack,
    pack_stream as lxz_pack_stream,
    read_index_stream,
    unpack as lxz_unpack,
    verify_stream,
    unpack_stream as lxz_unpack_stream,
)
from lexora.zstd_core import CodecError, compress, decompress

# LIM-01 ceiling for the pack CLI surface (docs/RESOURCE_LIMITS.md; mirrors
# container.DEFAULT_MAX_BLOCK_UNCOMPRESSED). Values above this are refused up
# front with a clear message instead of being silently clamped by the library.
MAX_BLOCK_SIZE = 8 * 1024 * 1024

EXIT_OK = 0
EXIT_PARTIAL = 1  # batch ran to completion, but at least one file failed (Session 48)
EXIT_FILE = 3
EXIT_CANON = 4
EXIT_CODEC = 5
EXIT_ROUNDTRIP = 6
EXIT_CONTAINER = 7


def _raise_exit(signum, frame):  # noqa: ARG001 - signal handler signature
    """Turn a termination signal into SystemExit so cleanup handlers run."""
    raise SystemExit(EXIT_FILE)


def _install_termination_handler() -> None:
    """Make SIGTERM unwind like Ctrl-C does.

    The atomic writers' guarantee (never a partial destination) holds under every
    signal, because the destination is only ever created by `os.replace` after the
    temp file is complete. What differed was *debris*: SIGINT raises
    KeyboardInterrupt, which the writers catch and clean up after; SIGTERM killed
    the process outright and left a `.lxz-tmp-*` behind (measured, Session 57).
    SIGKILL cannot be handled — debris there is unavoidable, and the destination is
    still safe.

    Installed only for the duration of a CLI run; a host embedding `cli.main()`
    gets the same behaviour, which is what its callers expect from a command.
    """
    try:
        signal.signal(signal.SIGTERM, _raise_exit)
    except (ValueError, OSError, AttributeError):
        # not the main thread, or a platform without SIGTERM — nothing to do
        pass


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
    """Canonicalize. Streaming by default (Session 45): the working set is one
    decoded chunk plus a one-character carry, so it no longer tracks document
    size. --no-stream keeps the buffered path for A/B evidence runs."""
    if args.no_stream:
        raw = _read(args.infile)
        try:
            if args.meta:
                from lexora.canonicalize import canonicalize_with_meta

                meta = canonicalize_with_meta(raw, declared_encoding=args.encoding)
                out = meta.pop("canonical")
                if args.outfile != "-":
                    _write(args.outfile, out)
                print(json.dumps(meta, indent=2, sort_keys=True))
                print(
                    f"canon: {meta['input_bytes']} -> {meta['output_bytes']} bytes "
                    f"(rules CAN-R01,R02,R05; lexcan-0.1; --meta audit)",
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
            f"(rules CAN-R01,R02,R05; lexcan-0.1)",
            file=sys.stderr,
        )
        return EXIT_OK

    try:
        src = open(args.infile, "rb")
    except OSError as exc:
        # _read() raises SystemExit(EXIT_FILE) for an unreadable input, and the
        # tests (and the documented exit-code table) hold the streaming path to
        # the same contract rather than returning a code.
        print(f"error: cannot read {args.infile}: {exc}", file=sys.stderr)
        raise SystemExit(EXIT_FILE)
    with src:
        captured: dict = {}

        def _writer(fh) -> None:
            captured["meta"] = canonicalize_stream(
                src, fh, declared_encoding=args.encoding
            )

        try:
            if args.meta and args.outfile == "-":
                # --meta owns stdout; the payload has nowhere to go and must NOT
                # be written there, or it corrupts the JSON (pre-existing rule).
                with open(os.devnull, "wb") as sink:
                    _writer(sink)
            else:
                _stream_to_destination(args.outfile, _writer)
        except CanonicalizationError as exc:
            print(f"canonicalization error: {exc}", file=sys.stderr)
            return EXIT_CANON
    meta = captured["meta"]
    if args.meta:
        print(json.dumps(meta, indent=2, sort_keys=True))
        print(
            f"canon: {meta['input_bytes']} -> {meta['output_bytes']} bytes "
            f"(rules CAN-R01,R02,R05; lexcan-0.1; --meta audit)",
            file=sys.stderr,
        )
        return EXIT_OK
    print(
        f"canon: {meta['input_bytes']} -> {meta['output_bytes']} bytes "
        f"(rules CAN-R01,R02,R05; lexcan-0.1)",
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
    tmp: str | None = None
    try:
        # mkstemp must be INSIDE the try: an unwritable or missing destination
        # directory raises here, and before Session 55 that OSError escaped as a
        # traceback with exit 1 — contradicting the documented exit-code table,
        # which promises 3 and a one-line error for any output-file failure.
        fd, tmp = tempfile.mkstemp(dir=d, prefix=".lxz-tmp-")
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except OSError as exc:
        if tmp is not None:
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
    tmp: str | None = None

    def _discard() -> None:
        if tmp is None:
            return
        try:
            os.unlink(tmp)
        except OSError:
            pass

    try:
        # Inside the try for the same reason as _write_atomic: a missing or
        # unwritable destination directory must become exit 3, not a traceback.
        fd, tmp = tempfile.mkstemp(dir=d, prefix=".lxz-tmp-")
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


def _stream_to_destination(outfile: str, writer) -> None:
    """Run `writer(fh)` into a temp file, then deliver it to `outfile`.

    A path destination is renamed into place (same recovery guarantee as
    _write_atomic); `-` copies the finished temp file to stdout. Either way
    nothing reaches the destination unless writer() returned without raising,
    which is what keeps "refuse unverified output" (REQ-SEC-004) true on a
    streaming decode: a bad block aborts before a single byte is emitted.
    """
    if outfile != "-":
        _write_atomic_stream(outfile, writer)
        return
    fd, tmp = tempfile.mkstemp(prefix=".lxz-out-")
    try:
        with os.fdopen(fd, "wb") as fh:
            writer(fh)
            fh.flush()
            os.fsync(fh.fileno())
        with open(tmp, "rb") as fh:
            shutil.copyfileobj(fh, sys.stdout.buffer, 1 << 20)
        sys.stdout.buffer.flush()
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass


def _archive_meta(info) -> dict:
    """Index metadata as JSON (the --meta payload; index only, no blocks read)."""
    return {
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
    """Decode an archive. Streaming by default (Session 41): the index plus one
    block are resident, so decode memory no longer tracks archive size.
    --no-stream keeps the pre-Session-41 whole-archive path for A/B runs."""
    if args.no_stream:
        archive = _read(args.infile)
        try:
            info, _, _ = read_index(archive)
            out = lxz_unpack(archive, only_block=args.block)
        except ContainerError as exc:
            # refusal is all-or-nothing; NO output bytes written (REQ-SEC-004)
            print(f"container refusal: {exc}", file=sys.stderr)
            return EXIT_CONTAINER
        if args.meta:
            print(json.dumps(_archive_meta(info), indent=2))
        elif args.outfile == "-":
            sys.stdout.buffer.write(out)
        else:
            _write_atomic(args.outfile, out)
        archive_bytes, out_bytes = len(archive), len(out)
        blocks = 1 if args.block is not None else len(info.blocks)
    else:
        try:
            src = open(args.infile, "rb")
        except OSError as exc:
            print(f"error: cannot read {args.infile}: {exc}", file=sys.stderr)
            return EXIT_FILE
        with src:
            archive_bytes = os.fstat(src.fileno()).st_size
            try:
                info, _, _ = read_index_stream(src)
            except ContainerError as exc:
                print(f"container refusal: {exc}", file=sys.stderr)
                return EXIT_CONTAINER
            if args.meta:
                # index only: no block is read or decoded
                print(json.dumps(_archive_meta(info), indent=2))
                print(
                    f"unpack: archive={archive_bytes} out={info.total_uncompressed} "
                    f"blocks_decoded=0 verified=index-only "
                    f"(LXZ-{info.format_major}.{info.format_minor})",
                    file=sys.stderr,
                )
                return EXIT_OK
            captured: dict = {}

            def _writer(fh) -> None:
                _, written = lxz_unpack_stream(src, fh, only_block=args.block)
                captured["written"] = written

            try:
                _stream_to_destination(args.outfile, _writer)
            except ContainerError as exc:
                print(f"container refusal: {exc}", file=sys.stderr)
                return EXIT_CONTAINER
            out_bytes = captured["written"]
            blocks = 1 if args.block is not None else len(info.blocks)

    print(
        f"unpack: archive={archive_bytes} out={out_bytes} "
        f"blocks_decoded={blocks} verified=yes",
        file=sys.stderr,
    )
    return EXIT_OK


def cmd_doctor(args) -> int:
    """Report whether this installation is healthy, and on what.

    Exit 0 when every check passes, **1** when any check fails or warns — the same
    "not everything is well" meaning `batch` gives exit 1, and deliberately not 7,
    because nothing here is an archive refusal.
    """
    from lexora.doctor import format_report, run_checks

    report = run_checks()
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(format_report(report))
    return EXIT_OK if report["healthy"] else EXIT_PARTIAL


def cmd_inspect(args) -> int:
    """Human-readable summary of one archive; `--verify` adds a full integrity pass.

    Distinct from `unpack --meta` (JSON for scripts) and from `verify` (verdict
    only): this prints what a person wants to see — what the archive is, how much
    of it is payload, what the container costs, and whether its accounting closes.
    """
    from lexora.inspect import (
        format_directory_report,
        format_report,
        summarize,
        summarize_directory,
    )

    if Path(args.infile).is_dir():
        summary = summarize_directory(args.infile, pattern=args.pattern, verify=args.verify)
        if not summary["archives"]:
            print(f"error: no archives matched {args.pattern!r} under {args.infile}",
                  file=sys.stderr)
            return 2
        if args.json:
            print(json.dumps(summary, indent=2, sort_keys=True))
        else:
            print(format_directory_report(summary))
        return EXIT_OK if summary["archives_failed"] == 0 else EXIT_CONTAINER

    try:
        src = open(args.infile, "rb")
    except OSError as exc:
        print(f"error: cannot read {args.infile}: {exc}", file=sys.stderr)
        raise SystemExit(EXIT_FILE)
    with src:
        try:
            summary = summarize(src, verify=args.verify)
        except ContainerError as exc:
            print(f"container refusal: {exc}", file=sys.stderr)
            return EXIT_CONTAINER
    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print(format_report(summary, max_blocks=args.blocks))
    ok = summary["accounting"]["ok"] and (summary["verified"] is not False)
    return EXIT_OK if ok else EXIT_CONTAINER


def cmd_verify(args) -> int:
    """Audit an archive without writing any payload: structure, then per-block
    integrity. Streaming, so an audit costs one pass and one block of memory.

    Exit 0 = everything verified, 7 = refusal or any failed block (matching the
    reader's refusal code so scripts can treat "bad archive" uniformly), 3 =
    unreadable input.
    """
    try:
        src = open(args.infile, "rb")
    except OSError as exc:
        print(f"error: cannot read {args.infile}: {exc}", file=sys.stderr)
        raise SystemExit(EXIT_FILE)
    with src:
        archive_bytes = os.fstat(src.fileno()).st_size
        result = verify_stream(src, only_block=args.block)

    failed = [(i, code) for i, ok, code in result.blocks if not ok]
    if args.json:
        print(json.dumps({
            "archive_bytes": archive_bytes,
            "ok": result.ok,
            "error": result.error,
            "block_count": result.block_count,
            "checked": [i for i, _, _ in result.blocks],
            "failed": [{"index": i, "code": code} for i, code in failed],
        }, indent=2, sort_keys=True))
    if result.error:
        print(f"verify: refusal: {result.error}", file=sys.stderr)
    for i, code in failed:
        print(f"verify: block {i} FAILED ({code})", file=sys.stderr)
    print(
        f"verify: archive={archive_bytes} blocks={result.block_count} "
        f"checked={len(result.blocks)} failed={len(failed)} "
        f"verified={'yes' if result.ok else 'no'}",
        file=sys.stderr,
    )
    return EXIT_OK if result.ok else EXIT_CONTAINER


def _iter_batch_inputs(root: Path, pattern: str) -> list[Path]:
    """Every regular file under `root` (recursively) matching `pattern`.

    Ordering is sorted and therefore deterministic, which matters because the
    report is compared run to run and a shuffled batch is hard to audit.
    """
    if root.is_file():
        return [root]
    return sorted(p for p in root.rglob(pattern) if p.is_file())


def _batch_one(spec: dict) -> dict:
    """Process one file for `batch`. Module-level and picklable so it can run in a
    worker *process*.

    Threads were tried first and measured useless here: python-zstandard holds the
    GIL for the whole compress call (2 threads x 4 compressions took 3.04 s against
    1.62 s sequential, i.e. exactly 2x), so a thread pool only adds overhead to a
    CPU-bound batch. Processes have their own GIL, so `--jobs` is a real knob —
    bounded by core count, which is 2 on the machine these numbers came from.
    """
    from lexora.canonicalize import canonicalize_stream
    from lexora.container import pack_stream as lxz_pack_stream
    from lexora.container import unpack_stream as lxz_unpack_stream

    entry: dict = {"input": spec["rel"], "output": spec["out_rel"]}
    src_path, dst_path = Path(spec["src"]), Path(spec["dst"])
    try:
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        # pack_stream backfills the header and re-reads it to self-check, so its
        # destination must be readable; canon and unpack write forward only.
        mode = "wb+" if spec["op"] == "pack" else "wb"
        with open(src_path, "rb") as src, open(dst_path, mode) as dst:
            if spec["op"] == "canon":
                meta = canonicalize_stream(src, dst, declared_encoding=spec["encoding"])
            elif spec["op"] == "pack":
                info = lxz_pack_stream(src, dst, level=spec["level"],
                                       block_size=spec["block_size"])
                meta = {"input_bytes": src_path.stat().st_size,
                        "output_bytes": dst_path.stat().st_size,
                        "blocks": len(info.blocks)}
            else:
                info, written = lxz_unpack_stream(src, dst)
                meta = {"input_bytes": src_path.stat().st_size,
                        "output_bytes": written,
                        "blocks": len(info.blocks)}
        entry.update(ok=True, **{k: meta[k] for k in ("input_bytes", "output_bytes")})
        if "blocks" in meta:
            entry["blocks"] = meta["blocks"]
    except CanonicalizationError as exc:
        entry.update(ok=False, code="E-CAN", error=str(exc))
    except ContainerError as exc:
        entry.update(ok=False, code=exc.code, error=exc.message)
    except CodecError as exc:
        entry.update(ok=False, code="E-CMP", error=str(exc))
    except OSError as exc:
        entry.update(ok=False, code="E-IO", error=str(exc))
    if not entry["ok"]:
        try:
            dst_path.unlink()  # a failed file leaves no half-written artifact
        except OSError:
            pass
    return entry


def cmd_batch(args) -> int:
    """Process many files in one invocation (canon or pack), one at a time.

    This is the core the GUI's batch queue needs, built where it can be tested:
    streaming per file (so a batch of large documents costs one document, not
    all of them), deterministic ordering, per-file results in one report, and a
    documented policy for partial failure rather than a first-error abort.

    Exit codes: 0 every file succeeded; **1** the batch completed but some files
    failed (new in Session 48 — a partial run is neither success nor a single
    error); with `--stop-on-error`, the failing file's own code (3/4/5/7); 2 for
    usage problems; 3 when the input root or output directory cannot be used.
    """
    if args.op not in ("canon", "pack", "unpack"):
        print(f"usage error: --op must be canon, pack or unpack (got {args.op!r})",
              file=sys.stderr)
        return 2
    if args.block_size < 1 or args.block_size > MAX_BLOCK_SIZE:
        print(f"usage error: --block-size must be 1..{MAX_BLOCK_SIZE}", file=sys.stderr)
        return 2

    root = Path(args.infile)
    if not root.exists():
        print(f"error: cannot read {root}: no such file or directory", file=sys.stderr)
        return EXIT_FILE
    inputs = _iter_batch_inputs(root, args.pattern)
    if not inputs:
        print(f"error: no files matched {args.pattern!r} under {root}", file=sys.stderr)
        return 2

    out_dir = Path(args.out_dir)
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        print(f"error: cannot create {out_dir}: {exc}", file=sys.stderr)
        return EXIT_FILE

    suffix = args.suffix or (".canon" if args.op == "canon" else
                             ".lxz" if args.op == "pack" else "")

    def _output_name(rel: Path) -> str:
        """canon/pack append; unpack strips the archive suffix so the round trip
        returns the name it started with."""
        if args.op != "unpack":
            return rel.name + suffix
        if suffix:
            return rel.name + suffix
        if rel.name.endswith(".lxz"):
            return rel.name[: -len(".lxz")]
        return rel.name + ".unpacked"  # not an .lxz name; will fail to parse anyway
    base = root if root.is_dir() else root.parent

    specs = []
    for src_path in inputs:
        rel = src_path.relative_to(base)
        dst_path = out_dir / rel.parent / _output_name(rel)
        specs.append({
            "op": args.op,
            "src": str(src_path),
            "dst": str(dst_path),
            "rel": str(rel),
            "out_rel": str(dst_path.relative_to(out_dir)),
            "level": args.level,
            "block_size": args.block_size,
            "encoding": args.encoding,
        })

    jobs = max(1, int(getattr(args, "jobs", 1) or 1))
    if jobs == 1 or len(specs) == 1:
        outcomes = [_batch_one(spec) for spec in specs]
    else:
        from concurrent.futures import ProcessPoolExecutor

        with ProcessPoolExecutor(max_workers=jobs) as pool:
            outcomes = list(pool.map(_batch_one, specs))  # map preserves input order

    results = []
    for entry in outcomes:
        if not entry["ok"]:
            print(f"batch: {entry['input']} FAILED ({entry.get('code')}): "
                  f"{entry.get('error', '')}", file=sys.stderr)
            results.append(entry)
            if args.stop_on_error:
                break
            continue
        results.append(entry)

    failures = sum(1 for r in results if not r["ok"])
    ok_count = sum(1 for r in results if r["ok"])
    report = {
        "op": args.op,
        "input_root": str(root),
        "pattern": args.pattern,
        "output_dir": str(out_dir),
        "suffix": suffix,
        "files_matched": len(inputs),
        "files_ok": ok_count,
        "files_failed": failures,
        "input_bytes_total": sum(r.get("input_bytes", 0) for r in results),
        "output_bytes_total": sum(r.get("output_bytes", 0) for r in results),
        "results": results,
    }
    if args.report:
        Path(args.report).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    print(
        f"batch: {args.op} {ok_count}/{len(results)} ok"
        + (f", {failures} failed" if failures else "")
        + f"; in={report['input_bytes_total']} out={report['output_bytes_total']} bytes"
        + f" -> {out_dir}",
        file=sys.stderr,
    )
    if failures:
        if args.stop_on_error:
            first = next(r for r in results if not r["ok"])
            return {"E-CAN": EXIT_CANON, "E-CMP": EXIT_CODEC, "E-IO": EXIT_FILE}.get(
                first.get("code"), EXIT_CONTAINER
            )
        return EXIT_PARTIAL
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
    c.add_argument("--no-stream", action="store_true",
                   help="buffer the whole document in memory instead of canonicalizing "
                        "chunk-by-chunk (same output bytes, higher peak RSS)")
    c.set_defaults(func=cmd_canon)

    z = sub.add_parser("zround", help="zstd compress + verify byte-exact roundtrip")
    z.add_argument("--in", dest="infile", required=True)
    z.add_argument("--out", dest="outfile", default="-", help="'-' to skip writing")
    z.add_argument("--level", type=int, default=DEFAULT_LEVEL)
    z.set_defaults(func=cmd_zround)

    pp = sub.add_parser(
        "pipe",
        help="end-to-end baseline: canonicalize -> compress -> verify roundtrip",
    )
    pp.add_argument("--in", dest="infile", required=True)
    pp.add_argument("--out", dest="outfile", default="-", help="'-' to skip writing")
    pp.add_argument("--encoding", default=None, help="declared source encoding")
    pp.add_argument("--level", type=int, default=DEFAULT_LEVEL)
    pp.set_defaults(func=cmd_pipe)

    pk = sub.add_parser("pack", help="wrap canonical bytes into a .lxz v0 archive (ADR-0007)")
    pk.add_argument("--in", dest="infile", required=True)
    pk.add_argument("--out", dest="outfile", required=True, help="'-' for stdout")
    pk.add_argument("--level", type=int, default=DEFAULT_LEVEL)
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
                    help="print index metadata as JSON (stdout) instead of payload "
                         "(index only — no block is read)")
    up.add_argument("--no-stream", action="store_true",
                    help="buffer the whole archive and output in memory instead of "
                         "decoding block-by-block (same output bytes, much higher peak RSS)")
    up.set_defaults(func=cmd_unpack)

    vf = sub.add_parser("verify", help="audit a .lxz archive without writing payload bytes")
    vf.add_argument("--in", dest="infile", required=True)
    vf.add_argument("--block", type=int, default=None,
                    help="verify only block N (default: every block)")
    vf.add_argument("--json", action="store_true",
                    help="print the full per-block report as JSON to stdout")
    vf.set_defaults(func=cmd_verify)

    ins = sub.add_parser("inspect",
                         help="print a readable summary of one archive, or of every archive in a directory")
    ins.add_argument("--in", dest="infile", required=True,
                     help="an archive, or a directory to summarise every archive under it")
    ins.add_argument("--verify", action="store_true",
                     help="also decode every block and check its SHA-256 (costs a full read)")
    ins.add_argument("--json", action="store_true", help="machine-readable summary instead of text")
    ins.add_argument("--blocks", type=int, default=20,
                     help="how many block rows to print (default 20; 0 hides the table)")
    ins.add_argument("--pattern", default="*.lxz",
                     help="glob used when --in is a directory (default: *.lxz)")
    ins.set_defaults(func=cmd_inspect)

    doc = sub.add_parser("doctor", help="report whether this install is healthy")
    doc.add_argument("--json", action="store_true", help="machine-readable report")
    doc.set_defaults(func=cmd_doctor)

    bt = sub.add_parser("batch",
                        help="process many files in one invocation (canon, pack or unpack)")
    bt.add_argument("--in", dest="infile", required=True,
                    help="a directory (searched recursively) or a single file")
    bt.add_argument("--op", choices=("canon", "pack", "unpack"), default="canon")
    bt.add_argument("--out-dir", required=True, help="destination root (created if missing)")
    bt.add_argument("--pattern", default="*", help="glob applied under --in (default: *)")
    bt.add_argument("--suffix", default=None,
                    help="appended to each output name (default: .canon for canon, .lxz for pack; "
                         "for unpack the .lxz is stripped instead)")
    bt.add_argument("--encoding", default=None, help="declared source encoding (canon only)")
    bt.add_argument("--level", type=int, default=DEFAULT_LEVEL, help="zstd level (pack only)")
    bt.add_argument("--block-size", type=int, default=8 * 1024 * 1024)
    bt.add_argument("--jobs", type=int, default=1,
                    help="process this many files concurrently (default 1). Results and "
                         "the report are identical to a sequential run. EXPERIMENTAL: on "
                         "the 2-vCPU container these numbers came from it is 20-40%% "
                         "SLOWER than --jobs 1 (process start-up plus CPU contention), "
                         "so measure before relying on it")
    bt.add_argument("--stop-on-error", action="store_true",
                    help="abort at the first failure and exit with that file's code")
    bt.add_argument("--report", default=None, help="write the JSON report to this path")
    bt.add_argument("--json", action="store_true", help="print the JSON report to stdout")
    bt.set_defaults(func=cmd_batch)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    _install_termination_handler()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
