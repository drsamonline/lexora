"""LEXORA benchmark harness (P1 scaffolding — protocol-compliant, corpus-gated).

Implements the *mechanical* parts of docs/BENCHMARK_PROTOCOL.md that do not
require the corpus (OQ-8 still open):

  * env capture -> env.json            (protocol §6.1)
  * manifest create/verify             (§1: SHA-256 per file + lineage id)
  * split audit (leakage control)      (§2 / REQ-EXP-002)
  * cost accounting                    (§4 / REQ-CMP-004: total stored bytes
    == actual size on disk, byte-exact; harness asserts it)
  * system registry                    (§3 frozen baselines + LEXORA baseline)
  * N-repeat runs with min/median/max  (§6.3)
  * results JSON writer                (§6.5; BENCHMARK_RESULTS stays empty
    until a valid corpus run exists — honesty constraint §8)

Honesty notes:
  * NO benchmark numbers exist yet and none can be produced until a corpus is
    supplied under CORPUS_POLICY terms. `run` on an empty manifest fails loudly.
  * Only systems actually importable in this environment are enabled:
    zstd-19 via python-zstandard (installed, tested) and xz via CLI (`xz`,
    present). brotli / PPMd CLIs are NOT installed here -> auto-skipped with a
    recorded reason, never faked.
  * Raw outputs go to benchmarks/raw/ (gitignored); only the aggregated JSON
    artifact path is printed for commit-level references.

Usage:
  python benchmarks/harness.py env
  python benchmarks/harness.py manifest --root DIR --out MANIFEST.json [--lineage-map lm.json]
  python benchmarks/harness.py verify --manifest MANIFEST.json
  python benchmarks/harness.py audit-splits --manifest MANIFEST.json
  python benchmarks/harness.py run --manifest MANIFEST.json --out ARTIFACT.json [--reps 3] [--systems zstd19,xz]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import shutil
import statistics
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

MANIFEST_VERSION = 1
SPLIT_FRACTIONS = {"train": 0.70, "validation": 0.10, "heldout": 0.20}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------- env capture (protocol §6.1) ----------

def cmd_env(args: argparse.Namespace) -> int:
    info: dict = {
        "os": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
        "python": platform.python_version(),
        "cpu_model": None,
        "ram_bytes": None,
        "tools": {},
        "libs": {},
    }
    try:
        info["cpu_model"] = Path("/proc/cpuinfo").read_text().split("model name")[-1].split("\n")[0].lstrip(": ").strip() or None
    except OSError:
        pass
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemTotal:"):
                info["ram_bytes"] = int(line.split()[1]) * 1024
                break
    except OSError:
        pass
    for tool in ("zstd", "xz", "brotli", "7z"):
        p = shutil.which(tool)
        if p:
            try:
                out = subprocess.run([tool, "--version"], capture_output=True, text=True, timeout=10)
                info["tools"][tool] = {"path": p, "version": (out.stdout or out.stderr).splitlines()[0].strip()}
            except Exception as exc:  # record failure honestly
                info["tools"][tool] = {"path": p, "version": f"ERROR: {exc}"}
        else:
            info["tools"][tool] = None
    for lib in ("zstandard",):
        try:
            mod = __import__(lib)
            info["libs"][lib] = str(getattr(mod, "__version__", getattr(mod, "ZSTD_VERSION", "unknown")))
        except ImportError:
            info["libs"][lib] = None
    # git identity of the harness itself (§6.5 wants commit hash)
    try:
        rev = subprocess.run(["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"],
                             capture_output=True, text=True, timeout=10)
        info["git_commit"] = rev.stdout.strip() or None
    except Exception:
        info["git_commit"] = None
    dest = Path(args.out)
    dest.write_text(json.dumps(info, indent=2, sort_keys=True) + "\n")
    print(f"wrote {dest}")
    return 0


# ---------- manifest (§1) ----------

def cmd_manifest(args: argparse.Namespace) -> int:
    root = Path(args.root)
    if not root.is_dir():
        print(f"error: {root} is not a directory", file=sys.stderr)
        return 2
    lineage_map = {}
    if args.lineage_map:
        lineage_map = json.loads(Path(args.lineage_map).read_text())
    files = sorted(p for p in root.rglob("*") if p.is_file())
    entries = []
    for i, p in enumerate(files):
        rel = str(p.relative_to(root))
        lineage = lineage_map.get(rel) or p.stem  # fallback: filename stem
        # Deterministic split assignment BY LINEAGE (§2): hash lineage id,
        # same lineage always lands in the same split.
        bucket = int(hashlib.sha256(lineage.encode()).hexdigest(), 16) % 1000
        if bucket < int(SPLIT_FRACTIONS["train"] * 1000):
            split = "train"
        elif bucket < int((SPLIT_FRACTIONS["train"] + SPLIT_FRACTIONS["validation"]) * 1000):
            split = "validation"
        else:
            split = "heldout"
        # Optional sidecar metadata from corpus assembly scripts
        # (scripts/corpus/assemble_gutenberg.py writes <out>.meta.json keyed by
        # relative path). Absent sidecar -> honest defaults, never guessed.
        meta: dict = {}
        sidecar = Path(str(args.out) + ".meta.json")
        if sidecar.is_file():
            meta = json.loads(sidecar.read_text()).get(rel, {})
        entries.append({
            "path": rel,
            "sha256": sha256_file(p),
            "size_bytes": p.stat().st_size,
            "lineage_id": lineage,
            "split": split,
            "category": meta.get("category", "unclassified"),
            "language": meta.get("language", "unknown"),
            "rights": meta.get("rights", "UNCLASSIFIED"),
        })
    if not entries:
        print("warning: manifest is EMPTY — no corpus supplied (OQ-8 open)", file=sys.stderr)
    out = {"manifest_version": MANIFEST_VERSION, "root": str(root), "files": entries}
    body = json.dumps(out, indent=2, sort_keys=True)
    mh = hashlib.sha256(body.encode()).hexdigest()
    out["manifest_sha256"] = mh
    Path(args.out).write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
    print(f"wrote {args.out}: {len(entries)} files, manifest_sha256={mh}")
    return 0


def _load_manifest(path: str) -> dict:
    m = json.loads(Path(path).read_text())
    stored = m.pop("manifest_sha256", None)
    recomputed = hashlib.sha256(json.dumps(m, indent=2, sort_keys=True).encode()).hexdigest()
    m["manifest_sha256"] = stored
    if stored != recomputed:
        raise SystemExit(f"error: manifest hash mismatch (stored {stored}, recomputed {recomputed})")
    return m


def cmd_verify(args: argparse.Namespace) -> int:
    m = _load_manifest(args.manifest)
    root = Path(m["root"])
    bad = 0
    for e in m["files"]:
        p = root / e["path"]
        if not p.is_file():
            print(f"MISSING: {p}", file=sys.stderr)
            bad += 1
        elif sha256_file(p) != e["sha256"]:
            print(f"HASH MISMATCH: {p}", file=sys.stderr)
            bad += 1
    print(f"verified {len(m['files'])} files, {bad} problems, manifest_sha256={m['manifest_sha256']}")
    return 1 if bad else 0


def cmd_audit_splits(args: argparse.Namespace) -> int:
    """REQ-EXP-002: fail if any lineage id appears in two splits."""
    m = _load_manifest(args.manifest)
    seen: dict[str, str] = {}
    leaks = []
    for e in m["files"]:
        lid, sp = e["lineage_id"], e["split"]
        if lid in seen and seen[lid] != sp:
            leaks.append((lid, seen[lid], sp))
        seen.setdefault(lid, sp)
    counts = {s: 0 for s in SPLIT_FRACTIONS}
    for e in m["files"]:
        counts[e["split"]] += 1
    print(f"split file counts: {counts}")
    if leaks:
        for lid, a, b in leaks:
            print(f"LEAK: lineage '{lid}' in splits {a} and {b}", file=sys.stderr)
        return 1
    print("split audit OK: no lineage straddles splits")
    return 0


# ---------- systems (§3) ----------

def _sys_zstd19(data: bytes, out_path: Path) -> int:
    import zstandard
    params = zstandard.ZstdCompressionParameters.from_level(19)
    cctx = zstandard.ZstdCompressor(compression_params=params)
    blob = cctx.compress(data)
    out_path.write_bytes(blob)
    return len(blob)


def _sys_xz9(data: bytes, out_path: Path) -> int:
    if not shutil.which("xz"):
        raise RuntimeError("xz CLI not installed")
    with open(out_path, "wb") as fh:
        subprocess.run(["xz", "-9", "-k", "-c"], input=data, stdout=fh, check=True, timeout=600)
    return out_path.stat().st_size


SYSTEMS = {
    "zstd19": _sys_zstd19,
    "xz9": _sys_xz9,
    # brotli_q11 / ppmd: intentionally absent — tools not installed in this
    # environment (verified 2026-10-15 via harness `env`). Add real impls when
    # available; NEVER stub them to produce numbers.
}


def _available_systems(requested: list[str]) -> tuple[list[str], dict]:
    ok, skipped = [], {}
    for name in requested:
        if name not in SYSTEMS:
            skipped[name] = "not implemented in harness (see SYSTEMS comment)"
        elif name == "xz9" and not shutil.which("xz"):
            skipped[name] = "xz CLI not installed"
        elif name == "zstd19":
            try:
                import zstandard  # noqa: F401
                ok.append(name)
            except ImportError:
                skipped[name] = "python-zstandard not installed"
        else:
            ok.append(name)
    return ok, skipped


def cmd_run(args: argparse.Namespace) -> int:
    m = _load_manifest(args.manifest)
    if not m["files"]:
        print("error: empty manifest — cannot run benchmarks without a corpus "
              "(OQ-8 / CORPUS_POLICY). No numbers will be fabricated.", file=sys.stderr)
        return 1
    root = Path(m["root"])
    requested = [s.strip() for s in args.systems.split(",") if s.strip()]
    systems, skipped = _available_systems(requested)
    if not systems:
        print(f"error: no runnable systems (skipped: {skipped})", file=sys.stderr)
        return 1
    raw_dir = REPO_ROOT / "benchmarks" / "raw"
    raw_dir.mkdir(exist_ok=True)
    rows = []
    for e in m["files"]:
        data = (root / e["path"]).read_bytes()
        for name in systems:
            times_s, sizes = [], []
            for rep in range(args.reps):
                out_path = raw_dir / f"{hashlib.sha256(e['path'].encode()).hexdigest()[:12]}-{name}-{rep}.bin"
                t0 = time.perf_counter()
                n = SYSTEMS[name](data, out_path)
                dur = time.perf_counter() - t0
                # §4 cost accounting assert: reported total == size on disk
                disk = out_path.stat().st_size
                if n != disk:
                    raise SystemExit(f"cost-accounting violation: reported {n} != disk {disk} for {e['path']}/{name}")
                out_path.unlink()  # raw artifacts transient; keep repo clean
                times_s.append(dur)
                sizes.append(n)
            rows.append({
                "path": e["path"], "system": name, "split": e["split"],
                "input_bytes": e["size_bytes"],
                "stored_bytes_min": min(sizes), "stored_bytes_median": statistics.median(sizes),
                "stored_bytes_max": max(sizes),
                "encode_s_min": min(times_s), "encode_s_median": statistics.median(times_s),
                "encode_s_max": max(times_s),
            })
    artifact = {
        "benchmark_revision": args.revision,
        "date": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "manifest_sha256": m["manifest_sha256"],
        "reps": args.reps,
        "systems_run": systems,
        "systems_skipped": skipped,
        "rows": rows,
        "note": "Harness output. Publication into docs/BENCHMARK_RESULTS.md "
                "requires owner review per QUALITY_PLAN.",
    }
    Path(args.out).write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n")
    print(f"wrote {args.out}: {len(rows)} measurement rows ({len(m['files'])} files x {len(systems)} systems)")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="harness", description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("env"); e.add_argument("--out", default="benchmarks/env.json"); e.set_defaults(func=cmd_env)
    mf = sub.add_parser("manifest"); mf.add_argument("--root", required=True)
    mf.add_argument("--out", required=True); mf.add_argument("--lineage-map", default=None); mf.set_defaults(func=cmd_manifest)
    v = sub.add_parser("verify"); v.add_argument("--manifest", required=True); v.set_defaults(func=cmd_verify)
    a = sub.add_parser("audit-splits"); a.add_argument("--manifest", required=True); a.set_defaults(func=cmd_audit_splits)
    r = sub.add_parser("run"); r.add_argument("--manifest", required=True)
    r.add_argument("--out", required=True); r.add_argument("--reps", type=int, default=3)
    r.add_argument("--revision", type=int, default=0)
    r.add_argument("--systems", default="zstd19,xz9")
    r.set_defaults(func=cmd_run)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
