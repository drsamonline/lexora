# LEXORA Product Requirements

> **Status:** Draft — derived from the approved blueprint; pending owner approval
> **Owner:** Unassigned
> **Last verified:** 2026-10-15 (commit `816f58f`)
> **Related:** [Charter](PROJECT_CHARTER.md) · [Blueprint](../LEXORA_Full_Blueprint_Design_Master_Prompt.md) · future [REQUIREMENTS_TRACEABILITY.md] (Batch C)

**Priority key:** M = Mandatory, S = Should, N = Nice-to-have.
**Validation key:** every requirement lists a *Verification* method; requirements whose tests do not yet exist are implementation gaps by definition (no code exists yet).

## 1. Ingestion & extraction

| ID | Requirement | Priority | Verification | Status |
|---|---|---|---|---|
| REQ-ING-001 | Accept `.txt` inputs with declared or detected encoding; decode without corrupting valid text | M | Unit + golden files | Not started |
| REQ-ING-002 | Extract text layer from digital PDFs preserving page order | M | Integration tests on fixture PDFs | Not started |
| REQ-ING-003 | Optionally OCR scanned PDF pages (Tesseract-class engine); pipeline must run with OCR absent (graceful skip + clear report) | S | CI job with and without OCR installed | Not started |
| REQ-ING-004 | Record per-document provenance (source file, extraction mode, engine/version) in archive metadata | M | Schema check + round-trip test | Not started |

## 2. Canonicalization

| ID | Requirement | Priority | Verification | Status |
|---|---|---|---|---|
| REQ-CAN-001 | Canonicalization is deterministic: same input bytes + same canonicalizer version ⇒ identical output bytes | M | Property test (repeat runs, hash compare) | Not started |
| REQ-CAN-002 | Output is UTF-8 (no BOM unless versioned to include it); newline policy fixed per canonicalizer version | M | Golden byte vectors | Not started |
| REQ-CAN-003 | Cleaning is conservative: only transformations listed in an approved rule table may alter bytes; everything else passes through | M | Rule-table review + golden vectors | Not started |
| REQ-CAN-004 | Canonicalizer version identifier is recorded in every archive and checked at decode/verify time | M | Format field test | Not started |
| REQ-CAN-005 | Correct handling of Devanagari and Gujarati text (no mangling of combining marks/ZWJ/ZWNJ) | M | Script-specific golden vectors | Not started |
| REQ-CAN-006 | OCR-error correction applies only above configured confidence thresholds; corrections are logged | S | Log assertion tests | Not started |
| REQ-CAN-007 | Cleaning quality ≤ 1% per [ADR-0004](ADR/ADR-0004-cleaning-error-metric.md) (Accepted 2026-10-15): rule-audit sample + invariant checks | M | Sample-review report + invariant test suite | Not started (metric defined; awaiting P3 run) |

## 3. Compression core

| ID | Requirement | Priority | Verification | Status |
|---|---|---|---|---|
| REQ-CMP-001 | For every canonical byte string C: `decode(encode(C)) == C`, byte-exact | M | Round-trip verification on 100% of archived content + property/fuzz tests | Not started |
| REQ-CMP-002 | Core baseline codec is Zstandard; archives remain decodable with declared codec/profile IDs | M | Decoder conformance test | Not started |
| REQ-CMP-003 | Encoding selects codecs/candidates by cost; selection is reproducible given pinned settings | M | Determinism test (re-encode → same bytes) | Not started |
| REQ-CMP-004 | Cost accounting includes every serialized byte: headers, side tables, dictionaries, grammar stores, block metadata | M | Byte-exact accounting audit vs. actual archive size | Not started |
| REQ-CMP-005 | Decoding any single document/block does not require loading the entire archive into memory | M | Memory-profiled decode test | Not started |
| REQ-CMP-006 | Unknown codec IDs / unsupported feature flags cause clean refusal with specific error, never partial/garbage output | M | Negative format tests | Not started |

## 4. Experimental candidates (gated)

