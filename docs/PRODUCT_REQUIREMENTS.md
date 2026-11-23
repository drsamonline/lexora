# LEXORA Product Requirements

> **Status:** Active — reconciled against the code 2026-11-23
> **Owner:** Documentation architect (delegated)
> **Last verified:** 2026-11-23 against `main` @ `20daf22` — every row re-read against the module and
> test that implements it. The previous version said "Not started" for all 35 requirements, six
> weeks after ingestion, canonicalization, the container, the query archive, OCR and three language
> plugins had shipped. That was the requirements register claiming a project that no longer existed.
> **Related:** [Charter](PROJECT_CHARTER.md) · [Blueprint](../LEXORA_Full_Blueprint_Design_Master_Prompt.md) · [REQUIREMENTS_TRACEABILITY.md](REQUIREMENTS_TRACEABILITY.md) (the same rows with Impl/Test/Evidence populated) · [PATH_TO_V1.md](PATH_TO_V1.md) (what is left)

**Priority key:** M = Mandatory, S = Should, N = Nice-to-have.
**Validation key:** every requirement lists a *Verification* method. A status is a claim, so each one
names what backs it: **Met** = a named test or artifact exists; **Partial** = part of the requirement
holds and the unmet half is stated in the status itself; **Open** = nothing verifies it yet. An
implementation gap is a requirement whose status is Open or Partial — not a requirement nobody has
read since the code landed.

## 1. Ingestion & extraction

| ID | Requirement | Priority | Verification | Status |
|---|---|---|---|---|
| REQ-ING-001 | Accept `.txt` inputs with declared or detected encoding; decode without corrupting valid text | M | Unit + golden files | **Met** — declared encoding, else UTF-8/cp1252 sniff, else a refusal naming the file |
| REQ-ING-002 | Extract text layer from digital PDFs preserving page order | M | Integration tests on fixture PDFs | **Met** — text layer extracted with pypdf, page order preserved (ADR-0017) |
| REQ-ING-003 | Optionally OCR scanned PDF pages (Tesseract-class engine); pipeline must run with OCR absent (graceful skip + clear report) | S | CI job with and without OCR installed | **Met** — external Tesseract (ADR-0019); without the binary the document is refused and the message names the env var |
| REQ-ING-004 | Record per-document provenance (source file, extraction mode, engine/version) in archive metadata | M | Schema check + round-trip test | **Met** — mode, engine, engine_version, pages, pages_without_text and text_sha256 stored per document |

## 2. Canonicalization

| ID | Requirement | Priority | Verification | Status |
|---|---|---|---|---|
| REQ-CAN-001 | Canonicalization is deterministic: same input bytes + same canonicalizer version ⇒ identical output bytes | M | Property test (repeat runs, hash compare) | **Met** — pure function of (bytes, canonicalizer version, declared encoding); no locale, clock or randomness |
| REQ-CAN-002 | Output is UTF-8 (no BOM unless versioned to include it); newline policy fixed per canonicalizer version | M | Golden byte vectors | **Met** — UTF-8 out, BOM stripped, LF newlines, fixed per version |
| REQ-CAN-003 | Cleaning is conservative: only transformations listed in an approved rule table may alter bytes; everything else passes through | M | Rule-table review + golden vectors | **Met** — only CAN-R01/R02/R05 may alter bytes; everything else passes through |
| REQ-CAN-004 | Canonicalizer version identifier is recorded in every archive and checked at decode/verify time | M | Format field test | **Met** — `canonicalizer_version` in the 16-byte header field, read back at verify |
| REQ-CAN-005 | Correct handling of Devanagari and Gujarati text (no mangling of combining marks/ZWJ/ZWNJ) | M | Script-specific golden vectors | **Partial** — Devanagari covered; **Gujarati has no plugin and no vectors** |
| REQ-CAN-006 | OCR-error correction applies only above configured confidence thresholds; corrections are logged | S | Log assertion tests | **Open** — nothing is confidence-gated because nothing is corrected; CAN-R09 is proposed, not built |
| REQ-CAN-007 | Cleaning quality ≤ 1% per [ADR-0004](ADR/ADR-0004-cleaning-error-metric.md) (Accepted 2026-10-15): rule-audit sample + invariant checks | M | Sample-review report + invariant test suite | **Instrument built 2026-11-23, rate NOT measured** — `benchmarks/cleaning_audit.py` + `docs/CLEANING_AUDIT.md`; needs the reviewed sample |

