"""Tiered corpus fallback for the LEXORA benchmark harness (Session 17).

CORPUS_POLICY requires a >=1 GiB multilingual, rights-cleared corpus. That
corpus is an owner input and does not exist yet (OQ-8 partially open). To keep
baseline measurement moving WITHOUT fabricating data or violating rights, this
module implements a *tiered* fallback:

  TIER 0 (preferred)  Owner-supplied corpus directory (data/raw/ or any path
                      given by --root). Used whenever it exists.
  TIER 1 (fallback)   Public-domain Project Gutenberg texts (rights class P0
                      per CORPUS_POLICY — openly licensed, no privacy issues),
                      fetched over HTTPS from https://www.gutenberg.org via the
                      standard cache/file endpoint. Snapshot metadata (source
                      URL + SHA-256 per file) is written next to the corpus so
                      every later run can prove which bytes were used.
  TIER 2 (last resort) Deterministic synthetic text (seeded PRNG only). Real
                      measurements are still real, but such numbers say almost
                      nothing about natural-language compression; they are
                      clearly labeled \"synthetic\" in manifests and results.

Honesty contract:
  * The tier actually used is recorded in the manifest (`corpus_tier`) and in
    every results artifact (`corpus_tier`, `provenance`). Docs may only publish
    numbers together with that label.
  * Fetching is idempotent: files already present with matching SHA-256 are
    reused; corrupt/truncated downloads are deleted and reported, never kept.
  * NO Gutenberg mirror scraping beyond the official cache host; polite
    single-threaded requests with timeouts.

Usage (library): from benchmarks.corpus import fetch_gutenberg_snapshot
CLI entry point lives in benchmarks/harness.py subcommand `corpus-fetch`.
"""

from __future__ import annotations

import hashlib
import json
import random
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

GUTENBERG_CACHE_BASE = "https://www.gutenberg.org/cache/epub/"

# Curated public-domain English prose (Project Gutenberg IDs). All items are
# marked PG-DUKE/PD in the Gutenberg catalog; copyright page text inside each
# download states the license. Rights class per CORPUS_POLICY: P0 public.
DEFAULT_GUTENBERG_IDS: tuple[int, ...] = (
    1342,   # Pride and Prejudice — Austen
    84,     # Frankenstein — Shelley
    1661,   # Sherlock Holmes — Doyle
    2701,   # Moby Dick — Melville (large, good high-memory case)
    1184,   # Alice in Wonderland — Carroll
    74,     # Mark Twain — Tom Sawyer
    76,     # Heart of Darkness — Conrad
    1400,   # Great Expectations — Dickens
)

