"""Chinese — the third language plugin, and the first one that needs a different index.

Why this package exists
-----------------------
`hi` proved the seam is an interface and not a description of English. It did not
prove the seam's *other* declared capability. ADR-0022 lists four things a language
plugin may declare, and says which one matters most:

    a **search tokenizer** — which FTS5 tokenizer the index should use (this is the
    one that matters most for Chinese/Japanese, which have no spaces to split on)

Two Indic scripts both declare `unicode61` and both get away with it, because
Devanagari and Latin are written with spaces. A third language that declares a
*different* tokenizer is what turns that sentence from a comment into a claim. This
is that language.

What it adds over the base rules
--------------------------------
The base canonicaliser (CAN-R01 encoding, CAN-R02 newlines, CAN-R05 soft-hyphen
removal) and NFC, then one rule:

  ZH-R01 — full-width ASCII letters and digits fold to ASCII, and U+3000
           IDEOGRAPHIC SPACE folds to U+0020.

That is the same class of defect HI-R01 fixes. A Chinese IME emits `ＡＢＣ` (U+FF21
U+FF22 U+FF23) or `ABC` for the same three letters depending on the mode it was in,
and `２０２４` for the year 2024. NFC does not touch any of them — they are
compatibility characters, not canonical variants — so without ZH-R01 the same
sentence typed on two machines is two archives and one search finds half of it.

What it deliberately does NOT do
--------------------------------
* **No full-width PUNCTUATION folding.** `，` `。` `：` are Chinese typography, not
  wide spellings of `,` `.` `:`. Folding them would rewrite the text a reader sees.
  Only the letter and digit ranges fold, because there the two forms are the same
  characters.
* **No traditional → simplified conversion.** That is a content decision with a
  political history and a dictionary behind it, not a cleaning rule.
* **No compatibility-ideograph rule — because NFC already is one.** This was checked
  rather than assumed: every one of the 1002 CJK Compatibility Ideographs in
  U+F900–U+FAFF and U+2F800–U+2FA1D has a *canonical* singleton decomposition, so
  NFC folds all of them and NFKC adds nothing. A ZH-R02 that re-implemented it would
  be dead code with a test that passes for the wrong reason. `tests/` asserts the
  base rules already do it, so the next reader does not add the rule back.

The tokenizer, and the floor it comes with
------------------------------------------
Chinese has no spaces, so `unicode61` indexes a whole sentence as one token and a
search for a word inside it finds nothing. The plugin therefore declares
`trigram`, which indexes overlapping three-character sequences.

Two consequences the catalog had to be taught, both measured rather than guessed
(see `docs/ADR/ADR-0024-tokenizer-recording.md`):

1. **A trigram index must be built with `detail=full`.** Under the catalog's
   `detail=column` (chosen for space-separated scripts, where positions buy nothing
   worth 32 % of the index) every query longer than three characters is a phrase
   query, and FTS5 refuses phrase queries outright: `今天天气` raised
   `fts5: phrase queries are not supported (detail!=full)`. So CJK documents get
   their own index at a different detail level rather than sharing one.
2. **A query shorter than three characters cannot match at all.** `公园` (two
   characters, one of the most common query shapes in Chinese) matches nothing under
   trigram. That is a floor of the tokenizer, not a bug in this plugin, and the
   honest thing is to state it and test it rather than let a user discover a silent
   zero. It is recorded in the ADR as open work, with the fallback named.

The property that makes any of this safe is unchanged: **plugins affect ingestion
only.** An archive written with `zh-1` decodes to the same bytes on a machine that
has never installed this package.
"""

from __future__ import annotations

import hashlib
import unicodedata

from lexora.canonicalize import canonicalize as _base_canonicalize
from lexora.langapi import LanguagePlugin

#: Rules this plugin applies, in order. The base three, then the Chinese one.
APPLIED_RULES: tuple[str, ...] = ("CAN-R01", "CAN-R02", "CAN-R05", "ZH-R01")

#: The label that lands in the 16-byte header field (ADR-0023).
PROVENANCE = "zh-1"

#: ZH-R01, spelled out rather than built from ranges: three contiguous blocks are
#: easy to read and impossible to get subtly wrong.
#:   U+FF10–U+FF19 full-width digits  -> 0-9
#:   U+FF21–U+FF3A full-width A-Z     -> A-Z
#:   U+FF41–U+FF5A full-width a-z     -> a-z
#:   U+3000 IDEOGRAPHIC SPACE         -> U+0020
#: Full-width punctuation (U+FF01–U+FF0F, U+FF1A–U+FF20, U+FF3B–U+FF40,
#: U+FF5B–U+FF5E) is deliberately absent — see the module docstring.
_FOLD: dict[int, str] = {}
_FOLD.update({0xFF10 + i: str(i) for i in range(10)})
_FOLD.update({0xFF21 + i: chr(ord("A") + i) for i in range(26)})
_FOLD.update({0xFF41 + i: chr(ord("a") + i) for i in range(26)})
_FOLD[0x3000] = " "


def canonicalize(raw: bytes, *, declared_encoding: str | None = None) -> bytes:
    """Base canonicalisation, then ZH-R01. Pure and deterministic (REQ-CAN-001)."""
    base = _base_canonicalize(raw, declared_encoding=declared_encoding)
    # Decoding what we just encoded is exact: the base rules emit valid UTF-8.
    text = unicodedata.normalize("NFC", base.decode("utf-8"))
    return text.translate(_FOLD).encode("utf-8")


def canonicalize_with_meta(raw: bytes, *, declared_encoding: str | None = None) -> dict:
    """canonicalize() plus the same audit metadata shape the base rules return."""
    c = canonicalize(raw, declared_encoding=declared_encoding)
    return {
        "canonicalizer_version": PROVENANCE,
        "applied_rules": list(APPLIED_RULES),
        "input_bytes": len(raw),
        "output_bytes": len(c),
        "input_sha256": hashlib.sha256(raw).hexdigest(),
        "output_sha256": hashlib.sha256(c).hexdigest(),
        "canonical": c,
    }


PLUGIN = LanguagePlugin(
    id="zh",
    version=1,
    name="Chinese",
    # Chinese has no word boundaries to split on, so the space-separated tokenizer
    # indexes a whole sentence as one token. Trigram indexes three-character
    # sequences instead, which is what makes a word inside a sentence findable.
    tokenizer="trigram",
    canonicalize=canonicalize,
    canonicalize_with_meta=canonicalize_with_meta,
    ocr_languages=("chi_sim",),
)


def plugin() -> LanguagePlugin:
    """Entry-point factory: `lexora.languages` = zh = lexora_lang_zh:plugin."""
    return PLUGIN
