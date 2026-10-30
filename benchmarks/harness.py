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
  * NO real-corpus benchmark numbers exist yet; they require data assembled
    under CORPUS_POLICY terms. `run` on an empty manifest fails loudly.
  * Only systems actually importable in this environment are enabled:
    zstd-19 via python-zstandard (installed, tested) and xz via CLI (`xz`,
    present). brotli / PPMd CLIs are NOT installed here -> auto-skipped with a
    recorded reason, never faked.
  * Raw outputs go to benchmarks/raw/ (gitignored); only the aggregated JSON
    artifact path is printed for commit-level references.
  * Tiered corpus fallback (Session 17): when no owner-supplied corpus exists,
    `corpus-fetch` assembles a TIER-1 snapshot of public-domain Project
    Gutenberg books (rights tier P0 per CORPUS_POLICY) into the gitignored
    `corpus/gutenberg-r0/` tree, with a generated lineage map and rights
    sidecar. Manifest entries record `corpus_tier: "T1-gutenberg-p0"` so any
    downstream results artifact states provenance explicitly. Numbers from
    such a run are *real measurements* but limited scope (English prose only;
    not the >=1 GiB multilingual REQ-BMK-001 corpus) — they may be published
    as a smoke baseline, never as the official verdict.

Usage:
  python benchmarks/harness.py env
  python benchmarks/harness.py corpus-fetch [--n 8] [--min-mb 0.5] [--dest corpus/gutenberg-r0]
  python benchmarks/harness.py corpus-reconcile --root DIR   (repair after a killed fetch)
  python benchmarks/harness.py corpus-commit [--root corpus/gutenberg-r0]
  python benchmarks/harness.py manifest --root DIR --out MANIFEST.json [--lineage-map lm.json]
  python benchmarks/harness.py verify --manifest MANIFEST.json
  python benchmarks/harness.py audit-splits --manifest MANIFEST.json
  python benchmarks/harness.py run --manifest MANIFEST.json --out ARTIFACT.json [--reps 3] [--systems zstd19,xz]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import statistics
import subprocess
import sys
import time
import pathlib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT))  # allow `from benchmarks import corpus`

from benchmarks import corpus as corpus_mod  # noqa: E402

MANIFEST_VERSION = 2  # v2 adds corpus_tier + provenance fields (Session 17)
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


# ---------- corpus tiers (Session 17: tiered fallback) ----------

