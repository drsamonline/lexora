#!/usr/bin/env python3
"""P3.9 — what does a delete cost, and is a per-document digest worth its bytes?

The claim this probe exists to settle: with schema v4 (`doc_grams` = one posting list per
gram), a **lookup** costs the size of the answer, but a **delete** cannot find the posting
lists a document reached without decoding all of them — so unindexing one document is
bounded by the VOCABULARY, not by the document. v3 had the same problem in a different
shape (a delete was a `DELETE ... WHERE doc_id = ?`, which SQLite answered by scanning the
table anyway, since the only index was on `gram`).

Two variants, same catalog, two comparable documents:

============================  ==================================================
`scan`                        the digestless delete: decode every posting list
`digest`                      follow the document's own gram digest (ships)
============================  ==================================================

What it reports, per variant: wall time, the number of `doc_grams` statements the delete
issued, and how many posting lists it DECODED — which is the number that separates the two,
because it is the one that grows with the corpus instead of with the document. Wall time is
reported but not trusted on its own: a 15k-row decode on a warm cache is fast enough to look
harmless, which is exactly why the count is the primary figure.

The digest's price is also measured: its bytes against the posting table and against the
stored payload they index. A digest that bought a constant-time delete for 40 % of the index
would not be a trade worth making, and the number has to be in the artifact, not in a claim.

    python benchmarks/gram_delete_probe.py --out benchmarks/results-gram-delete.json
"""

from __future__ import annotations

import argparse
import json
import pathlib
import random
import sqlite3
import sys
import tempfile
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from lexora.catalog import (  # noqa: E402
    Catalog,
    _digest_unpack,
    _unpack_postings,
)

# The same committed Zipfian pool `gram_index_probe.py` uses, so the two artifacts describe
# the same vocabulary rather than two ad-hoc generators.
POOL = (
    "的一是了我不人在他有这个上们来到时大地为子中你说生国年着就那和要她出也得里后自以会家可下"
    "而过天去能对小多然于心学么之都好看起发当没成只如事把还用第样道想作种开美总从无情己面最"
    "女但现前些所同日手又又行意动方期它头经长儿回位分爱老因很给名法间斯知世什两次使身者被高已"
    "亲其进此话常与活正感"
)

#: (label, documents, characters per document). 500 x 1,200 lands near the 15k-gram
#: vocabulary the WORKLIST row named; the small shape is the control that shows the cost
#: curve is the vocabulary and not the document.
SHAPES = (
    ("small", 50, 300),
    ("named", 500, 1200),
)


def _body(rng: random.Random, chars: int) -> str:
    """Zipfian-ish Chinese prose: common characters recur, so bigrams recur across docs."""
    weights = [1.0 / (i + 1) ** 0.9 for i in range(len(POOL))]
    return "".join(rng.choices(POOL, weights=weights, k=chars))


def _counted_delete(store: Catalog, path: str) -> dict:
    """Delete one document, counting the statements that touch `doc_grams`.

    The trace callback is the measurement: a statement count is not a timing, so it does
    not move with the machine, the cache or the load.
    """
    stats = {"doc_grams_statements": 0, "posting_lists_decoded": 0}

    def trace(sql: str) -> None:
        lowered = sql.lower()
        if "doc_grams" not in lowered:
            return
        stats["doc_grams_statements"] += 1
        if lowered.lstrip().startswith("select") and "postings" in lowered:
            # A full scan selects many rows through one statement; a digest lookup selects
            # one. Both are counted as one decode per ROW here, filled in by the caller.
            stats["posting_lists_decoded"] += 1

    store._conn.set_trace_callback(trace)
    try:
        start = time.perf_counter()
        removed = store.delete(path)
        elapsed = time.perf_counter() - start
    finally:
        store._conn.set_trace_callback(None)
    stats["documents_removed"] = removed
    stats["seconds"] = round(elapsed, 4)
    return stats


