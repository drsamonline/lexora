"""Human-readable archive inspection — Qt-free, so the GUI can reuse it.

The JSON from `unpack --meta` is for scripts; this is for a person looking at one
archive and wanting to know what it is, how much of it is payload, and whether the
container's own accounting closes. It is also the data the GUI inspector (G4) will
render, which is why the formatting lives here rather than in `cli.py`.

The interesting number is `accounting`: `.lxz` v0 makes an exact promise — header
+ Σ frames + index + trailer must equal the file length. That is REQ-CMP-004
("nothing is free") instantiated for this format, and it is checkable from the
index alone without decoding anything.
"""

from __future__ import annotations

from pathlib import Path

from lexora.container import (
    HEADER_SIZE,
    ContainerError,
    INDEX_ENTRY_SIZE,
    TRAILER_SIZE,
    read_index_stream,
    verify_stream,
)


def summarize(src, *, verify: bool = False) -> dict:
    """Structural summary of the archive behind a seekable handle.

    `verify=True` additionally decodes every block and checks its SHA-256, which
    costs a full read but answers "is the payload actually intact?" rather than
    only "is the index self-consistent?".
    """
    info, idx_off, idx_len = read_index_stream(src)
    src.seek(0, 2)
    file_len = src.tell()

    total_compressed = sum(b.compressed_size for b in info.blocks)
    total_uncompressed = info.total_uncompressed
    fixed_overhead = HEADER_SIZE + TRAILER_SIZE
    accounted = HEADER_SIZE + total_compressed + idx_len + TRAILER_SIZE

    blocks = [
        {
            "index": i,
            "offset": b.offset,
            "compressed_bytes": b.compressed_size,
            "uncompressed_bytes": b.uncompressed_size,
            "ratio": round(b.compressed_size / b.uncompressed_size, 4)
            if b.uncompressed_size
            else None,
            "sha256": b.hexdigest,
        }
        for i, b in enumerate(info.blocks)
    ]

    summary = {
        "format": f"LXZ-{info.format_major}.{info.format_minor}",
        "codec_id": info.codec_id,
        "canonicalizer_version": info.canonicalizer_version,
        "generator_version": info.generator_version,
        "limits": {
            "max_block_uncompressed": info.max_block_uncompressed,
            "max_block_compressed": info.max_block_compressed,
            "max_total_uncompressed": info.max_total_uncompressed,
        },
        "archive_bytes": file_len,
        "index_offset": idx_off,
        "block_count": len(info.blocks),
        "total_uncompressed_bytes": total_uncompressed,
        "total_compressed_bytes": total_compressed,
        "ratio": round(file_len / total_uncompressed, 4) if total_uncompressed else None,
        "overhead": {
            "header_bytes": HEADER_SIZE,
            "index_bytes": idx_len,
            "index_bytes_per_block": INDEX_ENTRY_SIZE,
            "trailer_bytes": TRAILER_SIZE,
            "fixed_bytes": fixed_overhead,
            "total_bytes": fixed_overhead + idx_len,
        },
        "accounting": {
            "accounted_bytes": accounted,
            "actual_bytes": file_len,
            "ok": accounted == file_len,
        },
        "blocks": blocks,
        "verified": None,
        "failed_blocks": [],
    }

    if verify:
        result = verify_stream(src)
        summary["verified"] = result.ok
        summary["failed_blocks"] = [
            {"index": i, "code": code} for i, ok, code in result.blocks if not ok
        ]
        if result.error:
            summary["verify_error"] = result.error
    return summary


def format_report(summary: dict, *, max_blocks: int = 20) -> str:
    """One-screen text rendering of summarize(). Blocks past `max_blocks` are
    elided with a count, so a 10,000-block archive still prints something a
    person can read."""
    lines: list[str] = []
    acct = summary["accounting"]
    lines.append(
        f"{summary['format']}  {summary['block_count']} block(s)  "
        f"{summary['archive_bytes']:,} bytes  ratio {summary['ratio']}"
    )
    lines.append(
        f"codec {summary['codec_id']}  canonicalizer {summary['canonicalizer_version']}  "
        f"generator {summary['generator_version']}"
    )
    lines.append(
        f"payload {summary['total_uncompressed_bytes']:,} -> "
        f"{summary['total_compressed_bytes']:,} compressed bytes"
    )
    ov = summary["overhead"]
    lines.append(
        f"overhead {ov['total_bytes']:,} bytes "
        f"(header {ov['header_bytes']} + index {ov['index_bytes']} "
        f"[{ov['index_bytes_per_block']}/block] + trailer {ov['trailer_bytes']})"
    )
    lines.append(
        f"accounting: {'OK' if acct['ok'] else 'MISMATCH'} — "
        f"{acct['accounted_bytes']:,} accounted vs {acct['actual_bytes']:,} actual"
    )
    if summary["verified"] is not None:
        if summary["verified"]:
            lines.append("integrity: all blocks verified")
        else:
            codes = ", ".join(f"#{f['index']}={f['code']}" for f in summary["failed_blocks"])
            lines.append(f"integrity: FAILED ({codes or summary.get('verify_error', 'refusal')})")
    else:
        lines.append("integrity: not checked (pass --verify to decode and hash every block)")

    if summary["blocks"] and max_blocks > 0:
        lines.append("")
        lines.append(f"{'#':>4} {'offset':>10} {'compressed':>11} {'uncompressed':>13} "
                     f"{'ratio':>7}  sha256")
        for row in summary["blocks"][:max_blocks]:
            lines.append(
                f"{row['index']:>4} {row['offset']:>10,} {row['compressed_bytes']:>11,} "
                f"{row['uncompressed_bytes']:>13,} {row['ratio'] if row['ratio'] is not None else '-':>7}  "
                f"{row['sha256'][:16]}…"
            )
    hidden = len(summary["blocks"]) - max(0, max_blocks)
    if hidden > 0:
        lines.append(f"... {hidden} more block(s) not shown (--blocks N to raise the limit)")
    return "\n".join(lines)


