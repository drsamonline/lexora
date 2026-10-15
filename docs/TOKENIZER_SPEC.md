# Tokenizer Specification (candidate layer)

> **Status:** Proposed — v0 draft; boundaries not frozen; no golden vectors exist
> **Owner:** Unassigned
> **Last verified:** 2026-10-15
> **Related:** [SPECIFICATION.md §3](SPECIFICATION.md) · [COMPRESSION_ARCHITECTURE.md](COMPRESSION_ARCHITECTURE.md)

## Purpose & Scope

Defines deterministic token boundaries used by experimental candidates (bounded token PPM, record coding). The Core Zstd path does **not** depend on this tokenizer; nothing here ships today.

## Design constraints

1. **Total coverage / literal fallback.** Every byte of canonical input is either inside exactly one token or emitted via a literal escape. No byte may be unrepresentable. This preserves `decode(encode(C)) == C` at the candidate layer.
2. **Determinism.** Tokenization is a pure function of (canonical bytes, tokenizer version). Same input ⇒ same token stream, across platforms and Python builds (Unicode tables pinned via the version identifier).
3. **Script safety.** Tokens MUST NOT split combining-mark sequences (Devanagari/Gujarati matras, virama joins, ZWJ/ZWNJ clusters). A token boundary may fall only at defined break classes.
4. **Versioning.** Tokenizer version participates in codec profile identity (`lexTok-<major>.<minor>` proposed); any boundary-rule change bumps major and requires new golden vectors.

## Draft token classes (v0 proposal)

| Class | Rule sketch | Notes |
|---|---|---|
| WORD | Maximal run of letters/marks per script-aware break table | Indic clusters kept whole |
| NUMBER | Digit runs incl. decimal separators/locale variants | Candidate for numeric/record coding |
| WS | Whitespace runs collapsed as single token class, length-prefixed | Exact spaces recoverable |
| PUNCT | Single non-alphanumeric chars outside word runs | Literal-safe |
| OTHER/BINARY | Any byte not matched → literal escape | Guarantees total coverage |

Whitespace policy detail (collapse-and-length-prefix vs. verbatim) is an open decision — must be resolved before Phase 3 experiments.

## Test vectors (required before any use)

Planned `tests/vectors/tokenizer/`: English prose, Hindi, Gujarati, mixed numerics, pathological byte sequences (invalid UTF-8 cannot occur post-canonicalization; surrogate-like edge cases still tested). *None exist yet.*

## Open decisions

1. Break-table source (ICU-derived static table vs. hand-curated minimal set) — memory trade-off unmeasured.
2. Whitespace encoding policy.
3. Whether record-shaped inputs get a separate grammar-mode tokenizer (likely yes for REQ-EXP numeric coding; needs evidence).