def cmd_corpus_fetch(args: argparse.Namespace) -> int:
    """Assemble a snapshot corpus under the tiered fallback policy.

    Tier order: owner data in --owner-root (default data/raw/) if non-empty;
    else Project Gutenberg P0 fetch (--tier t1, default); --tier t2 forces the
    deterministic synthetic generator (offline CI smoke only).
    """
    dest = Path(args.dest)
    owner_root = Path(args.owner_root)
    if args.tier == "auto" and owner_root.is_dir() and any(owner_root.rglob("*")):
        print(f"tier T0: owner-supplied corpus found at {owner_root} — nothing to fetch. "
              f"Run `manifest --root {owner_root}` directly.")
        return 0
    if args.tier == "t2":
        snap = corpus_mod.generate_synthetic_corpus(dest)
        print(f"wrote synthetic corpus: {len(snap['files'])} files -> {dest}")
    else:
        selection = None
        if getattr(args, "catalog_limit", 0):
            cat = corpus_mod.fetch_catalog(
                pathlib.Path(args.catalog_cache) if args.catalog_cache else None
            )
            exclude = tuple(int(x) for x in args.exclude_ids.split(",") if x.strip())
            chosen = corpus_mod.select_ids_from_catalog(
                cat["path"], language="en", limit=args.catalog_limit, exclude=exclude
            )
            ids = tuple(r["id"] for r in chosen)
            min_mb = args.min_mb
            selection = {
                "method": "catalog-filter",
                "catalog_url": cat["url"],
                "catalog_sha256": cat["sha256"],
                "catalog_bytes": cat["bytes"],
                "catalog_reused_from_cache": cat["reused"],
                "filter": {"type": "Text", "language": "en"},
                "order": "PG id ascending",
                "limit": args.catalog_limit,
                "excluded_ids": list(exclude),
                "selected_count": len(ids),
                "rights_note": ("PG catalog has no rights column; selection inherits "
                                "Gutenberg's US-public-domain hosting posture and each "
                                "downloaded file carries its own licence statement. "
                                "Per-item RDF rights verification is an open item, not "
                                "implied by this record."),
            }
            print(f"catalog selection: {len(ids)} ids (limit {args.catalog_limit}) "
                  f"from catalog sha256 {cat['sha256'][:16]}…; size guard {min_mb} MB")
        elif args.ids:
            ids = tuple(int(s) for s in args.ids.split(","))
            min_mb = args.min_mb  # explicit override wins for raw id lists
        else:
            langs = [s.strip().lower() for s in args.languages.split(",") if s.strip()]
            lists = {"en": corpus_mod.ENGLISH_GUTENBERG_IDS,
                     "hi": corpus_mod.HINDI_GUTENBERG_IDS,
                     "gu": corpus_mod.GUJARATI_GUTENBERG_IDS}
            unknown = [l for l in langs if l not in lists]
            if unknown:
                print(f"error: unknown --languages values {unknown} (supported: en, hi, gu)",
                      file=sys.stderr)
                return 2
            ids = tuple(i for l in langs for i in lists[l])
            # Indic PG texts are genuinely small (~50-150 KB); the English
            # error-page guard (0.5 MB default) would discard every one of
            # them. If the user left --min-mb at its default and any Indic
            # language is requested, lower the guard to 30 KB; an explicitly
            # passed --min-mb is always respected.
            MIN_MB_DEFAULT = 0.5
            if args.min_mb == MIN_MB_DEFAULT and ("hi" in langs or "gu" in langs):
                min_mb = 0.03
            else:
                min_mb = args.min_mb
            print(f"language lists requested: {langs} -> {len(ids)} PG ids; size guard {min_mb} MB")
        snap = corpus_mod.fetch_gutenberg_snapshot(dest, ids=ids, min_mb=min_mb,
                                                  selection=selection,
                                                  rehash=args.rehash,
                                                  retry_failed=args.retry_failed,
                                                  jobs=args.jobs)
        total = sum(r["size_bytes"] for r in snap["files"])
        print(f"wrote Gutenberg snapshot: {len(snap['files'])} files, {total} bytes -> {dest}")
        if snap["failures"]:
            for f in snap["failures"]:
                print(f"FETCH FAILED (recorded, not hidden): {f['file']}: {f['error']}", file=sys.stderr)
            return 1
    return 0


def cmd_corpus_reconcile(args: argparse.Namespace) -> int:
    """Repair sidecars after an interrupted fetch, without touching the network.

    Hashes every gutenberg-*.txt in the snapshot and upserts a record for each
    file whose id belongs to the snapshot's requested set. Files outside that
    set are counted, not claimed.
    """
    root = Path(args.root)
    if not root.is_dir():
        print(f"error: {root} is not a directory", file=sys.stderr)
        return 2
    summary = corpus_mod.reconcile_snapshot(root)
    print(f"reconciled {root}: {summary['recovered']} recovered, "
          f"{summary['already_recorded']} already recorded, {summary['orphaned']} orphaned "
          f"(outside the requested id set); record now covers {summary['files']} files, "
          f"{summary['bytes']} bytes")
    return 0


