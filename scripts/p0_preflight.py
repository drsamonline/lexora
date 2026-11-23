#!/usr/bin/env python3
"""P0 preflight — the four things that make a 6-hour run fail at hour five.

PATH_TO_V1 P0 is the one item blocking the headline claim, `.lxdb` and REQ-BMK-003, and until now
it was a list of *conditions* with no commands: a run that has to be assembled from the harness's
seven subcommands by someone reading three documents, on a machine nobody has described.

This is the check that runs **before** it. Every item below is something a real P0 attempt has to
get right, and every one of them is cheaper to discover in ten seconds than in the fifth hour:

| Check | Why it fails late otherwise |
|---|---|
| corpus present, ≥ 1 GiB, manifest verifies | the harness refuses an empty manifest by design; a partial snapshot fails at the first split |
| `xz` on PATH | P0.3 wants the **CLI** row, not `xz9-lzma`; discovering that afterwards means re-running every split |
| `7z` on PATH | P0.3a wants a `ppmd-7z` row in *every* split — the measurement that settles OQ-18 |
| free disk | artifacts for three splits, three reps, six systems are not small |
| machine class | P0.2 wants a **second** class; a run on the same box as R6 is a re-run, not a second class |

It writes a JSON report so the evidence of what the machine was is part of the artifact, not a
memory. Exit 2 when anything is NO-GO.

    python scripts/p0_preflight.py --corpus corpus/gutenberg-r0 \\
        --manifest benchmarks/MANIFEST.json --out benchmarks/p0-preflight.json

`--allow-missing-7z` exists for the deliberate case: running P0 without the PPMd row is a smaller
claim, and the report records that the claim is smaller.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import platform
import shutil
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent

GIB = 1 << 30
#: P0.1: the snapshot is 1.054 GiB; the protocol floor is 1 GiB.
MIN_CORPUS_BYTES = 1 * GIB
#: Three splits × 3 reps × up to six systems, plus the forked RSS probe.
MIN_FREE_BYTES = 2 * GIB


def _run(cmd: list[str]) -> str | None:
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    return (out.stdout or out.stderr).strip().splitlines()[0] if (out.stdout or out.stderr) else ""


def check_corpus(corpus: pathlib.Path, manifest_path: pathlib.Path) -> dict:
    """The corpus exists, meets the floor, and every file the manifest names is there."""
    problems: list[str] = []
    if not corpus.is_dir():
        return {"status": "NO-GO", "detail": f"no corpus at {corpus}",
                "remedy": "run `python benchmarks/harness.py corpus-fetch --dest <corpus>` or copy the snapshot"}
    if not manifest_path.is_file():
        return {"status": "NO-GO", "detail": f"no manifest at {manifest_path}",
                "remedy": "`python benchmarks/harness.py manifest --root <corpus> --out benchmarks/MANIFEST.json`"}

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    entries = manifest.get("files", [])
    total = sum(int(e.get("size_bytes", 0)) for e in entries)
    missing = [e["path"] for e in entries
               if not (corpus / e["path"]).is_file()
               or (corpus / e["path"]).stat().st_size != int(e.get("size_bytes", -1))]
    splits = sorted({e.get("split") for e in entries})

    if missing:
        problems.append(f"{len(missing)} manifest file(s) absent or wrong size (first: {missing[0]})")
    if total < MIN_CORPUS_BYTES:
        problems.append(f"corpus is {total / GIB:.2f} GiB, below the {MIN_CORPUS_BYTES / GIB:.0f} GiB protocol floor")
    if set(splits) != {"train", "validation", "heldout"}:
        problems.append(f"splits present are {splits}, the protocol needs train/validation/heldout")

    if problems:
        return {"status": "NO-GO", "detail": "; ".join(problems),
                "remedy": "fetch or restore the full snapshot; the harness refuses a partial manifest by design",
                "files": len(entries), "bytes": total, "splits": splits}
    return {"status": "GO", "detail": f"{len(entries)} files, {total / GIB:.2f} GiB, splits {splits}",
            "files": len(entries), "bytes": total, "splits": splits}


def check_binary(name: str, *, version_args: tuple[str, ...] = ("--version",),
                 bin_dir: pathlib.Path | None = None) -> dict:
    """Look in --bin-dir first, then PATH.

    The fleet ships these binaries in `drsamonline/heavenzip` under `bin/`; a machine that has
    checked that repo out should not need them installed system-wide to pass preflight.
    """
    path = None
    if bin_dir:
        candidate = bin_dir / name
        path = str(candidate) if candidate.is_file() else None
    path = path or shutil.which(name)
    if not path:
        return {"status": "NO-GO", "detail": f"{name} not on PATH", "path": None}
    version = _run([path, *version_args])
    return {"status": "GO", "detail": version or path, "path": path}


def check_disk(root: pathlib.Path) -> dict:
    target = root if root.exists() else root.parent
    usage = shutil.disk_usage(target)
    free = usage.free
    return {
        "status": "GO" if free >= MIN_FREE_BYTES else "NO-GO",
        "detail": f"{free / GIB:.2f} GiB free at {target} (need {MIN_FREE_BYTES / GIB:.0f} GiB)",
        "free_bytes": free,
        "required_bytes": MIN_FREE_BYTES,
    }


def machine_class() -> dict:
    """Record what machine this is, so P0.2's "second class" is evidence rather than memory."""
    import os
    return {
        "machine": platform.machine(),
        "system": platform.system(),
        "release": platform.release(),
        "processor": platform.processor() or "unknown",
        "cpu_count": os.cpu_count(),
        "python": platform.python_version(),
        "hostname": platform.node(),
    }


