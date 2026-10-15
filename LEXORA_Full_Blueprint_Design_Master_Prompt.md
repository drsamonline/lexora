# LEXORA — Full Blueprint, Technical Design & Master Implementation Prompt

**Document ID:** `LEXORA-MASTER-BLUEPRINT-1.0-draft`  
**Project:** LEXORA — *Layered Exact-text Repository & Adaptive Compression Architecture*  
**Owner:** Dr. Sohil Momin  
**Status:** Complete planning blueprint; technical specification remains a draft  
**Implementation status:** Not asserted; no compression gains claimed  
**Target:** Low-resource Windows computer, approximately 4 GiB RAM  
**Primary deliverables:** TXT/PDF ingestion and OCR cleaning, exact canonical-text compression, `.lxz` immutable archive, later `.lxdb` mutable text database

> All numeric values below are proposed engineering targets, not measured results. LEXORA must not claim better compression until a reproducible held-out benchmark demonstrates it.

---

# 1. Mission and non-negotiable contracts

LEXORA ingests TXT and PDF files, optionally OCRs scanned pages, conservatively cleans the extracted text, converts it into a documented canonical UTF-8 representation, and compresses that representation.

It has two distinct stages:

1. **Canonicalization:** May intentionally change the source text to remove high-confidence OCR/layout artifacts. This stage must be versioned, conservative, and testable.
2. **Compression:** Must be exactly lossless relative to canonical bytes. Decoding must reproduce the same bytes, not merely visually similar text.

For canonical byte sequence `C`:

`decode(encode(C)) == C`

LEXORA does not need to reconstruct the original scan, original PDF layout, or original OCR output.

## 1.1 Primary objectives

- Remove high-confidence OCR artifacts without deleting meaningful content.
- Preserve meaningful paragraphs, repeated passages, citations, captions, tables, headings, lists, references, punctuation, casing, numbers, and identifiers.
- Support English, Hindi, Gujarati, mixed scripts, and Unicode.
- Achieve the smallest practical total stored size, including dictionaries, indexes, headers, activation maps, and metadata.
- Use independently decodable blocks and bounded decoding.
- Start with established compression algorithms; introduce experimental strategies only when measured benefit justifies their cost.
- Remain usable on a 4 GiB RAM computer without mandatory cloud APIs, GPUs, or network access.
- Prototype in Python; consider Rust only after profiling identifies a real bottleneck.

## 1.2 Non-goals

LEXORA 1.0 does not promise original-source recovery, semantic summarization, universal superiority over existing compressors, a custom entropy coder, neural compression, or a fully featured multi-user database in the first phase. Compression is not encryption. Similarity alone must never trigger automatic deletion of text.

## 1.3 Conformance vocabulary

Uppercase **MUST**, **MUST NOT**, **SHOULD**, **SHOULD NOT**, and **MAY** are normative terms, following RFC 2119/RFC 8174 conventions. MUST indicates an absolute requirement; SHOULD indicates a recommendation that can be deviated from only with documented justification; MAY indicates an option.

## 1.4 Version lineage

`LEXORA-SPEC-1.0-draft` is the first proposed normative blueprint. The earlier “v2.2” label referred to informal architecture notes, not a released file format. No 2.0 or 2.1 implementation is implied.

---

# 2. Architecture overview

```text
TXT / Markdown / PDF
        |
        v
Input adapters
  |-- TXT reader
  |-- PDF text extraction
  |-- optional OCR for scanned pages
        |
        v
Document reconstruction
  |-- page and reading order
  |-- columns and paragraphs
  |-- headings, lists, tables, footnotes
        |
        v
OCR quality assessment + conservative cleaning
  |-- repeated headers/footers
  |-- page-number detection
  |-- line breaks and hyphenation
  |-- confidence-based corrections
  |-- duplicate candidates (flag, don't silently delete)
        |
        v
Canonicalization (versioned UTF-8)
        |
        v
Representation candidates
  |-- Core bytes + Zstandard
  |-- global/domain dictionaries
  |-- Re-Pair grammar
  |-- token-level PPM
  |-- numeric/date coding
  |-- record/column coding
  |-- template + residual
        |
        v
Cost-driven selector
        |
        v
Versioned framing + checksums + resource limits
        |
        +--> .lxz immutable archive
        |
        +--> .lxdb mutable/searchable database (later)
```