| ID | Requirement | Priority | Verification | Status |
|---|---|---|---|---|
| REQ-EXP-001 | Optional candidates (shared dictionaries, Re-Pair grammar, bounded token PPM, numeric/record coding, template+residual) enter only if they pass frozen-baseline gates under REQ-CMP-004 accounting | M | Benchmark protocol runs | Not started |
| REQ-EXP-002 | Learned structures induced only from training split; never from validation/held-out documents | M | Lineage audit of dictionary build inputs | Not started |
| REQ-EXP-003 | Every candidate has a documented retirement threshold (re-ablation each benchmark revision) | S | Protocol checklist | Not started |

## 5. Formats & archives

| ID | Requirement | Priority | Verification | Status |
|---|---|---|---|---|
| REQ-FMT-001 | `.lxz` container defines magic, version, codec/profile IDs, checksums, indexes; layout frozen only via accepted ADR + test vectors | M | Format conformance suite | Proposed — layout NOT defined |
| REQ-FMT-002 | Archives carry resource-limit declarations (max block size, max dictionary size) enforced by decoder | M | Limit-violation tests | Not started |
| REQ-FMT-003 | Forward compatibility: unknown optional features flagged "must-understand" vs. "may-ignore" per spec rules | S | Synthetic future-flag archives | Not started |
| REQ-FMT-004 | `.lxdb` incremental database mode deferred until `.lxz` baseline validated | N | — | Deferred |

## 6. Benchmarks & evidence

| ID | Requirement | Priority | Verification | Status |
|---|---|---|---|---|
| REQ-BMK-001 | Frozen corpus manifest ≥ 1 GiB covering English/Hindi/Gujarati with train/val/held-out = 70/10/20 split by source lineage | M | Manifest hash + split audit script | Not started |
| REQ-BMK-002 | Baselines pinned (exact library versions & settings): Zstd-19, Brotli q11, XZ, PPMd — measurement-only roles per ADR-0002/0003 | M | Version capture in results artifact | Not started (roles resolved 2026-10-15) |
| REQ-BMK-003 | Acceptance: Pass ≥ 10%, Partial ≥ 3%, Fail < 3% total-stored-size reduction vs. best frozen baseline | M | Results report gate | Not started |
| REQ-BMK-004 | Report per-document and per-category results, hardware/software environment, repeated-run variance | M | Report schema check | Not started |

## 7. Resource & runtime

| ID | Requirement | Priority | Verification | Status |
|---|---|---|---|---|
| REQ-RES-001 | Full pipeline (ingest→canonicalize→compress→verify) completes on ~4 GiB-RAM machine for corpora far exceeding RAM via bounded blocks/streaming | M | Peak-RSS measurement on reference machine | Not started |
| REQ-RES-002 | Python-first prototype; supported interpreter range pinned by ADR | M | CI matrix (once CI exists) | Open decision |
| REQ-RES-003 | Offline operation after dependency installation | S | Network-disabled smoke test | Not started |

## 8. Security & privacy

| ID | Requirement | Priority | Verification | Status |
|---|---|---|---|---|
| REQ-SEC-001 | Decoder validates all lengths/checksums before allocation; hostile/truncated archives cannot cause unbounded memory growth | M | Fuzzing + crafted-archive tests | Not started |
| REQ-SEC-002 | No sensitive/clinical corpus content enters shared dictionaries or published artifacts by default | M | Corpus-policy audit | Not started |
| REQ-SEC-003 | Optional encryption uses an AEAD profile with nonce-uniqueness and key-rotation rules, specified only when in scope | S | Profile spec review + KAT vectors | Out of current scope |
| REQ-SEC-004 | Checksums detect corruption on read; mismatch ⇒ refuse decode with explicit error | M | Bit-flip tests | Not started |

## Traceability note

A full `Requirement → Design → Implementation → Test → Evidence → Release gate` matrix will be maintained in `REQUIREMENTS_TRACEABILITY.md` (Batch C). Until code exists, **every requirement above is "Not started"** except where marked Blocked/Open decision.