## 3. Compression core

| ID | Requirement | Priority | Verification | Status |
|---|---|---|---|---|
| REQ-CMP-001 | For every canonical byte string C: `decode(encode(C)) == C`, byte-exact | M | Round-trip verification on 100% of archived content + property/fuzz tests | **Met** — per-block round trip enforced at pack time, plus fuzz suites over the readers and writers |
| REQ-CMP-002 | Core baseline codec is Zstandard; archives remain decodable with declared codec/profile IDs | M | Decoder conformance test | **Met** — zstd is the default, `codec_id` is level-neutral (ADR-0020), ziptastic optional (ADR-0014/0015) |
| REQ-CMP-003 | Encoding selects codecs/candidates by cost; selection is reproducible given pinned settings | M | Determinism test (re-encode → same bytes) | **Partial** — selection is a pinned preset (ADR-0015), not a cost search; re-encode determinism is asserted |
| REQ-CMP-004 | Cost accounting includes every serialized byte: headers, side tables, dictionaries, grammar stores, block metadata | M | Byte-exact accounting audit vs. actual archive size | **Open** — the accounting is specified, not audited: nothing compares the formula to a real archive's size |
| REQ-CMP-005 | Decoding any single document/block does not require loading the entire archive into memory | M | Memory-profiled decode test | **Met** — `unpack --block N` and `verify --block N` decode one block; index read is per-block |
| REQ-CMP-006 | Unknown codec IDs / unsupported feature flags cause clean refusal with specific error, never partial/garbage output | M | Negative format tests | **Met** — unknown codec id, unknown must-understand flag and a corrupt header each refuse with a specific error and no output file |

## 4. Experimental candidates (gated)

| ID | Requirement | Priority | Verification | Status |
|---|---|---|---|---|
| REQ-EXP-001 | Optional candidates (shared dictionaries, Re-Pair grammar, bounded token PPM, numeric/record coding, template+residual) enter only if they pass frozen-baseline gates under REQ-CMP-004 accounting | M | Benchmark protocol runs | **Partial** — registry and policy landed (ADR-0014/0015/0021); CHCE measured at R6 scale; PPMd withdrawn for corruption |
| REQ-EXP-002 | Learned structures induced only from training split; never from validation/held-out documents | M | Lineage audit of dictionary build inputs | **Open** — zstd dictionary mode ships, but nothing audits that a dictionary was induced from the training split alone |
| REQ-EXP-003 | Every candidate has a documented retirement threshold (re-ablation each benchmark revision) | S | Protocol checklist | **Partial** — the promotion and retirement rule is written and ziptastic's negative results are recorded; no per-revision re-ablation |

## 5. Formats & archives

| ID | Requirement | Priority | Verification | Status |
|---|---|---|---|---|
| REQ-FMT-001 | `.lxz` container defines magic, version, codec/profile IDs, checksums, indexes; layout frozen only via accepted ADR + test vectors | M | Format conformance suite | **Met** — `.lxz` v0 frozen by ADR-0007, with committed test vectors |
| REQ-FMT-002 | Archives carry resource-limit declarations (max block size, max dictionary size) enforced by decoder | M | Limit-violation tests | **Met** — LIM-01/LIM-02 ceilings enforced on read *and* write, not merely declared |
| REQ-FMT-003 | Forward compatibility: unknown optional features flagged "must-understand" vs. "may-ignore" per spec rules | S | Synthetic future-flag archives | **Met** — must-understand bits refused, may-ignore bits tolerated |
| REQ-FMT-004 | `.lxdb` incremental database mode deferred until `.lxz` baseline validated | N | — | **Deferred** — unchanged and deliberate: `.lxdb` waits on gate G2 |