## 2.1 Component responsibilities

**Ingestion adapters:** Read TXT, extract embedded PDF text, and optionally OCR image-only or poorly extracted pages. Record extractor/OCR versions and settings.

**Document reconstruction:** Rebuild reading order, columns, paragraphs, headings, lists, tables, and footnotes where confidence permits. When uncertain, prefer preserving content over silently dropping it.

**Cleaning engine:** Each cleaning rule has a stable rule ID, conditions, transformation, confidence criterion, tests, and optional audit-log entry. Risky rules can be disabled independently.

**Canonicalizer:** Produces the exact canonical bytes to compress. It is separate from the decoder.

**Representation engine:** Trials eligible encodings and reports serialized size, dependencies, codec/profile, time, memory, and integrity information.

**Container layer:** Stores blocks, headers, indexes, dictionaries, and metadata independently of the codec implementation.

---

# 3. Ingestion and canonicalization

## 3.1 Input adapters

### TXT
- Accept an explicit encoding or use a documented detection policy.
- Specify invalid-byte handling; do not silently replace invalid sequences without recording the policy.
- Preserve source hash/provenance where lawful.
- Pass decoded text to canonicalization.

### PDF
- Extract embedded text first.
- Detect pages with missing or poor extraction.
- OCR only when required and enabled.
- Preserve page boundaries and coordinates when available.
- Record extraction method/version.

### OCR
Tesseract is an initial optional candidate, not a hard dependency of the architecture. OCR must be replaceable through an adapter. Record language packs, engine version, and settings. Confidence is evidence, not proof of correctness.

## 3.2 Proposed `LEXORA-CANON-1` profile

The profile must be finalized with frozen test vectors before it is treated as normative.

- Output encoding: UTF-8.
- Unicode normalization: NFC.
- Line endings: LF (`0A`).
- Leading UTF-8 BOM: removed.
- Trailing horizontal whitespace: removed from each line.
- Meaningful paragraph breaks and blank lines: preserved.
- Punctuation, casing, numbers, dates, identifiers, URLs, and email addresses: preserved.
- References, footnotes, captions, headings, tables, lists, and repeated passages: not deleted by default.
- Ambiguous OCR substitutions such as `l`/`1`, `O`/`0`, and `rn`/`m`: never globally replaced.
- Hyphenated line-end words: joined only when evidence is sufficient; otherwise preserved.
- Repeated paragraphs: may be flagged for review, but similarity alone MUST NOT trigger deletion.
- Repeated headers/footers and page numbers: removed only by high-confidence rules using position, recurrence, page structure, and sequence.

PDF extraction, OCR correction, reading-order reconstruction, and canonicalization must be independently identifiable. Cleaning should offer an optional audit report with document/page/line, rule ID, reason/confidence, and before/after content where safe.

## 3.3 Canonicalization manifest

Recommended fields:
- source SHA-256;
- canonical-output SHA-256;
- input type;
- extractor/OCR version and settings;
- canonicalizer version/profile;
- language hints;
- cleaning operations;
- page/line provenance when available.

A hash proves neither source recovery nor anonymization. Audit logs may contain sensitive text and must follow the source's privacy controls.

## 3.4 Reversible tokenizer

Tokenization is a representation layer, not a cleaning layer. Token IDs plus literal fallback must reconstruct every canonical byte, including whitespace and punctuation.

Token classes may include WORD, NUMBER, DATE, TIME, PUNCTUATION, WHITESPACE, NEWLINE, URL, EMAIL, CODE_FRAGMENT, and UNKNOWN_BYTES. The specification must define token boundaries, Unicode handling, literal/OOV fallback, ID serialization, reconstruction, and profile/version IDs.

Morphological stems may be predictive features, but must not replace original tokens unless all removed information is reversibly represented.

For blocks under 2 KiB, use the Core path unless a complete alternative is smaller after all dictionary, activation, framing, and metadata costs.

Maintain `tokenizer-test-vectors.json` with at least 1,000 frozen cases covering English, Hindi, Gujarati, mixed scripts, whitespace, punctuation, uncommon Unicode, URLs, numbers, and malformed-input boundaries. Each vector specifies expected tokens and reconstructed bytes. A change to a frozen vector requires a versioned profile or explicit compatibility change.

---

# 4. Compression architecture

## 4.1 Core baseline

