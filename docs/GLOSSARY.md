# LEXORA Glossary

> **Status:** Active — will grow with Batch B documents
> **Owner:** Unassigned
> **Last verified:** 2026-10-15 (commit `816f58f`)

| Term | Definition | Notes |
|---|---|---|
| **Canonical bytes / canonical text (`C`)** | The deterministic UTF-8 byte string produced by a specific version of the canonicalizer from extracted source text. The compression layer only ever sees `C`. | Losslessness is defined w.r.t. `C`, never w.r.t. the original file. |
| **Canonicalization** | Conservative, rule-driven cleaning/normalization of extracted text into canonical bytes. May be lossy relative to the source; every transformation must be in the approved rule table. | Versioned; see REQ-CAN-* |
| **Byte-exact losslessness** | Property that `decode(encode(C)) == C` for all inputs, verified at build time on 100% of archived content. | LEXORA's core invariant (REQ-CMP-001). |
| **Core baseline** | The always-available Zstandard codec path that guarantees a working archive even when no experimental candidate wins. | Blueprint §8. |
| **Candidate / experimental candidate** | An alternative representation or codec (dictionary, Re-Pair grammar, token PPM, numeric/record coder, template+residual) evaluated against baselines and admitted only by measured evidence. | Never presented as shipped until gated. |
| **Cost model** | Accounting rules ensuring the *total serialized size* (payload + headers + side data + dictionaries/grammars + block metadata) determines which encoder wins. | REQ-CMP-004. |
| **Total stored size** | Sum of every byte written to the archive attributable to a corpus, including shared-resource amortization per protocol. | Basis for Pass/Partial/Fail gates. |
| **Frozen baseline** | A pinned compressor + exact version + settings whose results are recorded in a benchmark revision and cannot change mid-revision. | Zstd-19, Brotli q11, XZ/LZMA, PPMd (pinning pending OQ-2/OQ-3). |
| **Pass / Partial / Fail gate** | Proposed acceptance levels vs. best frozen baseline: ≥ 10% smaller = Pass; ≥ 3% and < 10% = Partial; < 3% = Fail. | Blueprint §12; scope conflict open (OQ-1). |
| **Ablation** | Re-measuring a system with one component removed to verify that component still earns its cost. | Required each benchmark revision. |
| **Lineage** | The provenance group of a document (source file, collection, translation family). Train/validation/held-out splits must separate by lineage to prevent leakage. | 70/10/20 split (REQ-BMK-001). |
| **Held-out set** | Corpus portion never used to induce dictionaries/grammars or tune settings; used only for final measurement. | Leakage control. |
| **Block** | Self-contained unit of compressed payload enabling bounded-memory decode of a single document without reading the whole archive. | REQ-CMP-005. |
| **Dictionary (shared)** | Pre-trained LZ dictionary embedded/referenced by an archive to improve small-file compression; identity fixed by content hash. | Candidate, not Core. |
| **Re-Pair** | Grammar-based symbol-substitution compression; iteratively replaces frequent bigrams with new symbols. | Candidate. |
| **PPM / PPMd** | Prediction-by-participation-mixture context modeling (PPMd = Dmitry Shkarin's implementation). | Candidate & baseline role unresolved (OQ-3). |
| **Token PPM (bounded)** | Order-limited PPM over a token alphabet derived from the tokenizer, with bounded context memory. | Candidate. |
| **Tokenizer** | Deterministic Unicode-aware splitter defining token boundaries for token-level candidates; literal fallback guarantees any byte sequence is encodable. | Spec planned Batch B. |
| **Template + residual** | Encoding records as (template, per-record residual) pairs when structure is detected. | Candidate. |
| **`.lxz`** | Proposed single-file archive format for compressed corpora. **Layout NOT yet defined/frozen.** | FORMAT_LXZ.md (Batch B) will carry the proposal. |
| **`.lxdb`** | Proposed incremental database mode atop `.lxz` principles. Deferred. | REQ-FMT-004. |
| **OCR** | Optical character recognition (Tesseract-class) for scanned PDF pages; optional dependency. | Corrections gated by confidence (REQ-CAN-006). |
| **Codec ID / profile ID** | Numeric identifiers recorded in archives naming the exact decoder semantics required. Unknown IDs ⇒ refusal. | REQ-CMP-006. |
| **ADR** | Architecture Decision Record — numbered markdown doc capturing a material decision (status, context, options, consequences). | See [DECISIONS.md](DECISIONS.md). |
| **Round-trip verification** | Build-time check that decoding what was just encoded reproduces canonical bytes exactly. | Enforced for every archived document. |
| **Benchmark revision** | A frozen combination of corpus manifest hash, baseline pins, protocol version, and environment snapshot producing one comparable results set. | New revision required to compare changes. |
| **Specification identifier** | `LEXORA-SPEC-1.0-draft` for the first normative spec. Distinct from software version and file-format version. | Master-prompt §1.4. |