## 6. Benchmarks & evidence

| ID | Requirement | Priority | Verification | Status |
|---|---|---|---|---|
| REQ-BMK-001 | Frozen corpus manifest ≥ 1 GiB covering English/Hindi/Gujarati with train/val/held-out = 70/10/20 split by source lineage | M | Manifest hash + split audit script | **Partial** — 1.054 GiB / 2395 files meets the size condition; **English only**, so the en/hi/gu mix is not met |
| REQ-BMK-002 | Baselines pinned (exact library versions & settings): Zstd-19, Brotli q11, XZ, PPMd — measurement-only roles per ADR-0002/0003 | M | Version capture in results artifact | **Partial** — versions captured in every artifact; zstd-19 and xz9-lzma measured, **brotli absent from the environment and `ppmd-7z` never measured** |
| REQ-BMK-003 | Acceptance: Pass ≥ 10%, Partial ≥ 3%, Fail < 3% total-stored-size reduction vs. best frozen baseline | M | Results report gate | **Open** — no ADR-0001 Pass/Partial/Fail verdict has been issued; R4/R5 are smoke, R6 is protocol-*shaped* |
| REQ-BMK-004 | Report per-document and per-category results, hardware/software environment, repeated-run variance | M | Report schema check | **Partial** — per-document rows, environment capture, 3 reps and per-split reports exist; per-category reporting is not published |

## 7. Resource & runtime

| ID | Requirement | Priority | Verification | Status |
|---|---|---|---|---|
| REQ-RES-001 | Full pipeline (ingest→canonicalize→compress→verify) completes on ~4 GiB-RAM machine for corpora far exceeding RAM via bounded blocks/streaming | M | Peak-RSS measurement on reference machine | **Partial** — core path measured at 84 MiB peak against a 512 MiB budget, streaming flat in document size; **the second machine class has never run** |
| REQ-RES-002 | Python-first prototype; supported interpreter range pinned by ADR | M | CI matrix (once CI exists) | **Met** — Python ≥3.12,<4.0 pinned by ADR-0005; CI runs the suite on every push |
| REQ-RES-003 | Offline operation after dependency installation | S | Network-disabled smoke test | **Open** — no network-disabled smoke test exists; nothing asserts offline operation after install |

## 8. Security & privacy

| ID | Requirement | Priority | Verification | Status |
|---|---|---|---|---|
| REQ-SEC-001 | Decoder validates all lengths/checksums before allocation; hostile/truncated archives cannot cause unbounded memory growth | M | Fuzzing + crafted-archive tests | **Met** — lengths and checksums validated before allocation; LIM ceilings enforced; fuzz suites throw truncations, byte flips and random blobs at seven reader entry points |
| REQ-SEC-002 | No sensitive/clinical corpus content enters shared dictionaries or published artifacts by default | M | Corpus-policy audit | **Met by absence** — no shared dictionary ships, so no corpus content can enter one |
| REQ-SEC-003 | Optional encryption uses an AEAD profile with nonce-uniqueness and key-rotation rules, specified only when in scope | S | Profile spec review + KAT vectors | **Out of current scope** — unchanged; the AEAD profile stays Proposed |
| REQ-SEC-004 | Checksums detect corruption on read; mismatch ⇒ refuse decode with explicit error | M | Bit-flip tests | **Met** — per-block SHA-256 verified on read; a mismatch refuses with a specific error and writes nothing |

## Traceability note

The `Requirement → Design → Implementation → Test → Evidence → Release gate` matrix is maintained in
[REQUIREMENTS_TRACEABILITY.md](REQUIREMENTS_TRACEABILITY.md), and its Implementation and Test columns are
populated as of 2026-11-23. The rule that keeps this honest: **a status may only move forward with the
module and the test named in the same row.** "Not started" is no longer a safe default — it was wrong
for 30 of 35 rows for six weeks, and nothing failed when it was.