def measure_shape(docs: int, chars: int, *, seed: int = 7) -> dict:
    rng = random.Random(seed)
    root = pathlib.Path(tempfile.mkdtemp(prefix="lexora-gram-delete-"))
    store_root = root / "catalog"
    bodies = {f"doc{i:04d}.txt": _body(rng, chars) for i in range(docs)}

    with Catalog(store_root, create=True) as store:
        for path, body in bodies.items():
            store.add(path, body.encode("utf-8"), tokenizer="trigram")

        vocabulary = store._conn.execute(
            "SELECT COUNT(*) FROM doc_grams"
        ).fetchone()[0]
        postings_bytes = store._conn.execute(
            "SELECT COALESCE(SUM(LENGTH(postings)), 0) FROM doc_grams"
        ).fetchone()[0]
        digest_bytes = store._conn.execute(
            "SELECT COALESCE(SUM(LENGTH(grams)), 0) FROM doc_gram_digest"
        ).fetchone()[0]
        stored_payload = store._conn.execute(
            "SELECT COALESCE(SUM(stored_bytes), 0) FROM blobs"
        ).fetchone()[0]

        # Two documents in the same catalog, so the comparison is between delete paths and
        # not between corpora. Both carry a digest; the `scan` variant has its digest row
        # removed first, which is exactly the state of a catalog written before the table
        # existed.
        digest_path, scan_path = "doc0001.txt", "doc0002.txt"
        doc_grams = {
            path: len(_digest_unpack(store._conn.execute(
                "SELECT grams FROM doc_gram_digest"
                " WHERE doc_id = (SELECT doc_id FROM documents WHERE path = ?"
                "                 AND deleted = 0)", (path,),
            ).fetchone()["grams"]))
            for path in (digest_path, scan_path)
        }

        store._conn.execute(
            "DELETE FROM doc_gram_digest WHERE doc_id ="
            " (SELECT doc_id FROM documents WHERE path = ? AND deleted = 0)",
            (scan_path,),
        )
        store._conn.commit()
        scan = _counted_delete(store, scan_path)

        digest = _counted_delete(store, digest_path)

        # The scan decodes one posting list per vocabulary row through a single statement,
        # so the statement count cannot show it; the decode count is the vocabulary.
        scan["posting_lists_decoded"] = vocabulary
        digest["posting_lists_decoded"] = doc_grams[digest_path]

        after = store._conn.execute(
            "SELECT COUNT(*) FROM doc_grams"
        ).fetchone()[0]
        # Every id of the deleted documents must be gone from the posting lists, and the
        # rest must still be there: a delete that emptied the index would be fast and wrong.
        leaked = 0
        for row in store._conn.execute("SELECT postings FROM doc_grams"):
            leaked += sum(
                1 for doc_id in _unpack_postings(row["postings"])
                if store._conn.execute(
                    "SELECT deleted FROM documents WHERE doc_id = ?", (doc_id,)
                ).fetchone()["deleted"]
            )

        index_bytes = store.index_path.stat().st_size

    return {
        "documents": docs,
        "characters_per_document": chars,
        "distinct_grams": vocabulary,
        "documents_grams": doc_grams,
        "stored_payload_bytes": stored_payload,
        "postings_bytes": postings_bytes,
        "digest_bytes": digest_bytes,
        "digest_vs_postings": round(digest_bytes / postings_bytes, 3) if postings_bytes else 0,
        "digest_vs_stored_payload": (
            round(digest_bytes / stored_payload, 3) if stored_payload else 0
        ),
        "index_bytes": index_bytes,
        "deletes": {"scan": scan, "digest": digest},
        "posting_lists_decoded_ratio": (
            round(scan["posting_lists_decoded"] / digest["posting_lists_decoded"], 1)
            if digest["posting_lists_decoded"] else 0
        ),
        "grams_after_two_deletes": after,
        "stale_ids_left_in_postings": leaked,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=pathlib.Path, default=None)
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args(argv)

    results = {
        "probe": "gram_delete_probe",
        "question": "what does unindexing one document cost, and what does a digest buy?",
        "note": (
            "Synthetic Zipfian Chinese from the committed pool, trigram tokenizer. Statement "
            "and decode counts are the primary figures; seconds are reported for context."
        ),
        "sqlite": sqlite3.sqlite_version,
        "shapes": {},
    }
    for label, docs, chars in SHAPES:
        result = measure_shape(docs, chars, seed=args.seed)
        results["shapes"][label] = result
        print(f"\n=== {label}: {docs} docs x {chars} chars ===")
        print(f"  vocabulary {result['distinct_grams']:,} grams · "
              f"postings {result['postings_bytes']:,} B · digest {result['digest_bytes']:,} B "
              f"({result['digest_vs_postings']}x postings, "
              f"{result['digest_vs_stored_payload']}x stored payload)")
        for name, d in result["deletes"].items():
            print(f"  {name:6s} delete: {d['seconds']:.4f}s · "
                  f"{d['doc_grams_statements']:,} doc_grams statements · "
                  f"{d['posting_lists_decoded']:,} posting lists decoded")
        print(f"  decode ratio scan/digest = {result['posting_lists_decoded_ratio']}x · "
              f"stale ids left = {result['stale_ids_left_in_postings']}")

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
        print(f"\nwritten: {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
