# lexora-lang-zh — Chinese for Lexora

A language plugin for [Lexora](../../README.md): the third implementation behind the
plugin seam (ADR-0022), and the first one that declares a **different search
tokenizer** — which is the capability the seam was written for.

```bash
pip install -e packages/lexora-lang-zh --no-deps   # from a lexora checkout
lexora doctor                                       # now lists `zh`, provenance `zh-1`, trigram
```

`--no-deps` is deliberate while both packages are unreleased: the plugin depends on
`lexora`, which is installed from the same checkout, and PyPI has no release to resolve.

## What it does

It applies the base canonicaliser (CAN-R01 encoding, CAN-R02 newlines, CAN-R05
soft-hyphen removal) and NFC, then **ZH-R01: full-width ASCII letters and digits fold
to ASCII, and U+3000 IDEOGRAPHIC SPACE folds to U+0020**.

A Chinese IME emits `ＡＢＣ` (U+FF21 U+FF22 U+FF23) or `ABC` for the same three letters
depending on the mode it was in, and `２０２４` for the year 2024. NFC does not touch
either — they are compatibility characters, not canonical variants — so without ZH-R01
the same sentence typed on two machines is two archives, and one search finds half of
it. This is the same class of defect HI-R01 fixes for Devanagari nukta letters.

It does **not** fold full-width punctuation (`，` `。` `：` are Chinese typography, not
wide spellings of `,` `.` `:`), does not convert traditional to simplified, and does not
carry a compatibility-ideograph rule: NFC already folds all 1002 CJK Compatibility
Ideographs, which was checked rather than assumed, and a test asserts it so nobody adds
the rule back.

## The tokenizer, and its floor

Chinese has no spaces, so `unicode61` indexes a whole sentence as one token. The plugin
declares `trigram`, and the catalog now records that per document and indexes CJK text in
its own FTS5 table at `detail=full` — because under the space-separated index's
`detail=column`, every query longer than three characters is a phrase query and FTS5
refuses those outright. See
[ADR-0024](../../docs/ADR/ADR-0024-tokenizer-recording.md).

**A query shorter than three characters cannot match under trigram at all.** `公园`
(two characters) has no trigram to match. That is a floor of the tokenizer, not a defect
in this plugin. The *catalog* answers such a query anyway: `Catalog.search` falls back to
a literal, case-folded scan of the live CJK documents (bounded to 1000 documents, and it
sets `last_search_truncated` when the bound bites, which `lexora db search` prints as a
note on stderr). See [ADR-0024](../../docs/ADR/ADR-0024-tokenizer-recording.md). The
remaining open work is bigram pre-segmentation — the option that would answer short
queries from an index rather than by scanning.
