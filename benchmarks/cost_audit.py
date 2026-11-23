#!/usr/bin/env python3
"""REQ-CMP-004 — account for every serialized byte, against the file itself.

The requirement: *"Cost accounting includes every serialized byte: headers, side tables,
dictionaries, grammar stores, block metadata"* — verification: *"byte-exact accounting audit vs.
actual archive size"*. [COST_MODEL.md](../docs/COST_MODEL.md) states the formula and its first rule
is "nothing is free": if the decoder needs it, its bytes count. What did not exist was the auditor
that checks the formula against a real archive.

This is that auditor. It decomposes an `.lxz` file into the model's terms and demands the sum equal
the file size **exactly** — no tolerance, because a tolerance is where an unaccounted field hides.

| Cost-model term | What it is in `.lxz` v0 | Size |
|---|---|---|
| `payload(r, b)` | the compressed block bytes | Σ `compressed_size` |
| `blockHeader(b)` + `blockMetadata` | the index entry: offset, sizes, per-block SHA-256 | 56 B per block |
| `indexContribution(b)` | the same index entry — counted **once**, not twice | (already above) |
| archive header | magic, version, flags, ids, limits, header hash | 128 B |
| archive trailer | index offset, index length, index hash | 40 B |
| `sideTables`, `dictionaryShare`, `residualBytes` | **0 in v0** — no grammar, no dictionary, no literal tails | 0 |

That "counted once" is the whole reason this file exists. An accounting that charges the index
entry to both `blockMetadata` and `indexContribution` reports a number 56 bytes per block larger
than the archive and looks like a win; one that forgets the trailer reports it smaller and looks
like a saving. Both are wrong in a direction that flatters the codec.

    python benchmarks/cost_audit.py --archive file.lxz [--json]

Exit 0 when the accounting closes exactly, 2 when it does not, 3 when the file is not an archive.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

from lexora import container


class CostError(Exception):
    """The archive cannot be accounted for — not a cost-model result, a refusal to pretend."""


def account(path: pathlib.Path) -> dict:
    """Decompose an archive into the cost model's terms and check the sum closes."""
    data = path.read_bytes()
    try:
        info, index_offset, index_bytes = container.read_index(data)
    except container.ContainerError as exc:
        raise CostError(f"{path} is not a readable .lxz archive: {exc}") from exc

    blocks = list(info.blocks)
    payload = sum(b.compressed_size for b in blocks)
    index_entries = container.INDEX_ENTRY_SIZE * len(blocks)

    components = {
        "payload_bytes": payload,
        "block_metadata_bytes": index_entries,   # 56 B per block: offsets, sizes, sha256
        "index_contribution_bytes": 0,           # same bytes as block_metadata — see docstring
        "archive_header_bytes": container.HEADER_SIZE,
        "archive_trailer_bytes": container.TRAILER_SIZE,
        "side_tables_bytes": 0,                  # no grammar store in v0
        "dictionary_bytes": 0,                   # v0 archives carry no dictionary
        "residual_bytes": 0,                     # no literal tails in v0
    }
    accounted = sum(components.values())
    actual = len(data)
    residual = actual - accounted

    # Independent cross-check: the trailer declares where the index lives, so the gap between the
    # last block and the index — and between the index and the trailer — must both be zero. This
    # catches a file whose index is fine but whose layout has padding nobody accounted for.
    last_block_end = container.HEADER_SIZE + payload
    layout = {
        "index_offset_from_trailer": index_offset,
        "index_bytes_from_trailer": index_bytes,
        "last_block_end": last_block_end,
        "gap_before_index": index_offset - last_block_end,
        "gap_before_trailer": (actual - container.TRAILER_SIZE) - (index_offset + index_bytes),
    }

    report = {
        "requirement": "REQ-CMP-004",
        "archive": str(path),
        "actual_bytes": actual,
        "accounted_bytes": accounted,
        "unaccounted_bytes": residual,
        "blocks": len(blocks),
        "components": components,
        "layout": layout,
        "verdict": "PASS" if residual == 0 and not any(
            layout[k] for k in ("gap_before_index", "gap_before_trailer")) else "FAIL",
    }
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--archive", required=True, type=pathlib.Path)
    ap.add_argument("--json", action="store_true", help="machine-readable report")
    ap.add_argument("--out", type=pathlib.Path, default=None)
    args = ap.parse_args(argv)

    if not args.archive.is_file():
        print(f"no such archive: {args.archive}", file=sys.stderr)
        return 3
    try:
        report = account(args.archive)
    except CostError as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 3

    if args.json:
        text = json.dumps(report, indent=2)
    else:
        c, lay = report["components"], report["layout"]
        lines = [
            f"{report['archive']} — {report['actual_bytes']:,} B in {report['blocks']} block(s)",
            f"  payload (compressed)      {c['payload_bytes']:>12,}",
            f"  block metadata (index)    {c['block_metadata_bytes']:>12,}   "
            f"{report['blocks']} × {container.INDEX_ENTRY_SIZE} B",
            f"  archive header            {c['archive_header_bytes']:>12,}",
            f"  archive trailer           {c['archive_trailer_bytes']:>12,}",
            f"  side tables / dictionary  "
            f"{c['side_tables_bytes'] + c['dictionary_bytes']:>12,}   v0 carries neither",
            f"  residual (literal tails)  {c['residual_bytes']:>12,}",
            f"  {'accounted':<24}{report['accounted_bytes']:>12,}",
            f"  {'actual file':<24}{report['actual_bytes']:>12,}",
            f"  {'unaccounted':<24}{report['unaccounted_bytes']:>12,}",
            "",
            f"layout gaps: before index {lay['gap_before_index']} B, "
            f"before trailer {lay['gap_before_trailer']} B",
            f"verdict: {report['verdict']}",
        ]
        text = "\n".join(lines)

    if args.out:
        args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(text)
    return 0 if report["verdict"] == "PASS" else 2


if __name__ == "__main__":
    sys.exit(main())
