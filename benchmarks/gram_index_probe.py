#!/usr/bin/env python3
"""P3.8 — where does the `doc_grams` table's cost actually go, and what would packing buy?

The claim this probe exists to settle: the short-query gram index costs **~5x the stored
payload**, which was measured once, on an ad-hoc generator that was never committed. A number in
a CHANGELOG with no artifact behind it is exactly what this project's own rule forbids, so the
first job here is to make the claim reproducible; the second is to find out whether packing it is
worth a schema change at all.

It measures five layouts over identical data, in one SQLite file, and reports bytes from
`dbstat` rather than from arithmetic:

======================  ==========================================================================
`a_current`             `(gram TEXT, doc_id)` WITHOUT ROWID — what ships today
`b_hash32`              `(crc32(gram), doc_id)` — the obvious packing
`c_hash4`               the same hash stored as a 4-byte BLOB (integer-sorted, compact)
`d_posting32`           `crc32(gram) -> packed doc ids` — an inverted index, one row per gram
`e_posting_text`        `gram TEXT -> packed doc ids` — inverted, exact, no hashing
`f_posting_varint`      the same, with the SHIPPED delta-coded encoder (`_pack_postings`)
======================  ==========================================================================

Two numbers decide the question and neither is size alone:

* **collisions** — how many distinct grams collapse under a 32-bit hash. That is the exactness
  price of packing: a colliding query must be verified against the document, or it will return
  documents that do not contain the needle.
* **bytes per stored payload** — the gram table against the zstd-compressed text it indexes,
  which is the ratio the CHANGELOG quotes.

Shapes are synthetic and labelled as such. They are chosen to separate two effects that the
single-document measurement could not: a corpus where the same bigrams recur across documents
favours an inverted index, and one document cannot.

    python benchmarks/gram_index_probe.py --out benchmarks/results-gram-index.json
"""

from __future__ import annotations

import argparse
import json
import pathlib
import random
import sqlite3
import struct
import sys
import tempfile
import zlib

# A Zipfian Chinese vocabulary, drawn from characters that actually recur in prose. The pool is
# committed with the probe so the measurement can be reproduced; the previous figure in the
# CHANGELOG came from a generator nobody kept, and could not be.
POOL = (
    "的一是了我不人在他有这个上们来到时大地为子中你说生国年着就那和要她出也得里后自以会家可下"
    "而过天去能对小多然于心学么之都好看起发当没成只如事把还用第样道想作种开美总从无情己面最"
    "女但现前些所同日手又行意动方期它头经长儿回位分爱老因很给名法间斯知世什两次使身者被高已"
    "亲其进此话常与活正感"
)

SHAPES = (
    # (label, documents, characters per document)
    ("one-document-20k", 1, 20_000),
    ("small-corpus-50x4k", 50, 4_000),
    ("recurring-bigrams-500x400", 500, 400),
)

VARIANTS = ("a_current", "b_hash32", "c_hash4", "d_posting32", "e_posting_text",
            "f_posting_varint")


def zipf_text(chars: int, seed: int) -> str:
    rng = random.Random(seed)
    weights = [1.0 / (i + 1) for i in range(len(POOL))]
    return "".join(rng.choices(POOL, weights=weights, k=chars))


def grams_of(text: str) -> set[str]:
    """The catalog's own definition: every unigram and bigram of the case-folded text."""
    folded = text.casefold()
    grams = set(folded)
    grams.update(folded[i:i + 2] for i in range(len(folded) - 1))
    return grams


def _pack(docs: set[int]) -> bytes:
    return b"".join(struct.pack("<I", d) for d in sorted(docs))


def _table_bytes(conn: sqlite3.Connection, table: str) -> int:
    """Real page usage, not a formula. dbstat is compiled into CPython's sqlite3 on Debian."""
    row = conn.execute("SELECT SUM(pgsize) FROM dbstat WHERE name=?", (table,)).fetchone()
    return int(row[0] or 0)


