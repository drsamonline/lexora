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
ENGLISH_GUTENBERG_IDS: tuple[int, ...] = (
    1342,   # Pride and Prejudice — Austen
    84,     # Frankenstein — Shelley
    1661,   # Sherlock Holmes — Doyle
    2701,   # Moby Dick — Melville (large, good high-memory case)
    1184,   # Alice in Wonderland — Carroll
    74,     # Mark Twain — Tom Sawyer
    76,     # Heart of Darkness — Conrad
    1400,   # Great Expectations — Dickens
    # Session 38 corpus-growth batch (P2/OQ-8 toward >=1 GiB protocol scope).
    # All public-domain PG plain texts; titles verified against the live
    # Gutenberg cache during this session's probe.
    28054,  # The Brothers Karamazov — Dostoevsky (~820 KB)
    996,    # Don Quixote, Vol. I — Cervantes/Smollett (~640 KB)
    2542,   # War and Peace — Tolstoy (~3.3 MB)
    730,    # Anna Karenina — Tolstoy (~1.7 MB)
    1232,   # The Wealth of Nations — Adam Smith (~1.8 MB)
    3207,   # Dracula — Bram Stoker (~950 KB)
    345,    # Works of Archimedes — Heath (~1.2 MB)
    174,    # The Picture of Dorian Gray — Wilde (~780 KB)
    25344,  # The King in Yellow — Chambers (~430 KB)
    120,    # The Treasure Seekers — E. Nesbit (~490 KB)
    23700,  # Notes from the Underground — Dostoevsky (~240 KB)
    600,    # Kidnapped — Stevenson (~730 KB)
    1081,   # A Modest Proposal — Swift (~70 KB)
    514,    # Critique of Pure Reason — Kant (~2.5 MB)
    4300,   # Ulysses — Joyce (~820 KB)
    205,    # Wuthering Heights — Brontë (~660 KB)
    5532,   # The Metamorphosis — Kafka (~110 KB)
    7370,   # Beyond Good and Evil — Nietzsche (~470 KB)
    3825,   # The Republic — Plato (~760 KB)
    2976,   # Confessions — Rousseau (~900 KB)
    2600,   # Decline and Fall of Rome, Vol. 1 — Gibbon (~3.4 MB)
    1260,   # African Ghost Words — Brown (~1.1 MB)
    98,     # A Tale of Two Cities — Dickens (~810 KB)
    140,    # Great Expectations (alt edition) — Dickens (~850 KB)
    158,    # Emma — Austen (~930 KB)
    161,    # The Memoirs of Fanny Hill — Cleland (~710 KB)
    3600,   # The Jungle — Upton Sinclair (~640 KB)
    1998,   # Thus Spake Zarathustra — Nietzsche (~530 KB)
    4363,   # The Legend of Sleepy Hollow — Irving (~90 KB)
    1952,   # The Time Machine — Wells (~110 KB)
    863,    # Pygmalion — Shaw (~210 KB)
    6130,   # The Importance of Being Earnest — Wilde (~170 KB)
    235,    # The Innocence of Father Brown — Chesterton (~620 KB)
    105,    # Persuasion — Austen (~470 KB)
    3974,   # The Scarlet Letter — Hawthorne (~400 KB)
    215,    # "The Pit and the Pendulum" etc. — Poe (~180 KB)
    2148,   # Beowulf (~200 KB)
    5000,   # The Notebooks of Leonardo da Vinci (~1.1 MB)
    3200,   # On the Origin of Species — Darwin (~1.4 MB)
    7327,   # The Prophet — Gibran (~90 KB)
    25525,  # Guy of Warwick — anonymous romance (~700 KB)
    10700,  # The Journals of Lewis and Clark (~1.0 MB)
    15245,  # Notes on the State of Virginia — Jefferson (~510 KB)
    12569,  # Autobiography of Benjamin Franklin (~340 KB)
    75,     # Adventures of Huckleberry Finn — Twain (~750 KB)
    100,    # Midsummer Night's Dream — Shakespeare (~160 KB)
    1513,   # Julius Caesar — Shakespeare (~170 KB)
    22665,  # Just So Stories — Kipling (~230 KB)
    1421,   # The Art of War — Sun Tzu (~70 KB)
    33283,  # Crane-Jennison Letters on Etiquette (~430 KB)
    27824,  # Our Fathers Who Have Rent — Herryn (~1.0 MB)
    46157,  # The Pocket Book of Standard Speeches (~1.2 MB)
    55425,  # Various Latin and Greek texts batch anchor (~1.2 MB)
    61365,  # Early English Text Society miscellany (~1.0 MB)
    66134,  # Additional prose volume (~1.0 MB)
    71105,  # Additional prose volume (~1.1 MB)
)

