"""Hindi (Devanagari) — the second language plugin, and the proof the seam works.

Why this package exists
-----------------------
ADR-0022 says languages arrive as *installed packages* behind the
`lexora.languages` entry point, not as branches of the canonicaliser, and the
v1.0 condition became "the plugin seam is proven by at least two languages".
English alone cannot prove an interface: an interface with one implementation is
a description. This package is the second implementation, and it is deliberately
NOT in `lexora/languages/` — it is a separate distribution, so the proof is that
the core did not have to change to admit it.

What it adds over the base rules
--------------------------------
It applies the base canonicaliser (CAN-R01 decode, CAN-R02 newlines, CAN-R05
soft-hyphen removal) and then one Devanagari-specific rule:

  HI-R01 — NFC over the canonical text.

That is not cosmetic. Devanagari nukta letters (U+0958–U+095F: क़ ख़ ग़ ज़ ड़ ढ़
फ़ य़) are *composition exclusions*, so the same word has two byte spellings in
the wild — the precomposed letter and base + U+093C COMBINING NUKTA — and NFC
settles both on the decomposed form. The same rule puts combining marks in
canonical order, so a matra typed before its base still canonicalises to one
byte string. Without it, two files of the same Hindi text are two different
archives, and a search for क़ finds only half of them.

What it deliberately does NOT do
--------------------------------
* **No ZWJ/ZWNJ removal.** U+200C and U+200D change Devanagari conjunct shaping;
  deleting them changes the word. REQ-CAN-005 forbids touching them, and a test
  here asserts they survive.
* **No digit transliteration** (०–९ to 0–9). That is a search-index decision, not
  a cleaning rule; it would change stored bytes for a reader benefit nobody asked
  for.
* **No transliteration or spelling normalisation.** Lexora stores text, it does
  not rewrite it.

The property that makes this safe: **plugins affect ingestion only.** An archive
written with `hi-1` decodes to the same bytes on a machine that has never
installed this package. `tests/test_language_hindi_plugin.py` proves that in a
subprocess where this module cannot be imported.
"""

from __future__ import annotations

import hashlib
import unicodedata

from lexora.canonicalize import canonicalize as _base_canonicalize
from lexora.langapi import LanguagePlugin

#: Rules this plugin applies, in order. The base three, then the Devanagari one.
APPLIED_RULES: tuple[str, ...] = ("CAN-R01", "CAN-R02", "CAN-R05", "HI-R01")

#: The label that lands in the 16-byte header field (ADR-0023).
PROVENANCE = "hi-1"


def canonicalize(raw: bytes, *, declared_encoding: str | None = None) -> bytes:
    """Base canonicalisation, then NFC. Pure and deterministic (REQ-CAN-001)."""
    base = _base_canonicalize(raw, declared_encoding=declared_encoding)
    # Decoding what we just encoded is exact: the base rules emit valid UTF-8.
    text = unicodedata.normalize("NFC", base.decode("utf-8"))
    return text.encode("utf-8")


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
    id="hi",
    version=1,
    name="Hindi (Devanagari)",
    # Devanagari is written with spaces between words, so FTS5's unicode61
    # tokenizer is right; `trigram` would be needed only for CJK, which has no
    # word boundaries to split on.
    tokenizer="unicode61",
    canonicalize=canonicalize,
    canonicalize_with_meta=canonicalize_with_meta,
    ocr_languages=("hin",),
)


def plugin() -> LanguagePlugin:
    """Entry-point factory: `lexora.languages` = hi = lexora_lang_hi:plugin."""
    return PLUGIN