The first codec is canonical UTF-8 bytes compressed with Zstandard. It provides:
- the correctness reference;
- the first reproducible compression measurement;
- a fallback for every experimental stage;
- baseline speed and memory figures;
- a known codec instead of a custom entropy coder.

Do not build a custom entropy coder before the harness and established-codec baseline are stable.

## 4.2 Optional representation candidates

### A. Global/domain dictionaries
Train only from permitted training documents. Support global, domain, document, and block scopes. Dictionaries must have immutable content-addressed versions, stable ID mappings, tokenizer profile IDs, literal/OOV fallback, and complete size accounting.

Dictionary activation may use implicit activation, sparse sorted IDs, bitmap, or run-length bitmap. Choose by actual serialized cost. Do not automatically use a full bitmap for small blocks.

Sensitive clinical documents must not contribute to shared global/domain dictionary induction by default. They may still be evaluated and encoded with permitted dictionaries, local representations, or Core fallback.

### B. Re-Pair grammar
Re-Pair discovers repeated adjacent symbol pairs and replaces them with grammar symbols. It is optional, not guaranteed to help. Count every rule and reference byte. Enforce rule/depth/memory limits. Reject cycles, invalid IDs, excessive depth, and expansion beyond declared decoded length.

### C. Token-level PPM
Use a pinned, established PPMd implementation as a reference. Initial custom token-PPM limits:
- maximum context order: 4;
- maximum model memory: 64 MiB per block;
- reset contexts at block boundaries;
- specify initialization, context ordering, escape mechanics, exclusion, update timing, termination, and literal/OOV fallback.

Order 4 is a resource/complexity design point, not a claim that higher orders are universally worse. Where supported, compare PPMd orders 4 and 6 so the custom cap is not evaluated against an artificially weak baseline.

### D. Numeric/date coding
Evaluate delta coding, varints, Rice/FOR-style integer coding, structured dates, and exact scaled integers. Retain literal fallback. Include schema and metadata overhead.

### E. Record/columnar coding
Potentially useful for tables, clinical forms, repertories, logs, CSV/JSON-like data, and repeated forms. Use only when structure is confidently detected. Include schema, null map, field types, dictionary, index, and ordering metadata. Preserve order unless a recorded reordering demonstrably saves more than its map costs.

### F. Template + residual
For repeated documents, encode a shared template plus exact variable-field residuals. Count template, field map, escaping, version, and residual bytes. Decoding must reproduce canonical bytes exactly.

### G. Neural compression/context mixing
Out of scope for the initial prototype. Revisit only after classical strategies have a stable benchmark and measured remaining gap. No mandatory GPU/cloud dependency.

## 4.3 Cost-driven selection

For each candidate:

`total_bytes = payload_bytes + dictionary_bytes + grammar_bytes + activation_bytes + index_bytes + header_bytes + metadata_bytes`

Storage reduction:

`storage_reduction_percent = 100 * (1 - lexora_total_bytes / baseline_total_bytes)`

Compression ratio:

`compression_ratio = canonical_input_bytes / total_stored_bytes`

Report both. A database comparison must use a baseline with equivalent functionality. Trial-encode candidates when practical. Expensive candidates may be screened on a representative sample, but any accepted final candidate must be measured on the full held-out set.

The encoder chooses the smallest complete valid representation within configured time and memory budgets. Estimated payload savings alone do not qualify.

---

# 5. Resource and performance budget

These are proposed targets, not measured results. Freeze them before formal evaluation.

| Requirement | Proposed limit |
|---|---:|
| Maximum decoded block | 1 MiB |
| Default block target | 64 KiB |
| Maximum dictionary entries | 65,535 per dictionary |
| Maximum serialized dictionary | 8 MiB per dictionary |
| Maximum grammar rules | 65,536 per block |
| Maximum grammar expansion depth | 32 |
| Maximum custom PPM order | 4 |
| Maximum PPM model memory | 64 MiB per block |
| Decoder process memory budget | 128 MiB |
| Encoder process memory budget | 512 MiB |
| Core decode throughput target | ≥20 MiB/s |
| Random block decode latency | ≤25 ms p95 for 64 KiB, excluding storage I/O |
| Required block checksum | CRC32C |
| Canonical encoding | UTF-8 |
| Canonical line ending | LF |

The reference machine must have 4 GiB RAM. Record exact CPU, OS, storage, power mode, and software versions. Results from different machines must be reported separately.