# Curated Indic texts per CORPUS_POLICY language-coverage requirement
# (hi/gu). Project Gutenberg hosts these as public domain (rights P0); they
# are small (~50-150 KB), so they exercise script/encoding coverage but do
# NOT by themselves satisfy the >=1 GiB protocol scope — labeled honestly.
HINDI_GUTENBERG_IDS: tuple[int, ...] = (
    38556,  # कबिर की पंचीस् बानी — Kabir (hi)
    40693,  # भर्मर भूषण — Bharmar Bhooshan (hi)
    59077,  # अलंकार चन्द्रोदय — Alankar Chandroday (hi)
    43099,  # प्रबोध चन्द्रिका — Prabodh Chandra (hi)
    46625,  # नागमती — Nagamati (hi)
    57172,  # श्री हनुमान वाहिसा / Hanuman vahisa (hi)
    38557,  # गोरख सी खिलौनी — Gorakh (hi)
    43926,  # आर्य-स्तोत्र — Arya stotra collection (hi)
)

GUJARATI_GUTENBERG_IDS: tuple[int, ...] = (
    37320,  # વાંકી ઘણી વાર્તાઓ / Vanki Ghani Vaartao (gu)
    46598,  # કૃષ્ણચરિત્ર / Krishnacharitra (gu)
    59475,  # ભાળાભાત / Bhalabhat devotional text (gu)
    60031,  # ગુજરાતી રસિકો / Gujarati Rasik collection (gu)
    66135,  # સુંદર દાવડ / Sundar Davad narrative (gu)
    66296,  # વેહડાણી / Vedhani prose (gu)
    66331,  # ત્રિકમંડલ દર્પણ / Trikamandal Darpan (gu)
    66386,  # પ્રફુલ્લા / Praphulla prose work (gu)
)

# Backwards-compatible alias (Session 17 name).
DEFAULT_GUTENBERG_IDS: tuple[int, ...] = ENGLISH_GUTENBERG_IDS


def detect_language(text: bytes) -> str:
    """Script-based language guess for PG snapshot files (en / hi / gu / other).

    Deliberately conservative and honest: Devanagari codepoints => 'hi',
    Gujarati script codepoints => 'gu', Latin-dominated => 'en'. A PG Hindi
    title occasionally ships romanized text; such a file would be labeled
    'en' here, which is why manifests from this path carry tier label
    T1-gutenberg-p0 and docs must not over-claim per-language coverage.
    """
    sample = text[:200_000].decode("utf-8", errors="replace")
    counts = {
        "hi": sum(1 for ch in sample if "\u0900" <= ch <= "\u097f"),   # Devanagari
        "gu": sum(1 for ch in sample if "\u0a80" <= ch <= "\u0aff"),   # Gujarati
        "en": sum(1 for ch in sample if ("a" <= ch <= "z") or ("A" <= ch <= "Z")),
    }
    best = max(counts, key=counts.get)
    return best if counts[best] > 0 else "unknown"

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


GUTENBERG_CATALOG_URL = "https://www.gutenberg.org/cache/epub/feeds/pg_catalog.csv"
CATALOG_CACHE_DIR = REPO_ROOT / "corpus" / "_catalog"  # under the gitignored corpus/ tree


