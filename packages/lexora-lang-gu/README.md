# lexora-lang-gu — Gujarati for Lexora

A language plugin for [Lexora](../../README.md): the fourth implementation behind the plugin seam
(ADR-0022), and the half of REQ-CAN-005 that was missing — the requirement names Devanagari *and*
Gujarati, and only Devanagari had shipped.

```bash
pip install -e packages/lexora-lang-gu --no-deps   # from a lexora checkout
lexora doctor                                       # now lists `gu`, provenance `gu-1`
lexora canon --language gu --in file.txt --out canonical.txt
```

`--no-deps` is deliberate while both packages are unreleased: the plugin depends on `lexora`,
which is installed from the same checkout, and PyPI has no release to resolve.

## What it does

The base canonicaliser (CAN-R01 encoding, CAN-R02 newlines, CAN-R05 soft-hyphen removal), then
**GU-R01: NFC**.

**And its win is a different mechanism from Hindi's, which is why this file is not a copy of that
one.** Devanagari's NFC merges two spellings of a letter, because its nukta letters
(क़ ख़ ग़ …, U+0958–U+095F) are composition exclusions. **Gujarati has no precomposed nukta letters
at all** — Unicode 15.0 defines zero canonical decompositions anywhere in U+0A80–U+0AFF, and a test
in `tests/test_language_gujarati_plugin.py` asserts that rather than trusting this paragraph.

So Gujarati's NFC win is **canonical ordering**: the nukta (U+0ABC) has combining class 7 and the
virama (U+0ACD) class 9, so `ક` + virama + nukta and `ક` + nukta + virama are the same sequence in
two orders, and NFC settles both. Same consequence as Hindi — one word, one archive, one search
hit — reached differently, and worth having for that reason alone.

## What it does not do

- **No ZWJ/ZWNJ removal** — U+200C/U+200D change Gujarati conjunct shaping (REQ-CAN-005).
- **No digit transliteration** — ૦–૯ stay ૦–૯.
- **No legacy-font transcoding** — Terafont/Shree Lipi text is not Unicode text, and mapping it is
  a transcoding project with its own failure modes, not a cleaning rule.
- **No transliteration or spelling normalisation.** Lexora stores text; it does not rewrite it.

## The property that matters

Plugins affect **ingestion only**. An archive written with `gu-1` decodes to identical bytes on a
machine where this package has never been installed — asserted in a subprocess where the module is
made unimportable.

## Licence

PolyForm Noncommercial 1.0.0, like the core. See [NOTICE](../../NOTICE).