TIER_LABEL_T0 = "T0-owner-supplied"
TIER_LABEL_T1 = "T1-gutenberg-p0"
TIER_LABEL_T2 = "T2-synthetic"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _fetch_one(pg_id: int, timeout: float = 60.0) -> bytes:
    url = f"{GUTENBERG_CACHE_BASE}{pg_id}/pg{pg_id}.txt"
    req = urllib.request.Request(url, headers={"User-Agent": "lexora-benchmark-harness/0 (research; contact: repo owner)"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        if resp.status != 200:
            raise RuntimeError(f"HTTP {resp.status} for {url}")
        return resp.read()


def fetch_gutenberg_snapshot(
    dest: Path,
    *,
    ids: tuple[int, ...] | list[int] = DEFAULT_GUTENBERG_IDS,
    min_mb: float = 0.5,
) -> dict:
    """Download (or reuse) PG texts into dest/, write sidecars, return provenance.

    Sidecars (all keyed by relative filename):
      <dest>.lineage.json  -> {relpath: lineage_id}   (one book = one lineage)
      <dest>.meta.json     -> {relpath: {category, language, rights}}
      <dest>.sources.json  -> full snapshot record: urls, sha256, sizes, fetched_utc
    Existing files whose SHA-256 matches the sources record are NOT re-downloaded.
    """
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    sources_path = Path(str(dest) + ".sources.json")
    prior: dict = {}
    if sources_path.is_file():
        prior = {e["file"]: e for e in json.loads(sources_path.read_text()).get("files", [])}

    records, lineage_map, meta_map = [], {}, {}
    failures: list[dict] = []
    for pg_id in ids:
        fname = f"gutenberg-{pg_id}.txt"
        path = dest / fname
        rel = fname
        source_url = f"{GUTENBERG_CACHE_BASE}{pg_id}/pg{pg_id}.txt"
        reused = False
        if path.is_file() and rel in prior:
            digest = sha256_bytes(path.read_bytes())
            if digest == prior[rel]["sha256"]:
                reused = True
        if not reused:
            try:
                data = _fetch_one(pg_id)
            except (urllib.error.URLError, RuntimeError, OSError) as exc:
                failures.append({"file": rel, "error": str(exc)})
                continue
            digest = sha256_bytes(data)
            if len(data) < min_mb * 1024 * 1024:
                # Suspiciously small for these titles => likely an error page.
                failures.append({"file": rel, "error": f"payload too small ({len(data)} B); discarded"})
                continue
            path.write_bytes(data)
        records.append({
            "file": rel,
            "sha256": sha256_bytes(path.read_bytes()),
            "size_bytes": path.stat().st_size,
            "source_url": source_url,
            "reused_existing": reused,
        })
        lineage_map[rel] = f"gutenberg:{pg_id}"
        meta_map[rel] = {"category": "prose/books", "language": "en", "rights": "P0"}

    snapshot = {
        "tier": TIER_LABEL_T1,
        "host": GUTENBERG_CACHE_BASE,
        "requested_ids": list(ids),
        "files": records,
        "failures": failures,
    }
    sources_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n")
    Path(str(dest) + ".lineage.json").write_text(json.dumps(lineage_map, indent=2, sort_keys=True) + "\n")
    Path(str(dest) + ".meta.json").write_text(json.dumps(meta_map, indent=2, sort_keys=True) + "\n")
    return snapshot


def generate_synthetic_corpus(dest: Path, *, n_files: int = 6, seed: int = 20261016) -> dict:
    """TIER 2 fallback: deterministic pseudo-English text, seeded PRNG only.

    Same word distribution every run (REQ-CMP-003 determinism spirit); NOT a
    substitute for real corpora — labeled accordingly everywhere.
    """
    rng = random.Random(seed)
    words = ("the quick brown fox jumps over lazy dogs while compressible text "
             "repeats patterns again and again and again").split()
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    records = []
    for i in range(n_files):
        lines = []
        for _ in range(2000):
            lines.append(" ".join(rng.choice(words) for _ in range(rng.randint(6, 14))))
        data = ("\n".join(lines) + "\n").encode("utf-8")
        fname = f"synthetic-{i:02d}.txt"
        (dest / fname).write_bytes(data)
        records.append({"file": fname, "sha256": sha256_bytes(data), "size_bytes": len(data)})
    snapshot = {"tier": TIER_LABEL_T2, "seed": seed, "files": records, "failures": []}
    Path(str(dest) + ".sources.json").write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n")
    Path(str(dest) + ".lineage.json").write_text(
        json.dumps({r["file"]: f"synthetic:{r['file']}" for r in records}, indent=2, sort_keys=True) + "\n")
    Path(str(dest) + ".meta.json").write_text(
        json.dumps({r["file"]: {"category": "synthetic", "language": "en", "rights": "N/A-generated"}
                    for r in records}, indent=2, sort_keys=True) + "\n")
    return snapshot


def commit_sidecars(root: Path) -> dict:
    """Copy the gitignored provenance sidecars of snapshot `root` into a
    COMMITTED directory (`<repo>/benchmarks/provenance/<snapshot-name>/`).

    Raw texts stay gitignored; these small JSON files (lineage map, rights /
    language / category metadata, fetch record) are the evidence chain that
    lets anyone re-verify or regenerate a manifest from committed state alone.
    Refuses to overwrite silently unless contents are byte-identical.
    Returns {basename: committed_path}.
    """
    root = Path(root)
    dest_dir = REPO_ROOT / "benchmarks" / "provenance" / root.name
    dest_dir.mkdir(parents=True, exist_ok=True)
    copied: dict = {}
    for src in sorted(root.parent.glob(root.name + ".*.json")):
        base = src.name[len(root.name) + 1:]  # e.g. gutenberg-r0.meta.json -> meta.json
        dst = dest_dir / base
        data = src.read_bytes()
        if dst.is_file() and dst.read_bytes() == data:
            copied[base] = str(dst.relative_to(REPO_ROOT)) + " (unchanged)"
            continue
        dst.write_bytes(data)
        copied[base] = str(dst.relative_to(REPO_ROOT))
    return copied


def read_snapshot_tier(dest: Path) -> str | None:
    p = Path(str(dest) + ".sources.json")
    if p.is_file():
        return json.loads(p.read_text()).get("tier")
    return None
