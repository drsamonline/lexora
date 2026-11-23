"""Gujarati — the fourth language, and the first whose script-specific rule is *not* composition.

Why this package exists
-----------------------
REQ-CAN-005 names two scripts: Devanagari and Gujarati. Devanagari has shipped since
`packages/lexora-lang-hi` (ADR-0023); Gujarati had **no plugin and no vectors**, which meant the
requirement was half met by a document that said otherwise. This is the other half, and it is a
separate distribution for the same reason the Hindi one is: the proof that the seam is a seam is
that the core did not change to admit it.

What it adds over the base rules
--------------------------------
The base canonicaliser (CAN-R01 decode, CAN-R02 newlines, CAN-R05 soft-hyphen removal), then one
Gujarati rule:

  GU-R01 — NFC over the canonical text.

**And it does something different from HI-R01, which is the point of measuring instead of
copying.** Devanagari's win is *composition*: its nukta letters (क़ ख़ ग़ … U+0958–U+095F) are
composition exclusions, so NFC merges the precomposed letter with base + nukta. **Gujarati has no
precomposed nukta letters at all** — Unicode 15.0 defines **zero** canonical decompositions in the
whole U+0A80–U+0AFF block (asserted by a test, not assumed). So there is no pair of spellings to
merge, and a plugin that claimed Devanagari's byte saving here would be claiming something the
script cannot deliver.

Gujarati's NFC win is **canonical ordering**. The nukta (U+0ABC) has combining class 7 and the
virama (U+0ACD) class 9, so `ક` + virama + nukta and `ક` + nukta + virama are the same sequence
typed in two orders, and NFC settles both on the class order. Without it the same word is two
archives and a search finds half of them — the same *consequence* as Hindi, reached by a different
mechanism, and worth having for the same reason.

What it deliberately does NOT do
--------------------------------
* **No ZWJ/ZWNJ removal.** U+200C and U+200D change Gujarati conjunct shaping; deleting them
  changes the word. REQ-CAN-005 forbids touching them, and a test asserts they survive.
* **No digit transliteration** (૦–૯ to 0–9). A search-index decision, not a cleaning rule.
* **No legacy-font transcoding.** Gujarati text in the wild is often typed in non-Unicode 8-bit
  fonts (Terafont, Shree Lipi). Mapping those is a transcoding project with its own failure modes,
  not a canonicalisation rule, and pretending otherwise would corrupt text rather than clean it.
* **No transliteration or spelling normalisation.** Lexora stores text; it does not rewrite it.

The property that makes this safe: **plugins affect ingestion only.** An archive written with
`gu-1` decodes to the same bytes on a machine that has never installed this package.
`tests/test_language_gujarati_plugin.py` proves that in a subprocess where this module cannot be
imported.
"""

from __future__ import annotations

import hashlib
import unicodedata

from lexora.canonicalize import canonicalize as _base_canonicalize
from lexora.langapi import LanguagePlugin

#: Rules this plugin applies, in order. The base three, then the Gujarati one.
APPLIED_RULES: tuple[str, ...] = ("CAN-R01", "CAN-R02", "CAN-R05", "GU-R01")

#: The label that lands in the 16-byte header field (ADR-0023).
PROVENANCE = "gu-1"


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
    id="gu",
    version=1,
    name="Gujarati",
    # Gujarati is written with spaces between words, so FTS5's unicode61 tokenizer is
    # right; `trigram` is needed only for scripts with no word boundaries (CJK).
    tokenizer="unicode61",
    canonicalize=canonicalize,
    canonicalize_with_meta=canonicalize_with_meta,
    ocr_languages=("guj",),
)


def plugin() -> LanguagePlugin:
    """Entry-point factory: `lexora.languages` = gu = lexora_lang_gu:plugin."""
    return PLUGIN