The decoder must validate lengths and enforce allocation/output limits before allocating. A compression-ratio limit alone does not prevent decompression bombs.

---

# 6. Benchmark design and anti-leakage

## 6.1 Target corpus to assemble

This corpus is a target, not a claim that a validated dataset already exists.

| Requirement | Minimum target |
|---|---:|
| Total canonical text | ≥1 GiB |
| Distinct documents | ≥2,000 |
| English | ≥40% of canonical bytes |
| Hindi | ≥10% |
| Gujarati | ≥10% |
| Mixed-language or other scripts | ≥5% |
| OCR-derived documents | ≥60% of documents |
| Born-digital/searchable PDFs | ≥15% |
| TXT/Markdown/plain text | ≥10% |
| Tables/forms/clinical-style/repertory-like structured text | ≥10% |

Categories may overlap. Include noisy OCR, multi-column layouts, headers/footers, tables, references, long books, tiny files, and mixed Unicode. Synthetic examples may supplement but not replace real-document minimums.

Clinical or sensitive documents may be included in evaluation only under appropriate authorization/privacy controls. They must not train shared dictionaries by default.

## 6.2 Train/validation/held-out split

Split by document and source lineage, never by blocks from the same source:
- Training: 70% of documents.
- Validation: 10%.
- Held-out test: 20%.

Global/domain dictionaries and corpus-induced grammar rules are trained only on training documents. Validation selects parameters. Held-out data is reserved for final evaluation.

Per-document transforms such as local repetition analysis are allowed, but all serialized costs must be counted. If held-out results are used to tune a new combination, that set becomes development data and a new held-out set is required.

Frozen artifacts:
- `corpus_manifest.json`
- `corpus_manifest.sha256`
- `benchmark_config.json`
- `baseline_versions.json`
- `results.json`
- canonicalization and tokenizer test vectors

The manifest records IDs, source lineage, split, language/script, category, hashes where lawful, and processing versions. Any change requires a new benchmark revision.

## 6.3 Baselines and acceptance gate

Compare against:
- Zstandard level 19;
- Brotli quality 11;
- XZ/LZMA with pinned settings;
- 7-Zip PPMd with pinned settings and model order.

Pin versions, command lines, thread counts, and relevant settings in `baseline_versions.json`. Give every baseline identical canonical input bytes.

On the frozen held-out target corpus:
- **Pass:** at least 10% smaller total stored size than the best baseline.
- **Partial:** at least 3% but less than 10% smaller.
- **Fail:** less than 3% smaller, including parity or regression.

The 10% gate is intentionally ambitious. Partial is not a full pass. Do not generalize beyond the tested corpus.

Required reports:
- total input and stored bytes;
- dictionaries/indexes/headers/metadata;
- compression ratio and storage reduction;
- encode/decode throughput and peak memory;
- per-document and per-category results;
- random-read latency;
- OCR cleaning precision/recall on labelled examples;
- round-trip equality, corruption detection, and database crash recovery where applicable.

## 6.4 Dependency-aware kill criteria

Do not prune optional strategies greedily. Test each stage alone where meaningful, with declared prerequisites, and in combinations. A weak standalone result does not automatically eliminate a stage needed by a strong combination.

| Stage | Fallback | Proposed threshold |
|---|---|---|
| Global/domain dictionaries | Core | ≥2% total-size improvement over Core for general enablement |
| Re-Pair | Best non-Re-Pair prerequisite candidate | ≥2% net improvement after rule costs |
| Token PPM | Best non-PPM prerequisite candidate | ≥3% total-size improvement and within memory limit |
| Numeric/date coding | General candidate | ≥5% improvement on labelled numeric/record subset after overhead |
| Record/columnar coding | General candidate | ≥5% improvement on labelled structured subset with exact order/value recovery |
| Adaptive block boundaries | Fixed 64 KiB target | ≥1% total-size improvement and no >10% p95 latency regression, unless profile-specific requirements justify it |
| Specialized tokenizer | Canonical bytes + Core | ≥2% total-size improvement and all test vectors pass |

A failed standalone stage may remain as a prerequisite only if a predeclared combination passes validation and demonstrates the required benefit on held-out data. Restrict it to that validated profile. Any tuning based on held-out data requires a new test set.

---

# 7. File formats

