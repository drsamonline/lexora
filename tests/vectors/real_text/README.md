# `gutenberg_slices.txt` — real text for codec round-trip tests

**What it is:** 720,983 bytes assembled from **88** Project Gutenberg books, 8 KiB from the middle
of each (canonicalised first, so the fixture is the same shape the packer actually sees).
SHA-256 `9a4c666970a1114e0667885c2679cdd00fb0f6c0b53f599692ca452327d7ad96`.

**Why it exists.** The `ppmd` codec shipped on 2026-11-08 and was withdrawn the same day, because
`pyppmd` corrupted **3–8 % of real documents** ([ADR-0021](../../../docs/ADR/ADR-0021-codec-policy-v2.md)).
The test that let it through used one sentence repeated 400 times — the input *least* likely to
expose a model-state bug. This fixture is the correction: many books, many vocabularies, real
punctuation, real non-ASCII, in one file small enough to commit.

**Measured variety:** 23,474 distinct words, 32,368 non-ASCII bytes, 88 different prose styles.

**What it is honest about.** A 2 MiB version of this fixture (87 books, 24 KiB each) did **not**
reproduce the pyppmd corruption — that bug needs whole documents, not slices. So this file is not
a pyppmd regression test; it is a *realistic input* test for the codecs that ship. The withdrawal
record, not this fixture, is what guards against PPMd returning.

**Provenance.** Slices taken from the middle of each book to skip the licence boilerplate. The
source books are Project Gutenberg texts (public domain in the US); they are not redistributed
here in full, only as 8 KiB excerpts, and the corpus itself is fetched by
`benchmarks/harness.py corpus-fetch` rather than committed. Regenerate with the recipe in
`tests/test_codec_real_text.py`'s module docstring if the corpus changes.