def same_class_as(previous: dict, current: dict) -> bool:
    """Two runs are the same machine class when arch, CPU count and processor agree.

    Deliberately not hostname: the point of P0.2 is a *different box*, so a rename must not be
    able to look like a new class — and the same box under a new name must not either.
    """
    keys = ("machine", "cpu_count", "processor")
    return all(previous.get(k) == current.get(k) for k in keys)


def preflight(corpus: pathlib.Path, manifest: pathlib.Path, *, out_root: pathlib.Path,
              allow_missing_7z: bool = False, previous_env: pathlib.Path | None = None,
              bin_dir: pathlib.Path | None = None) -> dict:
    checks: dict[str, dict] = {
        "corpus": check_corpus(corpus, manifest),
        "xz_cli": check_binary("xz", bin_dir=bin_dir),
        "ppmd_7z": check_binary("7z", bin_dir=bin_dir),
        "disk": check_disk(out_root),
    }
    if checks["xz_cli"]["status"] != "GO":
        checks["xz_cli"]["remedy"] = "install xz-utils: P0.3 wants the CLI row, not xz9-lzma"
    if checks["ppmd_7z"]["status"] != "GO":
        if allow_missing_7z:
            checks["ppmd_7z"].update(
                status="WAIVED",
                detail="7z absent — P0 can run, but the ppmd-7z row will be missing from every split "
                       "and OQ-18 stays open. The claim this run supports is smaller.",
            )
        else:
            checks["ppmd_7z"]["remedy"] = (
                "install p7zip-full for P0.3a, or pass --allow-missing-7z to record a smaller claim"
            )
    if checks["disk"]["status"] != "GO":
        checks["disk"]["remedy"] = "free space, or point --out-root at a bigger volume"

    current = machine_class()
    second_class = None
    if previous_env and previous_env.is_file():
        previous = json.loads(previous_env.read_text(encoding="utf-8"))
        previous_class = previous.get("machine_class") or {
            k: previous.get(k) for k in ("machine", "cpu_count", "processor")
        }
        second_class = not same_class_as(previous_class, current)

    blocking = [name for name, c in checks.items() if c["status"] == "NO-GO"]
    return {
        "purpose": "P0 preflight (PATH_TO_V1 P0.1–P0.3a, P0.2 evidence)",
        "corpus": str(corpus),
        "manifest": str(manifest),
        "checks": checks,
        "machine_class": current,
        "second_machine_class": second_class,
        "second_class_note": (
            None if second_class is None
            else ("this is a different class from the recorded environment — P0.2 satisfied"
                  if second_class else
                  "SAME class as the recorded environment: P0.2 needs a second one, and this run "
                  "would be a re-run of R6's machine, not a second class")
        ),
        "blocking": blocking,
        "verdict": "GO" if not blocking else "NO-GO",
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--corpus", required=True, type=pathlib.Path)
    ap.add_argument("--manifest", required=True, type=pathlib.Path)
    ap.add_argument("--out-root", type=pathlib.Path, default=pathlib.Path("."),
                    help="where artifacts will be written (disk is checked here)")
    ap.add_argument("--previous-env", type=pathlib.Path, default=REPO / "benchmarks" / "env.json")
    ap.add_argument("--allow-missing-7z", action="store_true")
    ap.add_argument("--bin-dir", type=pathlib.Path, default=None,
                    help="directory holding the fleet's binaries (drsamonline/heavenzip → bin/)")
    ap.add_argument("--out", type=pathlib.Path, default=None)
    args = ap.parse_args(argv)

    report = preflight(args.corpus, args.manifest, out_root=args.out_root,
                       allow_missing_7z=args.allow_missing_7z, previous_env=args.previous_env,
                       bin_dir=args.bin_dir)

    for name, check in report["checks"].items():
        print(f"  {check['status']:6s} {name:9s} {check['detail']}")
        if check.get("remedy"):
            print(f"         {'':9s} → {check['remedy']}")
    if report["second_class_note"]:
        print(f"  {'note':6s} {'class':9s} {report['second_class_note']}")
    print(f"\nverdict: {report['verdict']}"
          + (f" (blocking: {', '.join(report['blocking'])})" if report["blocking"] else ""))

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return 0 if report["verdict"] == "GO" else 2


if __name__ == "__main__":
    sys.exit(main())