## 7.1 `.lxz` immutable archive

Purpose: compact, portable, immutable collection of cleaned text.

Proposed logical components:
1. Superblock.
2. Document catalog.
3. Shared dictionary catalog.
4. Independently decodable compressed blocks.
5. Document-to-block index.
6. Optional full-text index.
7. Integrity and manifest metadata.

Keep the first format simple. Optional indexes must be declared and counted.

## 7.2 `.lxdb` mutable text database

Purpose: searchable/updatable text repository, built only after `.lxz` and codec interfaces stabilize.

Proposed components:
1. Superblock and committed-root pointer.
2. Document catalog.
3. Dictionary catalog.
4. Compressed blocks.
5. Document/block index.
6. Optional full-text index.
7. Transaction/recovery metadata.

Start with append-oriented updates and a recoverable committed-root pointer; use compaction to reclaim obsolete blocks. Prefer a proven B-tree/B+ tree or embedded database component over inventing a custom index prematurely.

## 7.3 Framing and compatibility

File header must include:
- fixed magic bytes;
- major/minor format version;
- feature flags;
- header length;
- explicit byte order;
- integrity metadata.

Block header must identify:
- codec/representation ID;
- required/optional feature flags;
- compressed and decoded lengths;
- dictionary ID/hash/version as needed;
- checksum;
- representation-specific decoding metadata.

Lengths must be validated before allocation. Blocks must be independently decodable. Unknown required features, unsupported major versions, unknown required codecs, malformed lengths, and invalid dictionary references must fail closed. Unknown optional metadata may be skipped only when framing explicitly permits safe skipping.

CRC32C is mandatory per block. SHA-256 or BLAKE3 is recommended for dictionary identity and optional whole-object verification.

### Versioning and dictionaries

- A codec tag alone is not a compatibility contract.
- Decoding rules must be normative and versioned.
- Major versions may break compatibility; minor versions may add only explicitly optional features with defined skip behavior.
- Every immutable dictionary must have a content hash over canonical serialized bytes plus tokenizer/profile identity.
- Dictionary IDs must never silently change meaning.

## 7.4 Database recovery

After a crash, `.lxdb` must recover either the previous committed state or the complete new committed state. Silent mixed-state recovery is prohibited. Test interruptions during block append, catalog/index update, root commit, and compaction.

---

# 8. Security and privacy

## 8.1 Decoder limits

Bound allocations, decoded output, dictionary size/count, grammar rules/depth, expansion, PPM memory, index traversal, and file offsets. Validate before use. Avoid unbounded recursion and never silently truncate output. Fuzz headers, dictionaries, grammar, token streams, encrypted blocks, and truncated files.

## 8.2 Encryption

Encryption is optional and must use a vetted AEAD library, never a custom cipher.

Supported candidates:
- ChaCha20-Poly1305, 256-bit key, 96-bit nonce.
- AES-256-GCM, 256-bit key, 96-bit nonce.

Proposed scope is per block. Header fields affecting interpretation must be authenticated as associated data. Authentication failure aborts decoding; unauthenticated plaintext must not be returned as valid. Indexes/metadata affecting navigation must also be authenticated or covered by an authenticated integrity structure.

### Key management and nonce safety

The user/application supplies the key or obtains it from an OS credential store/documented key-management system. Do not derive secrets from document text or public hashes. Never store keys in plaintext in the archive.

A nonce must never repeat under the same key. Select and document a crash-safe scheme: a durable per-key counter or a correctly designed random-nonce scheme with explicit collision budget and strict per-key usage limit. Counters must not roll back after crashes or restored backups. If uniqueness cannot be guaranteed, encryption must stop. Define the maximum encrypted blocks/bytes per key before release.

Key rotation requires a new key identity and fresh nonces. Re-encryption must verify the new representation before discarding the old one. Compression and dictionary coding provide no confidentiality. Shared dictionaries may leak vocabulary and must be considered alongside encryption and clinical-data privacy.

---

# 9. Implementation sequence

