"""Peak-RSS probe for the **query path**: index resident, one document decoded.

Why this exists
---------------
`rss_probe.py` measures encode and decode of a `.lxz` archive. It says nothing about the
shape ADR-0016 introduced: a SQLite index that stays in memory while a query runs, plus
one document decoded on demand. That is a different memory profile and nobody has
measured it, which means the "~7 % of text" figure in ADR-0016 is a *size* claim being
read as a *memory* claim. This probe turns it into a measurement.

What it reports, per catalog size:
  * index bytes on disk (the resident floor, uncompressed by design),
  * peak RSS of `lexora db search` (index loaded, no payload decoded),
  * peak RSS of `lexora db get` (index loaded **plus** one document decoded),
  * the ratio of peak RSS to canonical text size, so a 4 GiB machine can be reasoned about
    rather than hoped about.

Usage
-----
    python3 benchmarks/index_rss_probe.py --sizes 4,16 --reps 2 --cap-mib 256
    python3 benchmarks/index_rss_probe.py --sizes 64 --out benchmarks/results-rss-index.json

`--cap-mib` is the assertion: exceed it and the process exits 1 with the failing row. On
the target hardware set it to whatever the budget is (e.g. 512 for a 4 GiB machine) and
the run becomes a pass/fail gate rather than a table.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = REPO_ROOT / "benchmarks" / "results-rss-index.json"
DEFAULT_CAP_MIB = 256

# A realistic vocabulary is the whole point of this fixture. An earlier version drew
# from 60 common words, which produced a 0.1 MiB index for 16 MiB of text — an FTS index
# costs what the *distinct term count* costs, so a tiny vocabulary measures nothing.
# Real English prose runs at roughly 10k–20k distinct words per megabyte, Zipf-shaped:
# a few very frequent words and a long tail of rare ones.
def _vocabulary(n: int, seed: int = 3) -> list[str]:
    import random

    rng = random.Random(seed)
    letters = "abcdefghijklmnopqrstuvwxyz"
    vowels = "aeiou"
    seen: set[str] = set()
    while len(seen) < n:
        length = rng.choice((3, 4, 4, 5, 5, 6, 7, 8, 9, 11))
        word = "".join(
            rng.choice(vowels) if i % 2 else rng.choice(letters) for i in range(length)
        )
        seen.add(word)
    return sorted(seen)


def synth_text(nbytes: int, seed: int = 11) -> bytes:
    """Deterministic pseudo-prose with a Zipf-shaped vocabulary of ~15k distinct words."""
    import random

    rng = random.Random(seed)
    vocab = _vocabulary(15000)
    # Zipf-ish weights: word i is chosen with probability proportional to 1/(i+1).
    weights = [1.0 / (i + 1) for i in range(len(vocab))]
    out: list[str] = []
    size = 0
    while size < nbytes:
        n_words = rng.randint(8, 18)
        sentence = " ".join(rng.choices(vocab, weights=weights, k=n_words))
        line = sentence.capitalize() + ".\n"
        out.append(line)
        size += len(line)
    return "".join(out).encode("utf-8")[:nbytes]


def measure(argv: list[str], cwd: Path) -> dict:
    """Run argv in a fresh process; return exit code, wall time and peak RSS (KiB)."""
    errf = tempfile.TemporaryFile()
    env = dict(os.environ)
    # Absolute src path, prepended: the child chdirs into a temp directory, so a
    # relative PYTHONPATH from the caller ("src:.") silently stops resolving and the
    # CLI fails to import. That produced a table of numbers measuring an import error
    # the first time this probe ran — every row said "ok" and none had run anything.
    env["PYTHONPATH"] = os.pathsep.join(
        [str(REPO_ROOT / "src"), env.get("PYTHONPATH", "")]
    ).rstrip(os.pathsep)
    t0 = time.perf_counter()
    pid = os.fork()
    if pid == 0:  # child
        try:
            devnull = os.open(os.devnull, os.O_RDWR)
            os.dup2(devnull, 0)
            os.dup2(errf.fileno(), 2)
            os.dup2(devnull, 1)
            os.chdir(cwd)
            os.execve(argv[0], argv, env)
        except BaseException:  # pragma: no cover
            os._exit(127)
    _, status, ru = os.wait4(pid, 0)
    elapsed = time.perf_counter() - t0
    errf.seek(0)
    stderr = errf.read().decode("utf-8", "replace").strip()
    errf.close()
    return {
        "exit_code": os.waitstatus_to_exitcode(status),
        "wall_s": round(elapsed, 3),
        "peak_rss_kib": int(ru.ru_maxrss),
        "stderr_tail": stderr[-300:] if stderr else "",
    }


def build_catalog(root: Path, text: bytes, docs: int = 4) -> int:
    """Populate a catalog with `docs` documents totalling ~len(text) bytes."""
    sys.path.insert(0, str(REPO_ROOT / "src"))
    from lexora.catalog import Catalog
    from lexora.canonicalize import canonicalize

    chunk = max(1, len(text) // docs)
    total = 0
    with Catalog(root, create=True) as cat:
        for i in range(docs):
            body = canonicalize(text[i * chunk:(i + 1) * chunk])
            cat.add(f"doc{i:03d}.txt", body, metadata={"bucket": str(i % 2)})
            total += len(body)
    return total


def build_catalog_subprocess(root: Path, mib: int, docs: int = 4) -> int:
    """Build the catalog in a **child**, so the measuring parent stays small.

    This is not tidiness. `os.fork()` copies the parent's address space, so the child's
    first `ru_maxrss` includes everything the parent had already allocated — building a
    16 MiB fixture in the parent made every measured row report the fixture's size
    instead of the CLI's. The probe was measuring itself.
    """
    code = (
        "import sys, pathlib;"
        f"sys.path.insert(0, {str(REPO_ROOT / 'benchmarks')!r});"
        f"sys.path.insert(0, {str(REPO_ROOT / 'src')!r});"
        "from index_rss_probe import synth_text, build_catalog;"
        f"print(build_catalog(pathlib.Path({str(root)!r}), synth_text({mib} * 1024 * 1024), docs={docs}))"
    )
    env = dict(os.environ)
    env["PYTHONPATH"] = str(REPO_ROOT / "src")
    proc = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=env)
    if proc.returncode != 0:
        raise RuntimeError(f"catalog build failed: {proc.stderr.strip()[-300:]}")
    return int(proc.stdout.strip().splitlines()[-1])


def probe_size(mib: int, reps: int, workdir: Path) -> dict:
    root = workdir / f"db{mib}"
    shutil.rmtree(root, ignore_errors=True)
    canonical = build_catalog_subprocess(root, mib)
    baseline = measure([sys.executable, "-c", "import lexora.cli"], cwd=workdir)

    index_bytes = (root / "catalog.sqlite").stat().st_size
    search, get = [], []
    for _ in range(reps):
        search.append(measure([sys.executable, "-m", "lexora.cli", "db", "search",
                               "--root", str(root), "--query", "the"], cwd=workdir))
        # `--out -` (stdout), not /dev/null: the CLI writes atomically through a
        # temp file beside the target, so /dev/null fails with EACCES on /dev.
        # measure() already sends the child's stdout to /dev/null for us.
        get.append(measure([sys.executable, "-m", "lexora.cli", "db", "get",
                            "--root", str(root), "doc000.txt", "--out", "-"],
                           cwd=workdir))
    return {
        "input_mib": mib,
        "interpreter_peak_rss_kib": baseline["peak_rss_kib"],
        "canonical_bytes": canonical,
        "index_bytes": index_bytes,
        "index_pct_of_text": round(index_bytes / canonical * 100, 2) if canonical else None,
        "search_peak_rss_kib": max(r["peak_rss_kib"] for r in search),
        "get_peak_rss_kib": max(r["peak_rss_kib"] for r in get),
        "search_wall_s": round(min(r["wall_s"] for r in search), 3),
        "get_wall_s": round(min(r["wall_s"] for r in get), 3),
        "search_exit": search[0]["exit_code"],
        "get_exit": get[0]["exit_code"],
        "errors": [r["stderr_tail"] for r in (search + get) if r["stderr_tail"]],
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sizes", default="4,16", help="catalog sizes in MiB, comma separated")
    ap.add_argument("--reps", type=int, default=2)
    ap.add_argument("--cap-mib", type=int, default=DEFAULT_CAP_MIB,
                    help="fail if any peak RSS exceeds this (KiB*1024)")
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--keep", action="store_true", help="keep the temporary catalogs")
    args = ap.parse_args(argv)

    sizes = [int(s) for s in args.sizes.split(",") if s.strip()]
    workdir = Path(tempfile.mkdtemp(prefix="lexora-index-rss-"))
    rows, failures = [], []
    try:
        for mib in sizes:
            row = probe_size(mib, args.reps, workdir)
            rows.append(row)
            for name in ("search", "get"):
                peak_mib = row[f"{name}_peak_rss_kib"] / 1024
                flag = "FAIL" if peak_mib > args.cap_mib else "ok"
                if flag == "FAIL":
                    failures.append(f"{name} at {mib} MiB: {peak_mib:.0f} MiB > cap {args.cap_mib}")
                print(f"{mib:>4} MiB catalog  {name:<6} peak {peak_mib:7.1f} MiB  "
                      f"{flag}   index {row['index_bytes']/2**20:5.1f} MiB "
                      f"({row['index_pct_of_text']}% of text)", flush=True)
    finally:
        if not args.keep:
            shutil.rmtree(workdir, ignore_errors=True)

    artifact = {
        "date": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "probe": "index_rss_probe",
        "cap_mib": args.cap_mib,
        "reps": args.reps,
        "note": ("Peak RSS of the query path: index resident plus, for `get`, one document "
                 "decoded. Compare with results-rss-core.json, which measures .lxz encode "
                 "and decode and knows nothing about the index."),
        "rows": rows,
        "failures": failures,
    }
    Path(args.out).write_text(json.dumps(artifact, indent=2) + "\n")
    print(f"\nwrote {args.out}")
    if failures:
        print("CAP EXCEEDED: " + "; ".join(failures), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
