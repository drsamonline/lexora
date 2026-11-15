#!/usr/bin/env python3
"""Report where two documents give different numbers for the same measurement.

The problem this exists for: `README.md` gives the shipped default as 0.3352 on
"172 files / 78.6 MiB", `docs/BENCHMARK_RESULTS.md` gives 0.3367 for the same
default on "746 MB corpus, 172 files", and `ADR-0015` backs 0.3352 with a byte
count. Each number may be right for its own run. A reader cannot tell which run a
figure belongs to, and nobody can spot the disagreement by reading one file.

So this does not decide which value is correct — that needs the run artifacts.
It finds the *named* systems across the documents, and reports any system that
carries more than one value.

    python3 scripts/check-benchmark-claims.py            # report, exit 0
    python3 scripts/check-benchmark-claims.py --strict   # exit 1 on a disagreement

Advisory until the figures are reconciled; `--strict` is for the day they are.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Documents that state measurements, and what each name means in them. Ordered so
# the first match wins for a line: "zstd-19" must not be read as "zstd".
SYSTEMS = [
    ("shipped default", r"shipped default.{0,45}?(0\.\d{3,4})"),
    ("lexora19", r"\blexora19\b[^0-9\n]{0,20}?(0\.\d{3,4})"),
    ("zstd-19", r"\bzstd[-_]?19\b[^0-9\n]{0,20}?(0\.\d{3,4})"),
    ("xz-9", r"\bxz[-_]?9\b[^0-9\n]{0,20}?(0\.\d{3,4})"),
]

# Documents that assert one run each. `docs/R4_SMOKE_DRAFT.md` is deliberately
# excluded: it prints R4 and R5 side by side, so the same system appears twice with
# two correct values and any comparison against it reads as a contradiction. A
# figure taken from it must cite its run (R4 or R5) to mean anything.
SOURCES = [
    "README.md",
    "docs/BENCHMARK_RESULTS.md",
    "docs/ADR/ADR-0015-codec-policy.md",
]


def scan(path: Path):
    """[(system, value, line_number, line_text)]"""
    if not path.is_file():
        return []
    found = []
    for i, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        for name, pattern in SYSTEMS:
            m = re.search(pattern, line, re.I)
            if m:
                found.append((name, m.group(1), i, line.strip()))
    return found


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--strict", action="store_true",
                    help="exit 1 when a named system carries more than one value")
    args = ap.parse_args()

    observations = {}
    for rel in SOURCES:
        for system, value, line_no, text in scan(ROOT / rel):
            observations.setdefault(system, []).append((value, rel, line_no, text))

    disagreements = 0
    for system in [name for name, _ in SYSTEMS]:
        rows = observations.get(system, [])
        if not rows:
            print(f"—    {system}: not found in the scanned documents")
            continue
        values = sorted({v for v, *_ in rows})
        if len(values) == 1:
            print(f"ok   {system}: {values[0]} in {len(rows)} place(s)")
            continue
        disagreements += 1
        print(f"DIFF {system}: {len(values)} values — {', '.join(values)}")
        for value, rel, line_no, text in rows:
            print(f"       {value}  {rel}:{line_no}")
            print(f"              {text[:110]}")

    print()
    if disagreements:
        print(f"{disagreements} named measurement(s) disagree across the documents. "
              f"Each value needs its run labelled, or one of them corrected — this "
              f"script cannot tell which.")
        if args.strict:
            return 1
        print("advisory: not failing the build")
        return 0
    print("every named measurement agrees across the scanned documents")
    return 0


if __name__ == "__main__":
    sys.exit(main())