1. Freeze specification interfaces and test-vector formats.
2. Implement TXT ingestion and canonicalization tests.
3. Implement PDF extraction and optional OCR adapter.
4. Build benchmark harness and Zstandard Core baseline.
5. Assemble and freeze corpus, splits, and baseline versions.
6. Implement and evaluate dictionaries.
7. Implement and evaluate Re-Pair.
8. Implement and evaluate bounded token-level PPM.
9. Evaluate numeric/date and record encoders.
10. Implement dependency-aware cost-driven selection.
11. Implement `.lxz`.
12. Implement `.lxdb` only after archive/codec interfaces stabilize.
13. Add encryption only after threat review and nonce design.
14. Consider Rust only after profiling identifies a meaningful bottleneck.

## 9.1 Engineering workflow

For each batch:
1. Inspect the actual repository and dependencies before editing.
2. State scope and acceptance tests.
3. Implement only files required for the current phase.
4. Run unit, round-trip, and static checks.
5. Inspect diffs and test output.
6. Report completed work, failed tests, and limitations honestly.
7. Create a commit/checkpoint after every five modified files when repository access supports it.
8. Never claim tests or benchmarks passed unless they were run.
9. Keep documentation aligned with implementation.
10. Stop and report contradictions rather than silently making architecture changes.

## 9.2 Proposed repository layout

```text
lexora/
├── README.md
├── pyproject.toml
├── docs/
│   ├── MASTER_BLUEPRINT.md
│   ├── SPECIFICATION.md
│   ├── FORMAT_LXZ.md
│   ├── FORMAT_LXDB.md
│   ├── SECURITY.md
│   ├── BENCHMARK_PROTOCOL.md
│   └── DECISIONS.md
├── spec/
│   ├── canonicalization/
│   ├── tokenizer/
│   ├── format/
│   └── test-vectors/
├── src/lexora/
│   ├── cli/
│   ├── ingest/
│   ├── pdf/
│   ├── ocr/
│   ├── cleaning/
│   ├── canonical/
│   ├── tokenize/
│   ├── codecs/
│   ├── selector/
│   ├── container/
│   ├── archive/
│   ├── database/
│   ├── integrity/
│   └── limits.py
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── roundtrip/
│   ├── corruption/
│   ├── fuzz/
│   └── cleaning/
├── benchmarks/
│   ├── harness/
│   ├── corpus_manifest.json
│   ├── benchmark_config.json
│   ├── baseline_versions.json
│   └── results/
└── scripts/
```

This is a proposal, not a claim that files already exist. Create only what the current phase requires.

## 9.3 Technology choices

- Python for the prototype and orchestration.
- PyMuPDF as a PDF extraction candidate, subject to dependency/license review.
- Tesseract as an optional OCR engine.
- Zstandard for Core.
- Pinned benchmark dependencies.
- Proven embedded index/database components where needed.
- Rust only for profiled bottlenecks.
- No mandatory cloud service or network access for Core.

---

# 10. Testing and release gates

## 10.1 Correctness tests

Test canonicalization golden cases, tokenizer reconstruction, exact round trips, mixed Unicode, empty/tiny files, long repetitive text, random/incompressible data, already-compressed data, corrupted headers, truncated blocks, wrong dictionary hashes, unknown required features, invalid grammar references/cycles, excessive expansion, checksum failures, and AEAD failures if encryption is enabled.

## 10.2 Cleaning evaluation

Build labelled examples for headers/footers, meaningful repeated lines, page numbers, broken words, multi-column text, tables, captions, references, footnotes, ambiguous OCR substitutions, and English/Hindi/Gujarati/mixed scripts.

Measure precision and recall separately. Proposed target for high-confidence header/footer removal is ≥99% precision; recall must be reported separately. Do not optimize recall by silently deleting meaningful content.

## 10.3 Benchmark reproducibility

Save machine/OS details, implementation commit, dependency versions, baseline commands, corpus manifest hash, split hash, codec settings, total-byte accounting, timings, peak memory, per-document results, category aggregates, and exclusions/failures.

## 10.4 Release blockers

Block release if:
- any canonical round-trip mismatch exists;
- decoder limits can be bypassed;
- malformed input causes uncontrolled allocation/recursion;
- integrity/authentication failures are ignored;
- unsupported required features are silently skipped;
- benchmark runs are not reproducible;
- metadata/dictionaries are omitted from cost accounting;
- cleaning silently deletes meaningful text;
- an enabled experimental stage lacks qualifying evidence or a declared profile restriction.

Compression gate: ≥10% smaller than best frozen baseline = pass; 3–10% = partial; <3% = fail for that benchmark revision. Cleaning and compression results remain separate.

---

# 11. Prior art and references