def cmd_corpus_commit(args: argparse.Namespace) -> int:
    """Copy a snapshot's provenance sidecars into the COMMITTED evidence dir
    (benchmarks/provenance/<name>/). Raw texts stay gitignored; only the small
    JSON files (lineage map, rights metadata, fetch record) are committed."""
    root = Path(args.root)
    if not root.is_dir():
        print(f"error: {root} is not a directory", file=sys.stderr)
        return 2
    copied = corpus_mod.commit_sidecars(root)
    if not copied:
        print(f"warning: no sidecars found next to {root} — nothing committed", file=sys.stderr)
        return 1
    for base, dest in sorted(copied.items()):
        print(f"committed: {dest}")
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
    # Corpus tier: explicit flag wins; else read snapshot sidecar; else owner-default label.
    tier = args.tier or corpus_mod.read_snapshot_tier(root) or corpus_mod.TIER_LABEL_T0
    provenance_path = Path(str(root) + ".sources.json")
    if not provenance_path.is_file():
        # Committed provenance copy (corpus-commit) is the fallback evidence.
        provenance_path = REPO_ROOT / "benchmarks" / "provenance" / root.name / "sources.json"
    provenance = json.loads(provenance_path.read_text()) if provenance_path.is_file() else None
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
        # (corpus-fetch writes <root>.meta.json keyed by relative filename).
        # Resolution order (Session 18, R2 fix): local gitignored sidecar >
        # COMMITTED provenance copy (benchmarks/provenance/<snapshot-name>/) >
        # honest defaults. Absent everywhere -> never guessed.
        meta: dict = {}
        for sidecar in (Path(str(root) + ".meta.json"),
                        REPO_ROOT / "benchmarks" / "provenance" / root.name / "meta.json"):
            if sidecar.is_file():
                meta = json.loads(sidecar.read_text()).get(rel, {})
                break
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
    out = {
        "manifest_version": MANIFEST_VERSION,
        "root": str(root),
        "corpus_tier": tier,
        "provenance": provenance,  # snapshot record (urls+hashes) when generated by corpus-fetch
        "files": entries,
    }
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


def _sys_lexora(data: bytes, out_path: Path) -> int:
    """LEXORA itself: canonicalize, then wrap in the `.lxz` v0 container.

    Measured as a *system* so the project's own pipeline sits in the same table as
    the frozen baselines, on the same files, with the same accounting. The stored
    bytes include the container overhead (128 B header + 56 B/block index + 40 B
    trailer) because REQ-CMP-004 says nothing is free: if the decoder needs it, it
    counts. Level follows `lexora.DEFAULT_LEVEL` (ADR-0012), so the row states the
    operating point the CLI actually ships.

    Deliberately in-process like `_sys_zstd19`, not a subprocess: the harness's
    peak-RSS method forks a child around this callable, and an extra interpreter
    would be measured as if it were ours.
    """
    from lexora import DEFAULT_LEVEL
    from lexora.canonicalize import canonicalize
    from lexora.container import pack as lxz_pack

    canonical = canonicalize(data)
    archive = lxz_pack(canonical, level=DEFAULT_LEVEL)
    out_path.write_bytes(archive)
    return len(archive)


def _sys_lexora19(data: bytes, out_path: Path) -> int:
    """LEXORA at zstd level 19 — the size-comparable row.

    The shipped default is `DEFAULT_LEVEL` (9, ADR-0012), which trades ~14 % more
    bytes for ~9x the speed. Comparing that against a level-19 baseline would
    mostly measure the level, not the pipeline, so this row exists to hold the
    level constant and expose what the container itself costs.
    """
    from lexora.canonicalize import canonicalize
    from lexora.container import pack as lxz_pack

    archive = lxz_pack(canonicalize(data), level=19)
    out_path.write_bytes(archive)
    return len(archive)


def _sys_xz9_lzma(data: bytes, out_path: Path) -> int:
    """xz preset 9 through Python's `lzma` (liblzma), for hosts without the CLI.

    Same algorithm and preset as `_sys_xz9`, different entry point: this sandbox has
    no `xz` binary (verified Session 62), and stdlib `lzma` produces genuine `.xz`
    streams. The artifact records which implementation ran, because "xz -9" and
    "liblzma preset 9 through CPython" are the same format but not the same process —
    a distinction that matters for a timing number and not at all for a size number.
    """
    import lzma

    blob = lzma.compress(data, format=lzma.FORMAT_XZ, preset=9)
    out_path.write_bytes(blob)
    return len(blob)