def measure_shape(docs: int, chars: int, seed: int = 7) -> dict:
    from lexora.zstd_core import compress  # the payload these grams index
    from lexora.catalog import _pack_postings  # the encoder schema v4 actually ships

    per_doc = {d: grams_of(zipf_text(chars, seed=seed + d)) for d in range(docs)}
    canonical = "".join(zipf_text(chars, seed=seed + d) for d in range(docs)).encode("utf-8")
    stored_bytes = len(compress(canonical, level=9))

    pairs = [(g, d) for d, grams in per_doc.items() for g in grams]

    with tempfile.TemporaryDirectory() as tmp:
        conn = sqlite3.connect(pathlib.Path(tmp) / "variants.db")
        conn.execute("CREATE TABLE a_current (gram TEXT NOT NULL, doc_id INTEGER NOT NULL,"
                     " PRIMARY KEY(gram, doc_id)) WITHOUT ROWID")
        conn.execute("CREATE TABLE b_hash32 (h INTEGER NOT NULL, doc_id INTEGER NOT NULL,"
                     " PRIMARY KEY(h, doc_id)) WITHOUT ROWID")
        conn.execute("CREATE TABLE c_hash4 (h BLOB NOT NULL, doc_id INTEGER NOT NULL,"
                     " PRIMARY KEY(h, doc_id)) WITHOUT ROWID")
        conn.execute("CREATE TABLE d_posting32 (h INTEGER PRIMARY KEY, docs BLOB NOT NULL)"
                     " WITHOUT ROWID")
        conn.execute("CREATE TABLE e_posting_text (gram TEXT PRIMARY KEY, docs BLOB NOT NULL)"
                     " WITHOUT ROWID")
        conn.execute("CREATE TABLE f_posting_varint (gram TEXT PRIMARY KEY, postings BLOB NOT NULL)"
                     " WITHOUT ROWID")

        conn.executemany("INSERT INTO a_current VALUES (?,?)", pairs)
        conn.executemany("INSERT INTO b_hash32 VALUES (?,?)",
                         [(zlib.crc32(g.encode()), d) for g, d in pairs])
        conn.executemany("INSERT INTO c_hash4 VALUES (?,?)",
                         [(zlib.crc32(g.encode()).to_bytes(4, "little"), d) for g, d in pairs])

        postings: dict[int, set[int]] = {}
        postings_text: dict[str, set[int]] = {}
        for gram, doc in pairs:
            postings.setdefault(zlib.crc32(gram.encode()), set()).add(doc)
            postings_text.setdefault(gram, set()).add(doc)
        conn.executemany("INSERT INTO d_posting32 VALUES (?,?)",
                         [(h, _pack(v)) for h, v in postings.items()])
        conn.executemany("INSERT INTO e_posting_text VALUES (?,?)",
                         [(g, _pack(v)) for g, v in postings_text.items()])
        conn.executemany("INSERT INTO f_posting_varint VALUES (?,?)",
                         [(g, _pack_postings(v)) for g, v in postings_text.items()])
        conn.commit()

        sizes = {}
        for name in VARIANTS:
            rows = conn.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
            size = _table_bytes(conn, name)
            sizes[name] = {"rows": rows, "bytes": size,
                           "bytes_per_row": round(size / rows, 2) if rows else 0}
        conn.close()

    sizes["f_posting_varint"]["bytes_per_pair"] = round(
        sizes["f_posting_varint"]["bytes"] / len(pairs), 3
    )
    distinct_grams = len({g for g, _ in pairs})
    distinct_hashes = len({zlib.crc32(g.encode()) for g, _ in pairs})
    base = sizes["a_current"]["bytes"] or 1
    for name, data in sizes.items():
        data["vs_current"] = round(base / data["bytes"], 2) if data["bytes"] else None

    return {
        "documents": docs,
        "chars_per_document": chars,
        "canonical_bytes": len(canonical),
        "stored_payload_bytes_zstd9": stored_bytes,
        "gram_doc_pairs": len(pairs),
        "distinct_grams": distinct_grams,
        "distinct_crc32": distinct_hashes,
        "hash_collisions": distinct_grams - distinct_hashes,
        "layouts": sizes,
        "current_vs_stored_payload": round(sizes["a_current"]["bytes"] / stored_bytes, 2),
        "best_packing_vs_stored_payload": round(
            min(v["bytes"] for v in sizes.values()) / stored_bytes, 2
        ),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=pathlib.Path, default=None)
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args(argv)

    results = {
        "probe": "gram_index_probe",
        "question": "what would packing doc_grams buy, and what would it cost in exactness?",
        "note": (
            "Synthetic Zipfian Chinese, shapes chosen to separate row-count cost from "
            "gram-width cost. Not a measurement of the corpus."
        ),
        "shapes": {},
    }
    for label, docs, chars in SHAPES:
        result = measure_shape(docs, chars, seed=args.seed)
        results["shapes"][label] = result
        print(f"\n=== {label}: {docs} docs x {chars} chars ===")
        print(f"  stored payload (zstd-9): {result['stored_payload_bytes_zstd9']:,} B · "
              f"{result['gram_doc_pairs']:,} pairs · {result['distinct_grams']:,} distinct grams")
        for name in VARIANTS:
            d = result["layouts"][name]
            print(f"  {name:15s} rows={d['rows']:8,}  bytes={d['bytes']:10,}  "
                  f"{d['bytes_per_row']:6.2f} B/row  {d['vs_current']}x")
        print(f"  current layout = {result['current_vs_stored_payload']}x the stored payload; "
              f"best packing = {result['best_packing_vs_stored_payload']}x; "
              f"32-bit collisions = {result['hash_collisions']}")

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
        print(f"\nwritten: {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