def summarize_directory(root: Path | str, *, pattern: str = "*.lxz", verify: bool = False) -> dict:
    """Aggregate summary over every archive under `root` (recursive, sorted).

    This is what a user actually asks after a batch pack: "how did the run turn
    out?" — so it answers per archive *and* in total, and it keeps going when one
    archive is broken rather than stopping at the first bad file. A broken archive
    is recorded with its refusal code; it is never silently dropped from the
    totals, because a count that omits its failures is a count you cannot trust.
    """
    root = Path(root)
    paths = sorted(p for p in root.rglob(pattern) if p.is_file())
    rows: list[dict] = []
    for path in paths:
        rel = path.relative_to(root).as_posix()
        try:
            with open(path, "rb") as fh:
                summary = summarize(fh, verify=verify)
        except ContainerError as exc:
            rows.append({"archive": rel, "ok": False, "code": exc.code,
                         "error": exc.message, "archive_bytes": path.stat().st_size})
            continue
        except OSError as exc:
            rows.append({"archive": rel, "ok": False, "code": "E-IO",
                         "error": str(exc), "archive_bytes": path.stat().st_size})
            continue
        ok = summary["accounting"]["ok"] and (summary["verified"] is not False)
        rows.append({
            "archive": rel,
            "ok": ok,
            "code": None if ok else ("E-ACCT" if not summary["accounting"]["ok"] else "E-INTEGRITY-001"),
            "archive_bytes": summary["archive_bytes"],
            "total_uncompressed_bytes": summary["total_uncompressed_bytes"],
            "block_count": summary["block_count"],
            "ratio": summary["ratio"],
            "accounting_ok": summary["accounting"]["ok"],
            "overhead_bytes": summary["overhead"]["total_bytes"],
            "verified": summary["verified"],
            "failed_blocks": summary["failed_blocks"],
        })

    good = [r for r in rows if r["ok"]]
    return {
        "root": str(root),
        "pattern": pattern,
        "archive_count": len(rows),
        "archives_ok": len(good),
        "archives_failed": len(rows) - len(good),
        "archive_bytes_total": sum(r.get("archive_bytes", 0) for r in rows),
        "uncompressed_bytes_total": sum(r.get("total_uncompressed_bytes", 0) for r in rows),
        "overhead_bytes_total": sum(r.get("overhead_bytes", 0) for r in rows),
        "block_count_total": sum(r.get("block_count", 0) for r in rows),
        "ratio": round(
            sum(r.get("archive_bytes", 0) for r in rows)
            / sum(r.get("total_uncompressed_bytes", 0) for r in rows), 4
        ) if sum(r.get("total_uncompressed_bytes", 0) for r in rows) else None,
        # Deliberately over ALL rows, not just the parsed ones: a broken archive
        # contributes no blocks, so "every good row verified" was vacuously True
        # and the report claimed full integrity while listing a FAILED archive.
        "verified": (all(r.get("verified") is True for r in rows) if verify and rows else None),
        "archives": rows,  # per-archive rows; "archive_count" is the number
    }


def format_directory_report(summary: dict) -> str:
    """Text rendering of summarize_directory(): totals first, then one line each."""
    lines = [
        f"{summary['archive_count']} archive(s) under {summary['root']} "
        f"({summary['pattern']}): {summary['archives_ok']} ok, "
        f"{summary['archives_failed']} failed",
        f"payload {summary['uncompressed_bytes_total']:,} -> "
        f"{summary['archive_bytes_total']:,} bytes on disk, ratio {summary['ratio']}, "
        f"container overhead {summary['overhead_bytes_total']:,} bytes "
        f"across {summary['block_count_total']} block(s) in the "
        f"{summary['archive_count'] - summary['archives_failed']} archive(s) that parsed",
    ]
    if summary["archives_failed"]:
        lines.append(
            f"integrity: {summary['archives_failed']} archive(s) could not be verified "
            f"(see rows below)"
        )
    elif summary["verified"] is True:
        lines.append("integrity: every block in every archive verified")
    elif summary["verified"] is False:
        lines.append("integrity: FAILURES present (see rows below)")
    else:
        lines.append("integrity: not checked (pass --verify to decode and hash every block)")
    lines.append("")
    width = max((len(r["archive"]) for r in summary["archives"]), default=7)
    lines.append(f"{'archive':<{width}} {'blocks':>6} {'bytes':>10} {'ratio':>7}  status")
    for r in summary["archives"]:
        status = "ok" if r["ok"] else f"FAILED ({r.get('code')})"
        lines.append(
            f"{r['archive']:<{width}} {r.get('block_count', 0):>6} "
            f"{r.get('archive_bytes', 0):>10,} {r.get('ratio') if r.get('ratio') is not None else '-':>7}  "
            f"{status}"
        )
    return "\n".join(lines)