SYSTEMS = {
    "lexora": _sys_lexora,
    "lexora19": _sys_lexora19,
    "zstd19": _sys_zstd19,
    "xz9": _sys_xz9,
    "xz9-lzma": _sys_xz9_lzma,
    # "lexora" is OUR pipeline (canon + .lxz v0), not a baseline: it exists so the
    # project's own numbers appear beside the frozen baselines on identical inputs.
    # brotli_q11 / ppmd: intentionally absent — tools not installed in this
    # environment (verified 2026-10-15 via harness `env`). Add real impls when
    # available; NEVER stub them to produce numbers.
}


def _available_systems(requested: list[str]) -> tuple[list[str], dict]:
    """Split requested systems into runnable and skipped, with a reason for each.

    Written as explicit branches that each terminate, after Session 62 shipped a
    branch that forgot `ok.append(name)` — the system then appeared in NEITHER list
    and vanished from the run without a word. The final assertion makes that class
    of mistake impossible: every requested name must land in exactly one list.
    """
    ok, skipped = [], {}
    for name in requested:
        if name not in SYSTEMS:
            skipped[name] = "not implemented in harness (see SYSTEMS comment)"
            continue
        if name == "xz9":
            if shutil.which("xz"):
                ok.append(name)
            else:
                skipped[name] = "xz CLI not installed (try xz9-lzma)"
            continue
        if name == "xz9-lzma":
            try:
                import lzma  # noqa: F401

                ok.append(name)
            except ImportError:  # pragma: no cover - interpreter without liblzma
                skipped[name] = "stdlib lzma unavailable in this interpreter"
            continue
        if name == "zstd19":
            try:
                import zstandard  # noqa: F401

                ok.append(name)
            except ImportError:  # pragma: no cover
                skipped[name] = "python-zstandard not installed"
            continue
        ok.append(name)
    unaccounted = set(requested) - set(ok) - set(skipped)
    if unaccounted:  # pragma: no cover - defensive, see docstring
        raise SystemExit(f"internal error: systems in neither list: {sorted(unaccounted)}")
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

    # Subset selection for smoke revisions (Session 60). The FULL manifest hash is
    # verified above before this runs, so a subset never weakens provenance; what
    # the artifact records is the parent hash plus exactly how the subset was cut.
    subset = None
    if args.split or args.max_bytes:
        selected, budget, seen = [], args.max_bytes or 0, 0
        for e in m["files"]:
            if args.split and e.get("split") != args.split:
                continue
            selected.append(e)
            seen += e["size_bytes"]
            if args.max_bytes and seen >= args.max_bytes:
                break
        if not selected:
            print(f"error: subset selectors matched no files "
                  f"(split={args.split!r}, max_bytes={args.max_bytes})", file=sys.stderr)
            return 1
        subset = {
            "selector": {"split": args.split, "max_bytes": args.max_bytes},
            "files": len(selected),
            "input_bytes": sum(e["size_bytes"] for e in selected),
            "note": "smoke-scope subset of the parent manifest — never protocol scope",
        }
        m = dict(m, files=selected)
        print(f"subset: {subset['files']} files, {subset['input_bytes'] / 2**20:.1f} MiB "
              f"(parent manifest_sha256 {m['manifest_sha256'][:16]}…)")
    rows = []
    # P1-T6: peak RSS per system. The encode call runs in a forked child;
    # the parent samples /proc/<pid>/status VmHWM while the child is alive
    # (Linux). VmHWM is the kernel's true high-water mark — sampling cannot
    # under-report it. ru_maxrss via RUSAGE_CHILDREN is NOT used: CPython
    # only reports child usage to the parent when the child exits by signal,
    # which would force artificial crashes on the measured path.
    def _peak_rss_kib(fn, data: bytes, out_path: Path) -> int | None:
        if not Path("/proc").is_dir():
            return None  # non-Linux: no reliable mechanism; report honestly
        pid = os.fork()
        if pid == 0:
            # Child: exit code 2 signals "encode raised" so the parent can
            # distinguish failure from success (exit 1 would be ambiguous
            # with a deliberate failure signal). Pass out_path as Path —
            # SYSTEMS callables use Path methods (write_bytes / open).
            try:
                fn(data, out_path)
            except BaseException:
                os._exit(2)
            os._exit(0)
        hwm_kib = None
        status_path = f"/proc/{pid}/status"
        while True:
            try:
                with open(status_path) as fh:
                    for line in fh:
                        if line.startswith("VmHWM:"):
                            hwm_kib = int(line.split()[1])
                            break
            except (FileNotFoundError, ProcessLookupError, PermissionError):
                break  # child exited; last observed VmHWM stands
            try:
                done_pid, wait_status = os.waitpid(pid, os.WNOHANG)
            except ChildProcessError:
                break  # already reaped elsewhere; last observed VmHWM stands
            if done_pid != 0:
                return _finish(wait_status, hwm_kib)
            time.sleep(0.002)
        try:
            _, status = os.waitpid(pid, 0)
        except ChildProcessError:
            status = 0
        return _finish(status, hwm_kib)

    def _finish(status: int, hwm_kib: int | None) -> int | None:
        if os.WIFSIGNALED(status) or os.WEXITSTATUS(status) != 0:
            return -1  # child failed; usage number would be meaningless
        return hwm_kib if hwm_kib is not None else -1

    rss_skipped_reason = None
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
            row = {
                "path": e["path"], "system": name, "split": e["split"],
                "input_bytes": e["size_bytes"],
                "stored_bytes_min": min(sizes), "stored_bytes_median": statistics.median(sizes),
                "stored_bytes_max": max(sizes),
                "encode_s_min": min(times_s), "encode_s_median": statistics.median(times_s),
                "encode_s_max": max(times_s),
            }
            rows.append(row)
    # Peak RSS: one measurement per (file, system) on the median-sized input
    # set would be ideal; protocol only requires *a* recorded peak per run.
    # We measure each system once, on the largest manifest file, via fork.
    peaks_kib: dict[str, int] = {}
    if m["files"]:
        biggest = max(m["files"], key=lambda x: x["size_bytes"])
        data = (root / biggest["path"]).read_bytes()
        for name in systems:
            out_path = raw_dir / f"rss-{name}.bin"
            r = _peak_rss_kib(SYSTEMS[name], data, out_path)
            out_path.unlink(missing_ok=True)
            if r is not None and r >= 0:
                peaks_kib[name] = r
    if not peaks_kib:
        rss_skipped_reason = (
            "peak-RSS capture unavailable or every forked measurement failed "
            "(VmHWM sampling is Linux-only; child failures are recorded as -1, "
            "never faked); P1-T6 remains open for this run"
        )
    artifact = {
        "benchmark_revision": args.revision,
        "date": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "manifest_sha256": m["manifest_sha256"],
        "subset": subset,
        "corpus_tier": m.get("corpus_tier", "UNKNOWN — pre-v2 manifest"),
        "provenance_present": m.get("provenance") is not None,
        "reps": args.reps,
        "systems_run": systems,
        "systems_skipped": skipped,
        "peak_rss_kib_by_system": peaks_kib or None,
        "peak_rss_method": (
            "forked child runs the identical encode call; parent samples "
            "/proc/<pid>/status VmHWM (KiB, Linux) until exit; measured "
            "once per system on the largest manifest file"
            if peaks_kib else None
        ),
        "peak_rss_skipped_reason": rss_skipped_reason,
        "rows": rows,
        "note": "Harness output. Publication into docs/BENCHMARK_RESULTS.md "
                "requires owner review per QUALITY_PLAN. Tier label above is "
                "MANDATORY alongside any published number from this artifact.",
    }
    Path(args.out).write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n")
    print(f"wrote {args.out}: {len(rows)} measurement rows ({len(m['files'])} files x {len(systems)} systems)")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="harness", description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("env"); e.add_argument("--out", default="benchmarks/env.json"); e.set_defaults(func=cmd_env)
    cf = sub.add_parser("corpus-fetch", help="tiered corpus fallback (T0 owner > T1 Gutenberg P0 > T2 synthetic)")
    cf.add_argument("--dest", default="corpus/gutenberg-r0")
    cf.add_argument("--owner-root", default="data/raw")
    cf.add_argument("--tier", choices=["auto", "t1", "t2"], default="auto")
    cf.add_argument("--ids", default=None, help="comma-separated PG ids (overrides --languages)")
    cf.add_argument("--languages", default="en", help="curated language lists: en,hi,gu (comma-separated)")
    cf.add_argument("--min-mb", type=float, default=0.5)
    cf.add_argument("--catalog-limit", type=int, default=0,
                    help="select this many English Text ids from PG's official catalog "
                         "instead of the curated list (0 = curated list). Selection is "
                         "deterministic: filter then order by PG id ascending.")
    cf.add_argument("--catalog-cache", default=None,
                    help="where to keep pg_catalog.csv (default corpus/_catalog, gitignored)")
    cf.add_argument("--jobs", type=int, default=1,
                    help="fetch this many ids concurrently (default 1); the record is "
                         "still assembled in id order, so sidecars are unchanged. Unlike "
                         "batch --jobs this is a real gain: the work is network-bound, so "
                         "8 threads fetch ~50%% more files per pass than 1")
    cf.add_argument("--retry-failed", action="store_true",
                    help="re-attempt ids already recorded as failed (404s, undersized "
                         "payloads); off by default because it dominates a pass")
    cf.add_argument("--rehash", action="store_true",
                    help="verify every existing file by SHA-256 instead of trusting "
                         "the recorded (size, mtime_ns) — slower, paranoid")
    cf.add_argument("--exclude-ids", default="",
                    help="comma-separated PG ids to leave out of a catalog selection"); cf.set_defaults(func=cmd_corpus_fetch)
    cr = sub.add_parser("corpus-reconcile",
                        help="rebuild provenance sidecars from the texts on disk "
                             "(repairs a fetch that was killed mid-run)")
    cr.add_argument("--root", required=True, help="snapshot directory")
    cr.set_defaults(func=cmd_corpus_reconcile)

    cc = sub.add_parser("corpus-commit", help="copy snapshot provenance sidecars into committed benchmarks/provenance/")
    cc.add_argument("--root", default="corpus/gutenberg-r0"); cc.set_defaults(func=cmd_corpus_commit)
    mf = sub.add_parser("manifest"); mf.add_argument("--root", required=True)
    mf.add_argument("--out", required=True); mf.add_argument("--lineage-map", default=None)
    mf.add_argument("--tier", default=None, help="override corpus tier label"); mf.set_defaults(func=cmd_manifest)
    v = sub.add_parser("verify"); v.add_argument("--manifest", required=True); v.set_defaults(func=cmd_verify)
    a = sub.add_parser("audit-splits"); a.add_argument("--manifest", required=True); a.set_defaults(func=cmd_audit_splits)
    r = sub.add_parser("run"); r.add_argument("--manifest", required=True)
    r.add_argument("--out", required=True); r.add_argument("--reps", type=int, default=3)
    r.add_argument("--revision", type=int, default=0)
    r.add_argument("--systems", default="zstd19,xz9")
    r.add_argument("--split", default=None,
                   help="restrict to one split (train|validation|heldout) — smoke runs")
    r.add_argument("--max-bytes", type=int, default=0,
                   help="stop after this many input bytes — smoke runs")
    r.set_defaults(func=cmd_run)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
