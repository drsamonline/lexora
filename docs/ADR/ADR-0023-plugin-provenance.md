# ADR-0023: A plugin's provenance is recorded in the header, and the second language is a package

> **Status:** **ACCEPTED 2026-11-09** (Forge cycle) — implements the half of ADR-0022 that was
> written but never wired: `LanguagePlugin.provenance` now reaches the archive's
> `canonicalizer_version` field, and a second language (`hi`) exists as a separate
> distribution to prove the seam.
> **Date:** 2026-11-09
> **Related:** [ADR-0022](ADR-0022-language-plugins.md) (the seam) · [ADR-0007](ADR-0007-container-v0-freeze.md)
> (the header layout) · [ADR-0020](ADR-0020-codec-id-naming.md) (the last change to this field) ·
> [ADR-0004](ADR-0004-cleaning-error-metric.md) (how a cleaning rule is judged)

## Context / Problem

ADR-0022 defined a language plugin as a declaration whose `provenance` string "lands in the
16-byte `canonicalizer_version` header field". It did not. `container._build_header()` wrote the
module constant `CANONICALIZER_VERSION` and nothing else, so:

* a file cleaned by a Hindi plugin would have claimed `lexcan-0.1` — a provenance field that
  states a falsehood is worse than an empty one;
* the v1.0 condition added on 2026-11-08 ("the plugin seam is proven by at least two languages")
  had no second language to prove it with, and no way to record that one had been used.

The seam also had a subtler gap: `langapi` was reachable only from `doctor`. Nothing in the
product could say *which* rules produced a payload.

## Decision

1. **`pack()` and `pack_stream()` take `canonicalizer_version: str | None = None`**, defaulting
   to `CANONICALIZER_VERSION`. The default keeps every archive byte-identical to before: this
   ADR changes *who may write* the field, not what existing archives contain. A test asserts the
   default output is unchanged byte for byte.
2. **The field is validated where it is written.** `_pad()` already refuses anything that does not
   fit 16 bytes; a non-ASCII provenance now raises `ContainerError` (`E-USAGE-005`) instead of
   escaping as a bare `UnicodeEncodeError` the CLI does not catch.
3. **Hindi ships as a separate distribution, `packages/lexora-lang-hi`**, registering through the
   `lexora.languages` entry point. It is deliberately **not** in `lexora/languages/`: the proof
   that the seam is a seam is that the core did not have to change to admit it. `langapi._builtins()`
   still returns English only, and a test asserts that.
4. **Its cleaning rule is HI-R01 = NFC** over the base canonicalisation. Devanagari nukta letters
   (U+0958–U+095F) are Unicode composition exclusions, so one word has two byte spellings in the
   wild; NFC settles both, and also puts combining marks in canonical order. It removes nothing —
   ZWJ/ZWNJ survive (REQ-CAN-005), and digits and spellings are not transliterated.
5. **Readability without the plugin is tested, not asserted.** `tests/test_language_hindi_plugin.py`
   packs an `hi-1` archive, then decodes it in a subprocess where `lexora_lang_hi` cannot be
   imported and `langapi` reports no `hi` — and requires the original bytes back.

## Consequences

* An archive now says which rules cleaned it. A reader needs no plugin to read it; it needs the
  plugin only to re-clean the same way.
* The header field becomes a small provenance namespace: `lexcan-0.1` (English, historical),
  `hi-1`, later `gu-1`, `zh-1`. Two plugins may not claim one label — the registry's collision
  rule and the 12-byte cap from ADR-0022 keep the namespace honest.
* **Not done here:** the CLI has no `--language` flag, so a plugin cannot yet be selected from the
  command line — the library surface is wired, the product surface is not. Recorded as P3.6 in
  [PATH_TO_V1](../PATH_TO_V1.md) rather than implied to be finished.
* The catalog still hardcodes `tokenize='unicode61'`; the plugin's `tokenizer` is declared and
  reported by `doctor` but not yet consumed by the index. That remains deferred until a
  tokenizer other than `unicode61` actually ships (ADR-0022 §2 fact 2).

## Verification

`PYTHONPATH=src:. python3 -m pytest -q` → **697 passed, 3 skipped** (was 680 passed, 3 skipped).
The 17 new tests are `tests/test_language_hindi_plugin.py`; one existing test was corrected —
`test_unknown_language_lists_what_is_available` asserted that `hi` was *absent*, which fails on
exactly the machines that installed the plugin, so it now uses an id no plugin claims.
