# ADR-0022: Language support arrives as plugins, and English becomes the first one

> **Status:** **ACCEPTED 2026-11-08** — owner direction: *"i want lexora to be able to support other
> languages through plugins and we can build them later and add them so lexora becomes a practical
> tool"*. **The seam is implemented** (`langapi.py`, `languages/english.py`, contract tests,
> `doctor` reporting); no second language ships, by design.
> **Date:** 2026-11-08
> **Related:** [PROJECT_CHARTER](../PROJECT_CHARTER.md) (multilingual design targets) · [ADR-0004](ADR-0004-cleaning-error-metric.md) (how a cleaning rule is judged) · [ADR-0016](ADR-0016-queryable-archive.md) (the index) · [ADR-0019](ADR-0019-ocr-plugin.md) (the plugin pattern this copies)

## Context / Problem

The charter names English, Hindi and Gujarati as design targets; the build has only ever
implemented English, and the cleaning rules in `canonicalize.py` are written as universal
("UTF-8, no BOM, LF, NFC") when several of them are really *English* choices — de-hyphenation,
ligature handling, quote style. Adding a language today would mean editing the canonicaliser
and changing every archive's bytes, with no way to say which rules produced a given file.

The owner wants language support to arrive as **plugins built later**, so the tool becomes
practical across languages without the core growing a branch per script.

## Two facts from the current code that shape the design

1. **`canonicalizer_version` is 16 bytes in the frozen header** (`container.py:201`), currently
   `lexcan-0.1`. A plugin identifier has to fit there *with* a version, or it needs a home
   outside the header. `lexcan-zh-hans-1.0` is 18 bytes — it does not fit.
2. **The search index is hardcoded to `tokenize='unicode61'`** (`catalog.py:70,184`). That is
   correct for space-separated scripts and **wrong for Chinese/Japanese**, where there are no
   spaces to split on. A language plugin must be able to choose the tokenizer, and changing it
   means **reindexing** — a fact the plan must carry, not discover.

## Decision

1. **A language plugin is a package that provides four optional things**, all declared:
   **cleaning rules** (the canonicalisation pass for that language), a **search tokenizer**
   (which FTS5 tokenizer the index should use), an optional **dictionary/trained model** (the
   M4 phase), and optional **OCR language hints** (which Tesseract codes to suggest).
2. **Plugins affect ingestion only. Decoding never needs one.** An archive stores canonical
   bytes; decompression is exact regardless of which rules produced them. So an archive written
   with the Hindi plugin is readable by a machine that has never installed it — the tool degrades
   to "you cannot re-canonicalise this, but you can read it". That property is the reason this
   design is safe.
3. **Provenance is mandatory and short.** The header field records `<lang>-<n>`, e.g. `en-1`,
   `hi-1`, `zh-1` (≤ 8 bytes, leaving room), with the full plugin name and version recorded in
   the catalog metadata (`db`) where there is no width limit. Archives stay comparable because
   the id changes when the rules change.
4. **English is refactored into the first plugin**, in the same release as the seam. A plugin
   system exercised by exactly one implementation is a plugin system that does not work; shipping
   the seam with English *as* a plugin is what proves it.
5. **The tokenizer is recorded per catalog**, not assumed. `db` stores the tokenizer id; opening
   a catalog built with a different tokenizer is refused with an instruction to reindex, rather
   than silently returning worse results.
6. **Plugins are code, so they are installed, never fetched.** Discovered through a Python entry
   point (`lexora.languages`), from installed packages only. Nothing in an archive, a metadata
   field or a path may cause code to load — an archive is data, and treating it as anything else
   is how archives become attack vectors.
7. **A plugin must pass a contract test suite** the core ships, and English is its reference
   implementation. A plugin that cannot pass cannot be installed by the CLI without `--force`,
   and `doctor` reports which plugins are present and valid.

## Consequences & trade-offs

**Positive.** Adding a language becomes a package, not a fork of the canonicaliser. Archives stay
readable without plugins. Provenance finally says *which* rules produced the bytes, which the
current single `lexcan-0.1` string only pretends to do. The multilingual charter goal stops being
vapour.

**Negative / accepted risks.**

- **The 16-byte field is tight.** Short ids work; anything longer needs a metadata field or a
  format version. This ADR takes the short-id route and accepts that plugin names are terse.
- **Tokenizer changes mean reindexing.** Not a bug — FTS5 indexes are tokenizer-specific — but it
  is a user-visible cost and must be documented before someone hits it.
- **A plugin can make archives incomparable.** Two archives of the same book cleaned by different
  plugin versions will differ byte-wise. That is correct and now *visible*, because the id is in
  the header.
- **Third-party code in the ingest path** is a new supply-chain surface. Mitigated by: installed
  packages only, contract tests, `doctor` reporting, and the fact that a bad plugin can corrupt
  *its own* ingest but cannot make a decoder return wrong bytes.

## Impact analysis

| Dimension | Impact |
|---|---|
| Security | New code-loading surface (entry points). No path from archive data to code execution |
| Performance | None in the core; a plugin's cleaning pass is its own cost |
| Compatibility | `canonicalizer_version` values change shape (`lexcan-0.1` → `en-1`). Old archives keep their old string and stay readable |
| Operations | `doctor` gains plugin reporting; `db` records the tokenizer and refuses a mismatch |

## Implementation & test implications

Not implemented. Order matters: **(a)** extract the English rules into a plugin behind the
contract, **(b)** ship the contract test suite, **(c)** record provenance and the tokenizer,
**(d)** only then build a second language — because the second language is the actual test of the
seam, and building it first would produce two special cases instead of one interface.

## Implementation note (2026-11-08)

Landed: `lexora.langapi` (the contract, the registry, discovery via the `lexora.languages`
entry point), `lexora.languages.english` as the reference plugin, `doctor` reporting, and 25
contract tests — of which **twelve deliberately broken plugins** must each fail for their own
reason. A contract that has only ever seen a valid implementation is a description of English,
not a contract.

**Two decisions made while implementing, both to avoid churn:**

1. **English keeps the provenance label `lexcan-0.1`,** via an explicit `provenance_label`
   override, rather than deriving `en-1`. ADR-0020 changed that header field *yesterday*; doing
   it again a day later would rewrite every archive twice for no reader benefit. New languages
   start at `hi-1`, `zh-1`; English's label can change once, with the format, at v1.
2. **English delegates to `canonicalize()` rather than copying the rules** into the plugin, and a
   test asserts the identity (`PLUGIN.canonicalize is canonicalize`). Copying would create a
   second source of truth that drifts from the tests pinning the first.

**Deliberately not done yet:** the catalog does not record its tokenizer, so a tokenizer mismatch
cannot yet be detected. That only matters once a second tokenizer exists (CJK/trigram), and it is
carried in the plan rather than pre-built.
