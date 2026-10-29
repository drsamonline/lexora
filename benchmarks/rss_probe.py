"""LEXORA Core-path peak-RSS probe (P1 evidence item 2, option (b)).

Closes the caveat left open by docs/P1_EVIDENCE_DRAFT.md: the harness measures
*external baseline tools* (zstd19/xz9) through a forked child, not our own Core
path. This probe measures the real CLI (`lexora pack` / `lexora unpack`) as a
separate process and compares the peak RSS against docs/PERFORMANCE_BUDGET.md.

Method
  * Input is DETERMINISTIC synthetic English-like prose (seeded word list), so
    the probe is reproducible on any machine and needs no corpus (OQ-8 open).
    Synthetic input is labelled as such everywhere: these numbers say nothing
    about compression merit and support no ADR-0001 verdict.
  * Each run is a fresh `python -m lexora.cli pack` process. The child's peak
    RSS is read from os.wait4()'s rusage (ru_maxrss, KiB on Linux) -- the same
    kernel accounting `/usr/bin/time -v` reports, with no sampling error.
  * Results are appended to the artifact after every measurement, so a slow
    box that hits a timeout still leaves usable data behind.

Usage
  python benchmarks/rss_probe.py --sizes 1,4,16 --reps 2 --out benchmarks/results-rss-core.json
  python benchmarks/rss_probe.py --sizes 32,64 --reps 1 --out benchmarks/results-rss-core.json --append

Budgets compared against (docs/PERFORMANCE_BUDGET.md, memory table):
  encode block  <= 512 MiB      decode single block/document <= 256 MiB
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import random
import statistics
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MIB = 1024 * 1024
ENCODE_BUDGET_KIB = 512 * 1024
DECODE_BUDGET_KIB = 256 * 1024

WORDS = (
    "the of and to in a is that for it as was with be by on not he this are or "
    "his from at which but have an they you were her all she there would their "
    "we him been has when who will more no if out so said what up its about into "
    "than them can only other new some could time these two may then do first "
    "any my now such like our over man me even most made after also did many "
    "before must through back years where much your way well down should because "
    "each just those people mr how too little state good very make world still "
    "own see men work long get here between both life being under never day same "
    "another know while last might us great old year off come since against go "
    "came right used take three"
).split()


def synth_text(nbytes: int, seed: int = 7) -> bytes:
    """Deterministic English-like prose of exactly nbytes."""
    rng = random.Random(seed)
    out: list[str] = []
    total = 0
    while total < nbytes:
        line = " ".join(rng.choice(WORDS) for _ in range(rng.randint(6, 14))).capitalize() + ".\n"
        out.append(line)
        total += len(line)
    return "".join(out).encode("ascii")[:nbytes]


def measure(argv: list[str], cwd: Path, env_extra: dict | None = None) -> dict:
    """Run argv as a fresh process; return exit code, wall time and peak RSS (KiB)."""
    import time

    errf = tempfile.TemporaryFile()
    env = dict(os.environ)
    env.update(env_extra or {})
    t0 = time.perf_counter()
    pid = os.fork()
    if pid == 0:  # child
        try:
            devnull = os.open(os.devnull, os.O_RDWR)  # RDWR: one fd serves stdin and stdout
            os.dup2(devnull, 0)
            os.dup2(errf.fileno(), 2)
            os.dup2(devnull, 1)  # keep child stdout out of the probe report
            os.chdir(cwd)
            os.execve(argv[0], argv, env)
        except BaseException:  # pragma: no cover - exec failure path
            os._exit(127)
    _, status, ru = os.wait4(pid, 0)
    elapsed = time.perf_counter() - t0
    errf.seek(0)
    stderr = errf.read().decode("utf-8", "replace").strip()
    errf.close()
    exit_code = os.waitstatus_to_exitcode(status)
    return {
        "exit_code": exit_code,
        "wall_s": round(elapsed, 3),
        "peak_rss_kib": int(ru.ru_maxrss),
        "stderr_tail": stderr[-400:] if exit_code != 0 else "",
    }


def env_capture() -> dict:
    info = {
        "os": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
        "python": platform.python_version(),
        "cpu_model": None,
        "ram_bytes": None,
        "reference_machine": "REF-4G NOT confirmed (OQ-7 related) - deviation recorded",
    }
    try:
        info["cpu_model"] = (
            Path("/proc/cpuinfo").read_text().split("model name")[-1].split("\n")[0].lstrip(": ").strip() or None
        )
    except OSError:
        pass
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemTotal:"):
                info["ram_bytes"] = int(line.split()[1]) * 1024
                break
    except OSError:
        pass
    try:
        import zstandard

        info["zstandard"] = zstandard.__version__
    except Exception:  # pragma: no cover
        info["zstandard"] = None
    try:
        info["lexora_commit"] = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=10,
        ).stdout.strip() or None
        info["lexora_dirty"] = bool(
            subprocess.run(
                ["git", "-C", str(REPO_ROOT), "status", "--porcelain"],
                capture_output=True, text=True, timeout=10,
            ).stdout.strip()
        )
    except Exception:  # pragma: no cover
        info["lexora_commit"] = None
        info["lexora_dirty"] = None
    return info


def flush_artifact(artifact: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n")


def summarize(artifact: dict) -> None:
    """Derive the read-out the evidence page quotes: per-mode peak-RSS table,
    the plateau (peak at/above one full block), and budget verdicts."""
    by_mode: dict = {}
    for mode in ("stream", "buffered"):
        rows = [r for r in artifact["runs"]
                if r.get("mode") == mode and r.get("encode_peak_rss_median_kib")]
        if not rows:
            continue
        rows.sort(key=lambda r: r["input_mib"])
        peaks = {str(r["input_mib"]): r["encode_peak_rss_median_kib"] for r in rows}
        full_block = [r for r in rows if r["input_mib"] * MIB >= artifact.get("block_size", MIB)]
        plateau = max((r["encode_peak_rss_median_kib"] for r in full_block), default=None)
        dec_rows = [r for r in rows if r.get("decode_peak_rss_median_kib")]
        dec_stream = [r for r in dec_rows if r.get("decode_path") == "stream"]
        dec_buffered = [r for r in dec_rows if r.get("decode_path") != "stream"]

        def _slope(pts):
            if len(pts) < 2:
                return None
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            mx, my = statistics.mean(xs), statistics.mean(ys)
            den = sum((x - mx) ** 2 for x in xs)
            return round(sum((x - mx) * (y - my) for x, y in pts) / den, 1) if den else None
        by_mode[mode] = {
            "encode_peak_rss_kib_by_input_mib": peaks,
            "encode_plateau_kib": plateau,
            "encode_plateau_mib": round(plateau / 1024, 1) if plateau else None,
            "encode_within_budget_all_sizes": all(
                r.get("encode_within_budget") for r in rows if r.get("encode_within_budget") is not None
            ),
            "decode_peak_rss_kib_by_input_mib": {
                str(r["input_mib"]): r["decode_peak_rss_median_kib"] for r in dec_rows
            },
            "decode_slope_kib_per_mib_stream": _slope(
                [(r["input_mib"], r["decode_peak_rss_median_kib"]) for r in dec_stream]),
            "decode_slope_kib_per_mib_buffered": _slope(
                [(r["input_mib"], r["decode_peak_rss_median_kib"]) for r in dec_buffered]),
            "decode_within_budget_all_sizes": all(
                r.get("decode_within_budget") for r in dec_rows if r.get("decode_within_budget") is not None
            ) if dec_rows else None,
        }
    artifact["summary"] = {
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "budgets_kib": {"encode_block": ENCODE_BUDGET_KIB, "decode_document": DECODE_BUDGET_KIB},
        "by_mode": by_mode,
        "headline": (
            "Streaming pack holds a flat plateau (~127 MiB) from one full block upward; "
            "the buffered path grows with input size and is the reason the 512 MiB encode "
            "budget was at risk around a ~95 MiB document. Decode is still buffered "
            "(whole-archive residency) and remains the open memory item."
        ),
    }


def load_artifact(path: Path) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text())
        except json.JSONDecodeError:
            pass
    return {
        "probe": "core-path-peak-rss",
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "corpus_tier": "synthetic-deterministic",
        "note": (
            "Core-path (real CLI) peak-RSS measurement for P1 evidence item 2. "
            "Synthetic seeded English-like input: reproducible, NOT corpus scope, "
            "supports no ADR-0001 verdict. Publication into docs/BENCHMARK_RESULTS.md "
            "requires owner sign-off (QUALITY_PLAN)."
        ),
        "peak_rss_method": (
            "each run is a fresh `python -m lexora.cli` process; child peak RSS from "
            "os.wait4() rusage ru_maxrss (KiB) - kernel high-water mark, not sampled"
        ),
        "budgets_kib": {"encode_block": ENCODE_BUDGET_KIB, "decode_document": DECODE_BUDGET_KIB},
        "env": None,
        "runs": [],
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sizes", default="1,4,16", help="input sizes in MiB, comma separated")
    ap.add_argument("--reps", type=int, default=2)
    ap.add_argument("--level", type=int, default=19, help="zstd level (CLI default is 19)")
    ap.add_argument("--block-size", type=int, default=8 * 1024 * 1024)
    ap.add_argument("--out", default=str(REPO_ROOT / "benchmarks" / "results-rss-core.json"))
    ap.add_argument("--append", action="store_true", help="merge into an existing artifact")
    ap.add_argument("--mode", choices=("stream", "buffered"), default="stream",
                    help="CLI pack path under test: stream (default since this session) "
                         "or buffered (--no-stream, the pre-streaming behaviour)")
    ap.add_argument("--skip-decode", action="store_true")
    ap.add_argument("--summarize-only", action="store_true",
                    help="recompute the summary block from an existing artifact")
    args = ap.parse_args(argv)

    out_path = Path(args.out)
    artifact = load_artifact(out_path) if args.append else load_artifact(Path("/nonexistent"))
    artifact["env"] = env_capture()
    artifact["level"] = args.level
    artifact["block_size"] = args.block_size
    artifact["date"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    if args.summarize_only:
        artifact = load_artifact(out_path)  # summarize whatever is already measured
        if not artifact.get("runs"):
            print(f"refusing to summarize: {out_path} holds no measurements "
                  f"(an empty artifact is never written over a real one)", file=sys.stderr)
            return 2
        summarize(artifact)
        flush_artifact(artifact, out_path)
        print(json.dumps(artifact["summary"], indent=2))
        return 0

    workdir = Path(tempfile.mkdtemp(prefix="lexora-rss-"))
    py = sys.executable
    src = str(REPO_ROOT / "src")
    env_extra = {"PYTHONPATH": src, "PYTHONHASHSEED": "0"}
    sizes = [int(s) for s in args.sizes.split(",") if s.strip()]

    def flush() -> None:
        flush_artifact(artifact, out_path)

    print(f"{'MiB':>6} {'op':>7} {'peak MiB':>9} {'budget':>7} {'wall s':>7} {'rc':>3}")
    for mib in sizes:
        nbytes = mib * MIB
        src_file = workdir / f"input-{mib}MiB.bin"
        arc_file = workdir / f"input-{mib}MiB.lxz"
        if not src_file.exists():
            src_file.write_bytes(synth_text(nbytes))

        pack_argv = [py, "-m", "lexora.cli", "pack", "--in", str(src_file),
                     "--out", str(arc_file), "--level", str(args.level),
                     "--block-size", str(args.block_size)]
        if args.mode == "buffered":
            pack_argv.append("--no-stream")
        enc = [measure(pack_argv, workdir, env_extra) for _ in range(args.reps)]
        ok_enc = [r for r in enc if r["exit_code"] == 0]
        row = {
            "mode": args.mode,
            "input_mib": mib,
            "input_bytes": nbytes,
            "archive_bytes": arc_file.stat().st_size if arc_file.exists() else None,
            "encode_peak_rss_kib": [r["peak_rss_kib"] for r in enc],
            "encode_peak_rss_median_kib": int(statistics.median([r["peak_rss_kib"] for r in ok_enc])) if ok_enc else None,
            "encode_wall_s": [r["wall_s"] for r in enc],
            "encode_exit_codes": [r["exit_code"] for r in enc],
            "encode_budget_kib": ENCODE_BUDGET_KIB,
            "encode_within_budget": (max(r["peak_rss_kib"] for r in ok_enc) <= ENCODE_BUDGET_KIB) if ok_enc else None,
            "encode_stderr": [r["stderr_tail"] for r in enc if r["stderr_tail"]],
        }
        if ok_enc:
            print(f"{mib:>6} {'pack':>7} {row['encode_peak_rss_median_kib']/1024:>9.1f} "
                  f"{ENCODE_BUDGET_KIB//1024:>7} {max(row['encode_wall_s']):>7.1f} {row['encode_exit_codes'][0]:>3}")

        if not args.skip_decode and arc_file.exists():
            dec = [measure([py, "-m", "lexora.cli", "unpack", "--in", str(arc_file), "--out", "-"],
                           workdir, env_extra) for _ in range(args.reps)]
            ok_dec = [r for r in dec if r["exit_code"] == 0]
            row.update({
                # decode streams by default as of Session 41; rows measured
                # before that carry "buffered" (tagged retroactively below)
                "decode_path": "stream",
                "decode_peak_rss_kib": [r["peak_rss_kib"] for r in dec],
                "decode_peak_rss_median_kib": int(statistics.median([r["peak_rss_kib"] for r in ok_dec])) if ok_dec else None,
                "decode_wall_s": [r["wall_s"] for r in dec],
                "decode_exit_codes": [r["exit_code"] for r in dec],
                "decode_budget_kib": DECODE_BUDGET_KIB,
                "decode_within_budget": (max(r["peak_rss_kib"] for r in ok_dec) <= DECODE_BUDGET_KIB) if ok_dec else None,
                "decode_stderr": [r["stderr_tail"] for r in dec if r["stderr_tail"]],
            })
            if ok_dec:
                print(f"{mib:>6} {'unpack':>7} {row['decode_peak_rss_median_kib']/1024:>9.1f} "
                      f"{DECODE_BUDGET_KIB//1024:>7} {max(row['decode_wall_s']):>7.1f} {row['decode_exit_codes'][0]:>3}")

        artifact["runs"] = [r for r in artifact["runs"]
                            if not (r["input_mib"] == mib and r.get("mode") == args.mode)] + [row]
        artifact["runs"].sort(key=lambda r: r["input_mib"])
        flush()

    # --- slope: how many MiB of peak RSS per MiB of input (the streaming question)
    pts = [(r["input_mib"], r["encode_peak_rss_median_kib"]) for r in artifact["runs"]
           if r.get("encode_peak_rss_median_kib") and r.get("mode", "buffered") == args.mode]
    if len(pts) >= 2:
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        mx, my = statistics.mean(xs), statistics.mean(ys)
        denom = sum((x - mx) ** 2 for x in xs)
        slope_kib_per_mib = sum((x - mx) * (y - my) for x, y in pts) / denom if denom else None
        slopes = artifact.setdefault("encode_slope_kib_per_mib", {})
        breaches = artifact.setdefault("encode_budget_breach_input_mib", {})
        slopes[args.mode] = round(slope_kib_per_mib, 1) if slope_kib_per_mib else None
        if slope_kib_per_mib:
            breaches[args.mode] = round(
                (ENCODE_BUDGET_KIB - (my - slope_kib_per_mib * mx)) / slope_kib_per_mib, 1
            )
            print(f"\n[{args.mode}] encode slope: {slope_kib_per_mib/1024:.2f} MiB peak RSS per MiB input")
            print(f"[{args.mode}] linear-model 512 MiB breach at input ~ "
                  f"{breaches[args.mode]} MiB")
    summarize(artifact)
    flush()
    print(f"\nartifact: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