1. Bradner, S. “Key words for use in RFCs to Indicate Requirement Levels.” RFC 2119, March 1997. https://www.rfc-editor.org/rfc/rfc2119
2. Leiba, B. “Ambiguity of Uppercase vs Lowercase in RFC 2119 Key Words.” RFC 8174, May 2017. https://www.rfc-editor.org/rfc/rfc8174
3. Collet, Y. and M. Kucherawy. “Zstandard Compression and the application/zstd Media Type.” RFC 8878, February 2021. https://www.rfc-editor.org/rfc/rfc8878
4. Alakuijala, J. and Z. Szabadka. “Brotli Compressed Data Format.” RFC 7932, July 2016. https://www.rfc-editor.org/rfc/rfc7932
5. Larsson, N. J. and A. Moffat. “Off-line dictionary-based compression.” *Proceedings of the IEEE*, 88(11), 1722–1732, 2000. DOI: https://doi.org/10.1109/5.892708
6. Shkarin, D. “PPM: One Step to Practicality.” *Data Compression Conference (DCC)*, 2002. Cite the exact PPMd implementation/version used in benchmark results.
7. Tukaani Project, XZ Utils documentation: https://tukaani.org/xz/
8. 7-Zip documentation and implementation: https://www.7-zip.org/

These sources document prior art; they do not prove that LEXORA outperforms any baseline.

# 12. Glossary

- **Canonical text:** Cleaned/normalized text treated as authoritative for compression.
- **Canonical bytes:** Exact UTF-8 byte sequence of canonical text.
- **Canonicalization:** Extraction and cleaning; may be lossy relative to source.
- **Codec:** Encoding/decoding algorithm.
- **Core profile:** Minimal independent-block representation using a proven codec, framing, and integrity checks.
- **Dictionary activation:** Per-block metadata defining available dictionary entries.
- **Held-out test set:** Documents excluded from training and parameter selection.
- **OOV/literal fallback:** Exact representation for tokens not in a dictionary.
- **PPM:** Prediction by Partial Matching, a context-based compression family.
- **Re-Pair:** Grammar-based compression that replaces repeated adjacent symbol pairs.
- **Source lineage:** Documents derived from the same source or near-duplicate source family.
- **Total stored bytes:** Payload plus dictionaries, rules, activation data, indexes, framing, and metadata.
- **AEAD:** Authenticated encryption with associated data.

---

# 13. Master implementation prompt

Copy the following prompt into a coding assistant when implementation begins.

## MASTER PROMPT — LEXORA

You are the lead software architect and implementation engineer for LEXORA. Treat this blueprint as the current project source of truth. Do not invent completed work, benchmark results, repository state, file contents, or test outcomes.

### Mission

Build a low-resource application that accepts TXT and PDF files, optionally OCRs scanned pages, conservatively cleans OCR artifacts, produces canonical UTF-8 text, and compresses that canonical text with byte-for-byte lossless decoding. Original OCR/source recovery is not required.

### Mandatory rules

1. Inspect the actual repository, dependencies, runtime, and tests before editing.
2. Follow documentation-first, phase-controlled development. If the blueprint conflicts with the repository or another approved spec, stop and report the conflict.
3. Implement only the current approved phase; do not prematurely build every codec or the database.
4. Build canonicalization, exact round trips, Zstandard Core, and a reproducible benchmark before experimental strategies.
5. Never claim a test, benchmark, audit, build, or commit succeeded unless it actually ran and was verified.
6. Enforce `decode(encode(canonical_bytes)) == canonical_bytes`.
7. Do not silently delete repeated meaningful text, references, captions, tables, headings, footnotes, or citations.
8. Keep extraction, OCR correction, canonicalization, tokenization, representation, and compression separately identifiable.
9. Enforce block, allocation, dictionary, grammar, context, and expansion limits before trusting untrusted lengths.
10. Count all serialized costs: payload, dictionaries, grammar rules, activation maps, indexes, headers, and metadata.
11. Evaluate optional stages individually and in dependency-aware combinations; do not prune a prerequisite solely because its standalone result is weak.
12. Pin versions/settings and hash benchmark artifacts. Keep per-document results.
13. Target a 4 GiB RAM machine. Core must not require cloud services, GPUs, or network access.
14. Use Python first. Consider Rust only after profiling shows a material bottleneck.
15. After every five modified files, inspect the diff and create a checkpoint/commit if supported. Report if it is unavailable.
16. Never implement a custom cipher. Encryption requires a vetted AEAD library and reviewed crash-safe nonce/key management.
17. Do not change format/tokenizer/canonicalization semantics silently; version the profile and update test vectors.
18. End each batch with completed files, actual tests run, results, known failures, resource measurements, and the exact next step.

