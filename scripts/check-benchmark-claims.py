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

**Reconciled 2026-11-23, and this script now keys on revision.** The reconciliation found
three different runs wearing one label: 0.3367 was revision 4's heldout-only first cut
(17 files / 12.1 MiB, 2 reps), 0.3360 was revision 5's all-splits run (184 files / 80.4 MiB),
and 0.3352 had no surviving artifact at all — revision 5's run reused revision 4's file names
and overwrote it. So a bare figure was never the ambiguity; the missing *revision* was.

A value is therefore grouped by `(system, revision)`, and only values claiming the same
revision are compared. The revision comes from the nearest `R4`/`R5`/`R6` token before the
number on its line, else the last token on the line, else the last one seen in the document —
so a table under a `Revision R5` heading inherits it, and a document that names no revision
still gets checked against other unnamed figures.

`--strict` exits 1 on a disagreement and is now the gate (CI runs it): the figures agree, so a
disagreement means someone has introduced one.
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


REVISION = re.compile(r"\bR([4-6])\b")


def scan(path: Path):
    """[(system, value, line_number, line_text, revision)]

    The revision is what makes a figure mean anything: R4 and R5 both measured the same
    systems on different corpora, so 0.3109 and 0.3120 are both right and only their labels
    tell them apart.
    """
    if not path.is_file():
        return []
    found = []
    current = None
    for i, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        tokens = [(m.start(), m.group(0)) for m in REVISION.finditer(line)]
        for name, pattern in SYSTEMS:
            m = re.search(pattern, line, re.I)
            if not m:
                continue
            before = [token for pos, token in tokens if pos < m.start(1)]
            revision = before[-1] if before else (tokens[-1][1] if tokens else current)
            found.append((name, m.group(1), i, line.strip(), revision))
        if tokens:
            current = tokens[-1][1]
    return found


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--strict", action="store_true",
                    help="exit 1 when a named system carries more than one value")
    args = ap.parse_args()

    observations = {}
    for rel in SOURCES:
        for system, value, line_no, text, revision in scan(ROOT / rel):
            observations.setdefault((system, revision), []).append((value, rel, line_no, text))

    disagreements = 0
    for system in [name for name, _ in SYSTEMS]:
        groups = {key: rows for key, rows in observations.items() if key[0] == system}
        if not groups:
            print(f"—    {system}: not found in the scanned documents")
            continue
        for (_, revision), rows in sorted(groups.items(), key=lambda kv: str(kv[0][1])):
            label = f"{system} @ {revision}" if revision else f"{system} @ (no revision named)"
            values = sorted({v for v, *_ in rows})
            if len(values) == 1:
                print(f"ok   {label}: {values[0]} in {len(rows)} place(s)")
                continue
            disagreements += 1
            print(f"DIFF {label}: {len(values)} values — {', '.join(values)}")
            for value, rel, line_no, text in rows:
                print(f"       {value}  {rel}:{line_no}")
                print(f"              {text[:110]}")

    print()
    if disagreements:
        print(f"{disagreements} named measurement(s) disagree across the documents at the "
              f"same revision. One of them is wrong, or one is missing its revision label.")
        if args.strict:
            return 1
        print("advisory: not failing the build")
        return 0
    print("every named measurement agrees with every other at the same revision")
    return 0


if __name__ == "__main__":
    sys.exit(main())
