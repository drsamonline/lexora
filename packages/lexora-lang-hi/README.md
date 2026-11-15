# lexora-lang-hi — Hindi (Devanagari) for Lexora

A language plugin for [Lexora](../../README.md): the second implementation behind the
plugin seam (ADR-0022), and the one that proves the interface is an interface and not a
description of English.

```bash
pip install -e packages/lexora-lang-hi --no-deps   # from a lexora checkout
lexora doctor                                       # now lists `hi`, provenance `hi-1`
```

`--no-deps` is deliberate while both packages are unreleased: the plugin depends on
`lexora`, which is installed from the same checkout, and PyPI has no release to resolve.

## What it does

It applies the base canonicaliser (CAN-R01 encoding, CAN-R02 newlines, CAN-R05
soft-hyphen removal) and then **HI-R01: NFC**.

That matters because Devanagari nukta letters (क़ ख़ ग़ ज़ ड़ ढ़ फ़ य़, U+0958–U+095F) are
Unicode *composition exclusions*: the same word is written in the wild as the precomposed
letter or as base + U+093C COMBINING NUKTA, and NFC settles both on the decomposed form.
NFC also puts combining marks in canonical order, so a matra typed out of order still
canonicalises to one byte string. Two files of the same Hindi text become one archive, and
one search finds all of it.

It does **not** touch ZWJ (U+200D) or ZWNJ (U+200C) — those change conjunct shaping, so
removing them changes the word (REQ-CAN-005) — and it does not transliterate Devanagari
digits or spellings. Lexora stores text; it does not rewrite it.

## The property that makes plugins safe

**Plugins affect ingestion only.** An archive written with `hi-1` decodes to the same
bytes on a machine that has never installed this package: the payload is canonical bytes
and decompression never consults a plugin. The test suite proves it in a subprocess where
this module cannot be imported.

## Provenance

`hi-1` lands in the 16-byte `canonicalizer_version` header field (ADR-0023), so an
archive says which rules cleaned it without the reader needing them.

Licence: PolyForm Noncommercial 1.0.0, per the repository [`LICENSE`](../../LICENSE).