### Required implementation sequence

**Phase 0 — Audit**
- Inspect repository tree, runtime, dependencies, and tests.
- Identify current state and missing pieces.
- Produce a file-by-file plan.
- Do not rewrite code before the audit.

**Phase 1 — Spec/test vectors**
- Resolve canonicalization edge cases, invalid UTF-8 policy, BOM, NFC, LF, whitespace rules.
- Create canonicalization golden tests and tokenizer vector schema.
- Do not invent experimental wire formats.

**Phase 2 — Ingestion**
- Implement TXT and PDF extraction.
- Add optional OCR behind an adapter.
- Keep extraction and cleaning separate.
- Add audit logging for high-confidence changes.
- Preserve uncertain content.

**Phase 3 — Core + harness**
- Implement canonical bytes → Zstandard blocks → decode → exact byte comparison.
- Add framing, lengths, CRC32C, and resource limits.
- Pin versions/settings and build reproducible benchmarks.
- Do not claim improvement before measurement.

**Phase 4 — Corpus/baselines**
- Assemble ≥1 GiB canonical text from ≥2,000 documents and meet language/type targets.
- Split by document/source lineage: 70% training, 10% validation, 20% held-out.
- Freeze/hash the manifest.
- Pin Zstandard -19, Brotli -q11, XZ/LZMA, and 7-Zip PPMd settings.
- Do not train shared dictionaries/grammar on held-out data.

**Phase 5 — Experiments**
- Evaluate dictionaries, Re-Pair, token PPM, numeric/date coding, and record coding.
- Run dependency-aware ablations.
- Count every serialized cost.
- Retain stages only when thresholds pass or a validated profile explicitly justifies them.

**Phase 6 — Selector**
- Select the smallest valid representation within time/memory limits.
- Screen expensive candidates on samples only for early rejection; measure accepted candidates on the full held-out set.
- Keep decoding deterministic and profile-tagged.

**Phase 7 — `.lxz`**
- Define the normative immutable archive layout.
- Add document catalog, blocks, optional indexes, dictionary catalog, and integrity metadata.
- Test corruption, truncation, unknown features, and random block decoding.

**Phase 8 — `.lxdb`**
- Begin only after `.lxz` and codec interfaces stabilize.
- Prefer a proven index/database component.
- Implement recoverable updates, committed-root semantics, compaction, and crash tests.

**Phase 9 — Optional encryption**
- Start only after threat review.
- Use ChaCha20-Poly1305 or AES-256-GCM through a vetted library.
- Define associated data, crash-safe nonce strategy, key rotation, and maximum per-key usage before release.

### Acceptance gates

- 100% byte-for-byte canonical round-trip correctness.
- Resource limits enforced.
- Corrupt input rejected safely.
- No known meaningful-content deletion in curated high-confidence cleaning tests.
- Reproducible benchmark with frozen artifacts.
- All metadata/assets counted.
- Pass: ≥10% smaller than best frozen baseline.
- Partial: 3–10% smaller.
- Fail: <3% smaller.
- Report OCR quality separately from compression efficiency.

### Required report format for each implementation batch

1. Phase and scope.
2. Repository findings.
3. Files to create/modify.
4. Design decisions and reasons.
5. Implementation performed.
6. Tests actually run.
7. Results and measurements.
8. Known issues/open decisions.
9. Files changed and checkpoint status.
10. Exact next step.

Do not jump straight to a complete implementation. Start with Phase 0 unless the user explicitly supplies a current audit and the relevant files. Do not call the project complete until the release gates have been verified.

---

# 14. Current status and next action

**Blueprint:** Complete as a planning document.  
**Normative format:** Draft; serialization and other open decisions must be frozen before claiming conformance.  
**Implementation:** Not asserted by this document.  
**Benchmark:** No compression improvement is claimed.  
**Next action:** Audit the actual repository, freeze canonicalization decisions and test vectors, then implement the Core Zstandard baseline and benchmark harness.
