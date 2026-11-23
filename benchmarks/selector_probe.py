#!/usr/bin/env python3
"""What a cost-based selector would actually be choosing between (REQ-CMP-003, ADR-0026).

`COST_MODEL.md` rule 2 says: per block, pick the argmin of total serialized bytes over the enabled
candidates, ties broken by a fixed priority. v0 does not do that — it takes a pinned preset
(ADR-0015) — and REQ-CMP-003 asks for cost-based selection. Before deciding whether to build it,
the question is what the choice is *worth*.

On the shipped default it is worth one comparison: level 9 against level 19 of the same codec. That
is the trade a selector would make automatically, and it is measurable here without any external
binary. The CHCE (ziptastic) candidate is the more interesting one and cannot be measured in this
container — the binary is absent — which is recorded in the artifact rather than papered over.

    python benchmarks/selector_probe.py --out benchmarks/results-selector-probe.json
"""

from __future__ import annotations

import argparse
import json
import pathlib
import statistics
import sys
import time

REPO = pathlib.Path(__file__).resolve().parent.parent
DEFAULT_INPUT = REPO / "tests" / "vectors" / "real_text" / "gutenberg_slices.txt"
LEVELS = (9, 19)


def measure(data: bytes, *, reps: int = 3) -> dict:
    from lexora import zstd_core

    rows = []
    for level in LEVELS:
        times, sizes = [], []
        for _ in range(reps):
            start = time.perf_counter()
            out = zstd_core.compress(data, level=level)
            times.append(time.perf_counter() - start)
            sizes.append(len(out))
        median = statistics.median(times)
        rows.append({
            "level": level,
            "stored_bytes": sizes[0],
            "ratio": round(sizes[0] / len(data), 4),
            "median_seconds": round(median, 4),
            "mib_per_second": round(len(data) / median / 1e6, 1),
        })
    cheapest, best = rows[0], min(rows, key=lambda r: r["stored_bytes"])
    return {
        "input": str(DEFAULT_INPUT.relative_to(REPO)),
        "input_bytes": len(data),
        "reps": reps,
        "rows": rows,
        "selector_would_pick": best["level"],
        "bytes_saved_by_picking": cheapest["stored_bytes"] - best["stored_bytes"],
        "percent_smaller": round(
            (cheapest["stored_bytes"] - best["stored_bytes"]) / cheapest["stored_bytes"] * 100, 2
        ),
        "time_multiplier": round(best["median_seconds"] / cheapest["median_seconds"], 1),
        "not_measured": {
            "ziptastic (CHCE)": "binary absent from this container — the candidate a selector would "
                                "most want to compare, and the one number this probe cannot supply",
        },
        "note": (
            "Timings are from a shared container: sizes are exact, throughput is indicative "
            "(PERFORMANCE_BUDGET.md). The question this answers is the size/time trade, not a "
            "throughput claim."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--input", type=pathlib.Path, default=DEFAULT_INPUT)
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--out", type=pathlib.Path, default=None)
    args = ap.parse_args(argv)

    result = measure(args.input.read_bytes(), reps=args.reps)
    text = json.dumps(result, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
