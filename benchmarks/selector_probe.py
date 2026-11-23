#!/usr/bin/env python3
"""What a cost-based selector would actually be choosing between (REQ-CMP-003, ADR-0026).

`COST_MODEL.md` rule 2 says: per block, pick the argmin of total serialized bytes over the enabled
candidates, ties broken by a fixed priority. v0 does not do that — it takes a pinned preset
(ADR-0015) — and REQ-CMP-003 asks for cost-based selection. Before deciding whether to build it,
the question is what the choice is *worth*.

**Every candidate is measured when its binary is present, and recorded as `not_measured` when it is
not.** The first version of this probe could only compare level against level, because the
container had no external binaries — and then it turned out the fleet already ships them
(`drsamonline/heavenzip` → `bin/ziptastic-*`, `bin/xz`, `bin/7z`, `bin/brotli`, `bin/zstd`). Point
`--bin-dir` at that directory and the probe measures what the decision actually needs: CHCE, the
`xz` CLI, PPMd through `7z`, and brotli q11.

Scope stays honest: this is **one 721 KB slice**, not a protocol-scope run. It answers "what would
a selector have to choose between, and by how much", not "which codec wins" — that is P0's job
(P0_RUNBOOK.md).

    python benchmarks/selector_probe.py --bin-dir /path/to/heavenzip/bin \
        --out benchmarks/results-selector-probe.json
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


def _timed(fn, data: bytes, reps: int) -> tuple[int, float]:
    """(stored bytes, median seconds). Sizes are exact; times are indicative."""
    times, sizes = [], []
    for _ in range(reps):
        start = time.perf_counter()
        out = fn(data)
        times.append(time.perf_counter() - start)
        sizes.append(len(out))
    return sizes[0], statistics.median(times)


def _external(argv_for, data: bytes):
    """Run an external compressor over stdin and count what comes back on stdout."""
    import subprocess

    def run(payload: bytes) -> bytes:
        proc = subprocess.run(argv_for(), input=payload, capture_output=True, timeout=600)
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr.decode("utf-8", "replace")[:200])
        return proc.stdout

    return run


def _seven_zip(binary: str):
    """7z writes an archive, not a stream — so it is timed through a temp file."""
    import subprocess
    import tempfile

    def run(payload: bytes) -> bytes:
        with tempfile.TemporaryDirectory() as tmp:
            src = pathlib.Path(tmp) / "in.bin"
            dst = pathlib.Path(tmp) / "out.7z"
            src.write_bytes(payload)
            proc = subprocess.run([binary, "a", "-t7z", "-m0=PPMd", "-mx9", str(dst), str(src)],
                                  capture_output=True, timeout=900)
            if proc.returncode != 0:
                raise RuntimeError(proc.stderr.decode("utf-8", "replace")[:200])
            return dst.read_bytes()

    return run


def _candidates(bin_dir: pathlib.Path | None) -> tuple[dict, dict]:
    """Every candidate whose binary is available, and a reason for every one that is not."""
    import shutil

    from lexora import zstd_core

    def which(name: str, *fallbacks: str) -> str | None:
        for candidate in (name, *fallbacks):
            if bin_dir:
                path = bin_dir / candidate
                if path.is_file():
                    return str(path)
            found = shutil.which(candidate)
            if found:
                return found
        return None

    available: dict = {}
    missing: dict = {}

    for level in LEVELS:
        available[f"zstd L{level}"] = lambda payload, level=level: zstd_core.compress(payload, level=level)

    ziptastic = which("ziptastic", "ziptastic-1.4.5-linux-x86_64")
    if ziptastic:
        from lexora import ziptastic_core
        available["chce (ziptastic)"] = (
            lambda payload: ziptastic_core.compress(payload, binary=ziptastic)
        )
    else:
        missing["chce (ziptastic)"] = "no ziptastic binary — set $LEXORA_ZIPTASTIC or --bin-dir"

    xz = which("xz")
    if xz:
        available["xz -9 (CLI)"] = _external(lambda: [xz, "-9", "-c"], b"")
    else:
        missing["xz -9 (CLI)"] = "no xz CLI — P0.3 wants the CLI row, not xz9-lzma"

    brotli = which("brotli")
    if brotli:
        available["brotli -q 11"] = _external(lambda: [brotli, "-q", "11", "-c"], b"")
    else:
        missing["brotli -q 11"] = "no brotli binary"

    seven = which("7z")
    if seven:
        available["ppmd (7z -m0=PPMd)"] = _seven_zip(seven)
    else:
        missing["ppmd (7z -m0=PPMd)"] = "no 7z binary — P0.3a needs this row"

    return available, missing


def _versions(bin_dir: pathlib.Path | None) -> dict:
    """What each tool said its version was — a number without its tool version is unusable."""
    import shutil
    import subprocess

    out: dict[str, str] = {}
    probes = {
        "ziptastic": ("ziptastic", "ziptastic-1.4.5-linux-x86_64"),
        "xz": ("xz",),
        "brotli": ("brotli",),
        "7z": ("7z",),
    }
    for name, candidates in probes.items():
        path = None
        for candidate in candidates:
            if bin_dir and (bin_dir / candidate).is_file():
                path = str(bin_dir / candidate)
                break
            found = shutil.which(candidate)
            if found:
                path = found
                break
        if not path:
            continue
        # `7z --version` is a command-line error; its banner comes from running it bare.
        # Collected across both attempts and matched on "7-Zip" first, because the error text
        # itself contains the word "version" ("Unsupported command: --version") and matching on
        # that recorded a failure as a version — which is how a probe lies.
        collected: list[str] = []
        for argv in ([path, "--version"], [path]):
            try:
                # Not `text=True`: 7z writes bytes in the host locale, and decoding them as UTF-8
                # raised UnicodeDecodeError — which crashed this probe *after* it had already
                # written nothing, leaving the previous artifact in place and looking current.
                proc = subprocess.run(argv, capture_output=True, timeout=30)
            except (OSError, subprocess.SubprocessError):
                continue
            raw = (proc.stdout or b"") + (proc.stderr or b"")
            collected += raw.decode("utf-8", "replace").strip().splitlines()
        banner = next((line for line in collected if "7-Zip" in line), None) or next(
            (line for line in collected
             if line.strip() and "error" not in line.lower() and "unsupported" not in line.lower()),
            None,
        )
        out[name] = banner.strip() if banner else "version unavailable"
    return out


def measure(data: bytes, *, reps: int = 3, bin_dir: pathlib.Path | None = None) -> dict:
    candidates, missing = _candidates(bin_dir)

    rows = []
    for name, fn in candidates.items():
        try:
            stored, median = _timed(fn, data, reps)
        except Exception as exc:                      # a broken binary is a missing candidate
            missing[name] = f"ran but failed: {exc}"
            continue
        rows.append({
            "candidate": name,
            "stored_bytes": stored,
            "ratio": round(stored / len(data), 4),
            # Six decimals, not four: on a small input a fast codec rounds to 0.0000 s, and a
            # zero in the fastest row divided into the multiplier and raised ZeroDivisionError —
            # in CI, where the runner is quicker than the container this was written in.
            "median_seconds": round(median, 6),
            "mib_per_second": round(len(data) / median / 1e6, 1) if median > 0 else None,
        })

    try:
        versions = _versions(bin_dir)
    except Exception as exc:                       # never lose the measurements to a banner
        versions = {"error": f"version probe failed: {exc}"}
    rows.sort(key=lambda r: r["stored_bytes"])
    cheapest_time = min(rows, key=lambda r: r["median_seconds"])
    best = rows[0]
    return {
        "input": str(DEFAULT_INPUT.relative_to(REPO)),
        "input_bytes": len(data),
        "reps": reps,
        "bin_dir": str(bin_dir) if bin_dir else None,
        "rows": rows,
        "selector_would_pick": best["candidate"],
        "fastest": cheapest_time["candidate"],
        "bytes_saved_by_picking": cheapest_time["stored_bytes"] - best["stored_bytes"],
        "percent_smaller": round(
            (cheapest_time["stored_bytes"] - best["stored_bytes"]) / cheapest_time["stored_bytes"] * 100, 2
        ),
        "time_multiplier": (
            round(best["median_seconds"] / cheapest_time["median_seconds"], 1)
            if cheapest_time["median_seconds"] > 0 else None
        ),
        "not_measured": missing,
        "tool_versions": versions,
        "scope": "ONE FILE, smoke — not a protocol-scope run (P0_RUNBOOK.md)",
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
    ap.add_argument("--bin-dir", type=pathlib.Path, default=None,
                    help="directory holding the fleet's binaries (drsamonline/heavenzip → bin/)")
    ap.add_argument("--out", type=pathlib.Path, default=None)
    args = ap.parse_args(argv)

    result = measure(args.input.read_bytes(), reps=args.reps, bin_dir=args.bin_dir)
    text = json.dumps(result, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