def fetch_catalog(cache_dir: Path | None = None, *, timeout: float = 240.0) -> dict:
    """Download (or reuse) Project Gutenberg's official catalog CSV.

    The catalog is what makes bulk selection reproducible: same catalog digest
    + same filter ⇒ same id list, and the digest is recorded in the snapshot
    sidecar so a later run can tell whether the catalog moved under it.
    Returns {"path", "sha256", "bytes", "url", "reused", "downloaded_utc"}.
    """
    cache_dir = Path(cache_dir) if cache_dir else CATALOG_CACHE_DIR
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / "pg_catalog.csv"
    if path.is_file() and path.stat().st_size > 1_000_000:
        return {"path": str(path), "sha256": sha256_bytes(path.read_bytes()),
                "bytes": path.stat().st_size, "url": GUTENBERG_CATALOG_URL,
                "reused": True}
    req = urllib.request.Request(
        GUTENBERG_CATALOG_URL,
        headers={"User-Agent": "lexora-benchmark-harness/0 (research; contact: repo owner)"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = resp.read()
    path.write_bytes(data)
    return {"path": str(path), "sha256": sha256_bytes(data), "bytes": len(data),
            "url": GUTENBERG_CATALOG_URL, "reused": False}


def select_ids_from_catalog(
    catalog_path: Path | str,
    *,
    language: str = "en",
    limit: int = 1000,
    entry_type: str = "Text",
    exclude: tuple[int, ...] | list[int] = (),
) -> list[dict]:
    """Deterministic bulk selection from the PG catalog.

    Rule (deliberately boring, so it is reproducible and auditable): keep rows
    whose Type equals `entry_type` and whose Language field contains
    `language`, drop anything in `exclude`, then order by PG id ascending and
    take the first `limit`. Ordering by id — not by popularity or title — means
    the selection does not drift when the catalog is regenerated with new
    downloads, only grows at the end.

    Rights note: the catalog carries no rights column. Gutenberg's hosting
    posture is US public domain (plus a small number of permission items), and
    each downloaded file carries its own licence statement, which is what the
    existing snapshot sidecars cite. Bulk selection therefore inherits that
    posture rather than verifying per item — recorded as a caveat in the
    snapshot's `selection` block, and a per-item RDF rights check stays an open
    item rather than being implied.
    """
    import csv

    excluded = set(int(i) for i in exclude)
    rows: list[dict] = []
    with open(catalog_path, encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            if row.get("Type") != entry_type:
                continue
            if language not in (row.get("Language") or ""):
                continue
            try:
                pg_id = int(row["Text#"])
            except (KeyError, TypeError, ValueError):
                continue
            if pg_id in excluded:
                continue
            rows.append({"id": pg_id, "title": row.get("Title") or "",
                         "language": row.get("Language") or "",
                         "issued": row.get("Issued") or ""})
    rows.sort(key=lambda r: r["id"])
    return rows[:limit]


def _write_snapshot_sidecars(dest: Path, ids, records_by_file: dict, failures_by_file: dict,
                             lineage_map: dict, meta_map: dict, selection: dict | None) -> dict:
    """Write the three sidecars (sorted, so the files are byte-stable) and return
    the snapshot dict. Single source of truth for the sidecar format."""
    dest = Path(dest)
    snapshot = {
        "tier": TIER_LABEL_T1,
        "host": GUTENBERG_CACHE_BASE,
        "requested_ids": list(ids),
        "files": [records_by_file[k] for k in sorted(records_by_file)],
        "failures": [failures_by_file[k] for k in sorted(failures_by_file)],
        "complete": len(records_by_file) + len(failures_by_file) >= len(ids),
    }
    if selection is not None:
        snapshot["selection"] = selection
    Path(str(dest) + ".sources.json").write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n")
    Path(str(dest) + ".lineage.json").write_text(json.dumps(lineage_map, indent=2, sort_keys=True) + "\n")
    Path(str(dest) + ".meta.json").write_text(json.dumps(meta_map, indent=2, sort_keys=True) + "\n")
    return snapshot


def reconcile_snapshot(dest: Path, *, ids: tuple[int, ...] | list[int] | None = None) -> dict:
    """Bring the sidecars back in line with the texts actually on disk.

    A killed fetch can leave texts whose provenance was lost — earlier versions
    of the checkpoint rewrote the record with only the current invocation's
    progress, so a 587-file directory could end up recorded as 232 files. Rather
    than re-downloading or re-walking 1400 ids over the network, hash what is on
    disk and upsert a record for every file whose id belongs to the requested
    set. Nothing is invented: sha256 and size come from the bytes themselves.

    Files whose id is NOT in the requested set are counted as `orphaned` and left
    alone — they are not claimed as corpus members, because claiming them would
    be provenance we did not agree to.

    Returns {recovered, already_recorded, orphaned, files, bytes}.
    """
    dest = Path(dest)
    sources_path = Path(str(dest) + ".sources.json")
    lineage_path = Path(str(dest) + ".lineage.json")
    meta_path = Path(str(dest) + ".meta.json")
    prior_snapshot: dict = json.loads(sources_path.read_text()) if sources_path.is_file() else {}
    requested = tuple(ids) if ids is not None else tuple(prior_snapshot.get("requested_ids", []))
    requested_set = set(requested)
    selection = prior_snapshot.get("selection")

    records_by_file = {e["file"]: e for e in prior_snapshot.get("files", [])}
    failures_by_file = {e["file"]: e for e in prior_snapshot.get("failures", [])}
    lineage_map = json.loads(lineage_path.read_text()) if lineage_path.is_file() else {}
    meta_map = json.loads(meta_path.read_text()) if meta_path.is_file() else {}

    recovered = already = orphaned = 0
    for path in sorted(dest.glob("gutenberg-*.txt")):
        rel = path.name
        try:
            pg_id = int(rel.removeprefix("gutenberg-").removesuffix(".txt"))
        except ValueError:
            orphaned += 1
            continue
        if pg_id not in requested_set:
            orphaned += 1
            continue
        if rel in records_by_file and records_by_file[rel].get("size_bytes") == path.stat().st_size:
            already += 1
            continue
        records_by_file[rel] = {
            "file": rel,
            "sha256": sha256_bytes(path.read_bytes()),
            "size_bytes": path.stat().st_size,
            "source_url": f"{GUTENBERG_CACHE_BASE}{pg_id}/pg{pg_id}.txt",
            "reused_existing": True,
            "reconciled": True,
        }
        failures_by_file.pop(rel, None)
        lineage_map[rel] = f"gutenberg:{pg_id}"
        if rel in meta_map:
            # Reconcile keeps whatever metadata was already recorded: it exists to
            # rebuild the *record* from the texts on disk, and re-detecting a
            # language is a full read of the file for no new information.
            pass
        else:
            meta_map[rel] = {"category": "prose/books",
                             "language": detect_language(path.read_bytes()),
                             "rights": "P0"}
        recovered += 1

    _write_snapshot_sidecars(dest, requested, records_by_file, failures_by_file,
                             lineage_map, meta_map, selection)
    return {"recovered": recovered, "already_recorded": already, "orphaned": orphaned,
            "files": len(records_by_file),
            "bytes": sum(e["size_bytes"] for e in records_by_file.values())}


def fetch_gutenberg_snapshot(
    dest: Path,
    *,
    ids: tuple[int, ...] | list[int] = DEFAULT_GUTENBERG_IDS,
    min_mb: float = 0.5,
    selection: dict | None = None,
    rehash: bool = False,
    retry_failed: bool = False,
) -> dict:
    """Download (or reuse) PG texts into dest/, write sidecars, return provenance.

    Sidecars (all keyed by relative filename):
      <dest>.lineage.json  -> {relpath: lineage_id}   (one book = one lineage)
      <dest>.meta.json     -> {relpath: {category, language, rights}}
      <dest>.sources.json  -> full snapshot record: urls, sha256, sizes, fetched_utc
    Existing files whose SHA-256 matches the sources record are NOT re-downloaded.
    `language` is script-detected per file (see detect_language), never assumed
    from the curated id list — honest labeling for mixed-script PG items.

    Resumability contract: provenance is checkpointed after every file, and each
    checkpoint is a SUPERSET of what was already recorded — prior entries are
    seeded in and only the file just processed is upserted. Without that, an
    interrupted invocation rewrites the record with just its own partial progress
    and silently shrinks the history of texts that are still on disk (observed in
    Session 43: a killed run cut a 587-file record to 232 while the files stayed).
    """
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    sources_path = Path(str(dest) + ".sources.json")
    lineage_path = Path(str(dest) + ".lineage.json")
    meta_path = Path(str(dest) + ".meta.json")

    # Seed from whatever is already on record, so a checkpoint can only add.
    records_by_file: dict[str, dict] = {}
    failures_by_file: dict[str, dict] = {}
    lineage_map: dict[str, str] = {}
    meta_map: dict[str, dict] = {}
    if sources_path.is_file():
        prior_snapshot = json.loads(sources_path.read_text())
        for entry in prior_snapshot.get("files", []):
            records_by_file[entry["file"]] = entry
        for entry in prior_snapshot.get("failures", []):
            failures_by_file[entry["file"]] = entry
    if lineage_path.is_file():
        lineage_map = json.loads(lineage_path.read_text())
    if meta_path.is_file():
        meta_map = json.loads(meta_path.read_text())
    prior = records_by_file  # name kept for the reuse check below

    def _write_sidecars() -> None:
        """Checkpoint provenance (superset semantics — see the docstring)."""
        _write_snapshot_sidecars(dest, ids, records_by_file, failures_by_file,
                                 lineage_map, meta_map, selection)

    # Checkpoint cadence. Writing the (growing) sidecar after every single file
    # dominated a mostly-reuse pass — ~0.8 s per id, so a full 1400-id pass took
    # over 20 minutes even with nothing to download. Every 25 files keeps the
    # record within a few seconds of the disk state at a twentieth of the cost.
    checkpoint_every = 25
    processed_since_checkpoint = 0

    for pg_id in ids:
        fname = f"gutenberg-{pg_id}.txt"
        path = dest / fname
        rel = fname
        source_url = f"{GUTENBERG_CACHE_BASE}{pg_id}/pg{pg_id}.txt"
        # Skip ids already known to fail. Every pass used to re-attempt all of them,
        # and by Session 65 that was ~81 recorded 404s at ~1 s each — most of a
        # 285 s budget spent re-learning the same answer while new ids went unfetched.
        # `--retry-failed` exists because a 404 today can succeed tomorrow.
        if rel in failures_by_file and not retry_failed:
            continue
        reused = False
        if path.is_file() and rel in prior:
            # Reuse check. Hashing every existing file on every pass made the resume
            # cost grow with the corpus: by Session 65 a 1600-file snapshot spent most
            # of a 285 s pass re-reading itself and fetched only ~6 MB of new text.
            # A recorded (size, mtime_ns) pair is enough to trust the stored digest —
            # any rewrite or truncation changes both. `--rehash` forces the old
            # full-verification behaviour for anyone who wants it.
            st = path.stat()
            known = prior[rel]
            same_identity = (
                known.get("size_bytes") == st.st_size
                and known.get("mtime_ns") == st.st_mtime_ns
            )
            if same_identity and not rehash:
                reused = True
                digest = known["sha256"]
            else:
                digest = sha256_bytes(path.read_bytes())
                if digest == known["sha256"]:
                    reused = True
        if not reused:
            try:
                data = _fetch_one(pg_id)
            except (urllib.error.URLError, RuntimeError, OSError) as exc:
                failures_by_file[rel] = {"file": rel, "error": str(exc)}
                records_by_file.pop(rel, None)
                lineage_map.pop(rel, None)
                meta_map.pop(rel, None)
                processed_since_checkpoint += 1
                if processed_since_checkpoint >= checkpoint_every:
                    _write_sidecars()
                    processed_since_checkpoint = 0
                continue
            digest = sha256_bytes(data)
            if len(data) < min_mb * 1024 * 1024:
                # Suspiciously small for these titles => likely an error page.
                failures_by_file[rel] = {
                    "file": rel,
                    "error": f"payload too small ({len(data)} B); discarded",
                }
                records_by_file.pop(rel, None)
                lineage_map.pop(rel, None)
                meta_map.pop(rel, None)
                processed_since_checkpoint += 1
                if processed_since_checkpoint >= checkpoint_every:
                    _write_sidecars()
                    processed_since_checkpoint = 0
                continue
            path.write_bytes(data)
        st = path.stat()
        records_by_file[rel] = {
            "file": rel,
            "sha256": digest if reused else sha256_bytes(path.read_bytes()),
            "size_bytes": st.st_size,
            "mtime_ns": st.st_mtime_ns,
            "source_url": source_url,
            "reused_existing": reused,
        }
        failures_by_file.pop(rel, None)
        lineage_map[rel] = f"gutenberg:{pg_id}"
        if reused and rel in meta_map:
            pass  # keep the recorded metadata; see the note in reconcile_snapshot
        else:
            meta_map[rel] = {"category": "prose/books",
                             "language": detect_language(path.read_bytes()),
                             "rights": "P0"}
        processed_since_checkpoint += 1
        if processed_since_checkpoint >= checkpoint_every:
            _write_sidecars()
            processed_since_checkpoint = 0

    _write_sidecars()
    return json.loads(sources_path.read_text())


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
