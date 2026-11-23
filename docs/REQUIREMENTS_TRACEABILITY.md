# LEXORA Requirements Traceability

> **Status:** Active — Implementation, Test and Evidence populated 2026-11-23 against `main` @ `20daf22`
> **Owner:** Documentation architect (delegated)
> **Related:** [PRODUCT_REQUIREMENTS.md](PRODUCT_REQUIREMENTS.md) · [IMPLEMENTATION_MATRIX.md](IMPLEMENTATION_MATRIX.md) · [ACCEPTANCE_CRITERIA.md](ACCEPTANCE_CRITERIA.md) · [TEST_STRATEGY.md](TEST_STRATEGY.md)

## Purpose

For every mandatory requirement, trace the chain
`Requirement → Design → Implementation → Test → Evidence → Release gate`
and expose any missing link as a gap. Optional (S/N) requirements may use lighter verification but still need a named method.

## How to read the chain columns

- **Req** — ID from PRODUCT_REQUIREMENTS.md.
- **Design** — normative section that defines behavior.
- **Impl** — module/file with passing code, or `—` where the requirement is genuinely unbuilt.
- **Test** — the test file that exercises it, or the review procedure where the verification is human.
- **Evidence** — committed artifact (log, report, fixture hash).
- **Gate** — release/phase gate the requirement blocks.

## Chain table

| Req | Design | Impl | Test | Evidence | Gate | Gap |
|---|---|---|---|---|---|---|
| REQ-ING-001 | SPEC §1.1–1.2 | `src/lexora/ingest.py` (`_read_text`) | `tests/test_ingest.py` | `ingest._read_text` refuses rather than mangles | P1 exit | — |
| REQ-ING-002 | SPEC §1.3 | `src/lexora/ingest.py` (`_read_pdf`) | `tests/test_ingest.py` (page order asserted) | ADR-0017; 15 ingest tests | P3 exit | — |
| REQ-ING-003 | OCR_PIPELINE | `src/lexora/ocr_core.py` | `tests/test_ocr.py` (15 tests, incl. the graceful skip) | verified on a real 99-page scan | P3 exit | OCR **language** scope is open (PATH_TO_V1 P7.4) |
| REQ-ING-004 | SPEC §1.4 | `src/lexora/ingest.py`, `src/lexora/catalog.py` | `tests/test_ingest.py`, `tests/test_catalog.py` | fields filterable in `lexora db` | P1 exit | — |
| REQ-CAN-001 | CANONICALIZATION §Determinism | `src/lexora/canonicalize.py` | `tests/test_canonicalize_invariants.py` | `canonicalize_with_meta` records the rule set | P1 exit | — |
| REQ-CAN-002 | CANONICALIZATION §Output form | `src/lexora/canonicalize.py` | `tests/test_canon_vectors.py` + `tests/vectors/` | 9 golden byte vectors, byte-exact | P0 exit (freeze) + P1 | — |
| REQ-CAN-003 | CANONICALIZATION rule table | `src/lexora/canonicalize.py` (`APPLIED_RULES_V0`) | `tests/test_canonicalize_invariants.py` (whitelist invariants) | rule table in `docs/CANONICALIZATION.md` | P1 exit | the table is not frozen for 0.x (CHANGELOG versioning note) |
| REQ-CAN-004 | SPEC §2.4 | `src/lexora/container.py` | `tests/test_container_lxz.py` | ADR-0023 made the field carry plugin provenance (`hi-1`, `zh-1`) | P1 exit | — |
| REQ-CAN-005 | CANONICALIZATION §Scripts | `packages/lexora-lang-hi`, `packages/lexora-lang-gu` | `tests/test_language_hindi_plugin.py`, `tests/test_language_gujarati_plugin.py` | script-specific vectors; ZWJ/ZWNJ preserved; NFC ordering asserted | P1 exit | — |
| REQ-CAN-006 | CAN-R09 / OCR_PIPELINE | — | — | `docs/OCR_PIPELINE.md` §corrections | P3 exit | the requirement's premise (correction) does not exist yet |
| REQ-CAN-007 | ADR-0004 (Accepted) | `benchmarks/cleaning_audit.py` | `tests/test_cleaning_audit.py` (15 tests) | ADR-0004 Option B | P3 exit | two human reviewers (PATH_TO_V1 P7.9) |
| REQ-CMP-001 | SPEC §3.1 | `src/lexora/container.py`, `src/lexora/zstd_core.py` | `tests/test_container_lxz.py`, `tests/test_reader_fuzz.py`, `tests/test_writer_fuzz.py` | a mismatch exits 6 and writes nothing | **P1 hard gate** | — |
| REQ-CMP-002 | SPEC §4.1–4.6 | `src/lexora/zstd_core.py`, `src/lexora/codec_registry.py` | `tests/test_codec_real_text.py`, `tests/test_ziptastic_codec.py` | decoder refuses an unknown id | P1 exit | — |
| REQ-CMP-003 | COST_MODEL §Selection | `src/lexora/cli.py` (level/preset mapping) | `tests/test_level_default.py`, `tests/test_container_lxz.py` | `docs/COST_MODEL.md` | P4 exit | pinned preset ships; ADR-0026 (Proposed) designs the cost search — a whole-archive trial, because per-block needs a v1 format |
| REQ-CMP-004 | COST_MODEL formula | `benchmarks/cost_audit.py` | `tests/test_cost_audit.py` (11 tests) | accounting closes exactly on real archives; mutations detected | P2/P4 exit | v0 has no side tables/dictionary, so those terms are structurally zero; per-candidate cost is REQ-CMP-003 |
| REQ-CMP-005 | SPEC §4.4 / RESOURCE_LIMITS | `src/lexora/container.py` (`read_index`) | `tests/test_container_lxz.py` | `benchmarks/results-rss-core.json`, `results-rss-index.json` | P1 exit | — |
| REQ-CMP-006 | SPEC §4.5 | `src/lexora/container.py` | `tests/test_format_flags.py` (7 tests), `tests/test_container_lxz.py` | exit 7 for format refusals, documented in CLI_REFERENCE | P1 exit | — |
| REQ-EXP-001 | SPEC §5.2 (ADR-0001) | `src/lexora/codec_registry.py`, `src/lexora/cli.py` | `tests/test_codec_real_text.py`, `tests/test_ziptastic_codec.py` | `benchmarks/results-r6-*.json`, `docs/ECOSYSTEM_REVIEW_2026-11-08.md` | P4 per-candidate | no candidate has passed ADR-0001 at protocol scope |
| REQ-EXP-002 | CORPUS_POLICY §Splits | `benchmarks/lineage_audit.py` | `tests/test_dictionary_lineage.py` (10 tests) | refuses a non-train input; leak probe is the backstop | P2 exit | probe cannot see a dictionary that was contaminated but kept no verbatim run — measured, so the input record is the control |
| REQ-EXP-003 | BENCHMARK_PROTOCOL §Ablation | — | — | ADR-0001, `docs/ZIPTASTIC_NOTES.md` | each benchmark rev | re-ablation per benchmark revision not run |
| REQ-FMT-001 | FORMAT_LXZ (PROPOSED) | `src/lexora/container.py` | `tests/test_container_lxz.py`, `tests/vectors/lxz_format/` | ADR-0007 (Accepted) | P1-T3 freeze | — |
| REQ-FMT-002 | FORMAT_LXZ §Limits | `src/lexora/container.py` (`DEFAULT_MAX_BLOCK_*`) | `tests/test_container_lxz.py` (limit violations) | `docs/RESOURCE_LIMITS.md` | P1 exit | — |
| REQ-FMT-003 | FORMAT_LXZ §Compat | `src/lexora/container.py` | `tests/test_format_flags.py` | `docs/FORMAT_LXZ.md` | P1 exit | — |
| REQ-FMT-004 | FORMAT_LXDB (proposal) | — | — | ADR-0013 (Proposed) | P5 entry | gated on P0 by owner decision |
| REQ-BMK-001 | CORPUS_POLICY | `benchmarks/corpus.py` | `tests/test_corpus_catalog.py`, `tests/test_corpus_reconcile.py` | `benchmarks/MANIFEST.json` (lineage splits) | P2 exit | no hi/gu coverage (owner directive 2026-10-16) |
| REQ-BMK-002 | SPEC §4.6 (ADR-0002/0003) | `benchmarks/harness.py` | `tests/test_harness_systems.py` | `benchmarks/env.json`, `benchmarks/results-r*.json` | P2 exit | OQ-18 open (PATH_TO_V1 P7.3) |
| REQ-BMK-003 | SPEC §5.2 | — | — | `docs/BENCHMARK_RESULTS.md` | M2 verdict | gate G2: full-corpus run, second machine class, sign-off (P0) |
| REQ-BMK-004 | BENCHMARK_PROTOCOL §Reporting | `benchmarks/harness.py` | `tests/test_harness_systems.py` | `benchmarks/results-r4-*.json`, `results-r6-*.json` | P2 exit | per-category table not published |
| REQ-RES-001 | RESOURCE_LIMITS / PERFORMANCE_BUDGET | `src/lexora/canonicalize.py` (streaming), `src/lexora/container.py` | `tests/test_pack_stream.py`, `tests/test_unpack_stream.py` | `docs/P1_EVIDENCE_DRAFT.md`, `benchmarks/results-rss-*.json` | P1 exit + each phase | REF-4G never tested (PATH_TO_V1 P4.3) |
| REQ-RES-002 | DECISIONS OQ-7 | `pyproject.toml` | CI workflow + `tests/test_readme_claims.py` (version guards) | ADR-0005 | before P1 code | — |
| REQ-RES-003 | INSTALLATION / BUILD_GUIDE | every verb, offline | `tests/test_offline.py` (4 tests, incl. the guard control) | sockets removed before import; byte-identical round trip offline | P7 release | — |
| REQ-SEC-001 | SPEC §4 / THREAT_MODEL (Batch D) | `src/lexora/container.py` | `tests/test_reader_fuzz.py`, `tests/test_writer_fuzz.py`, `tests/test_interruption.py` | `docs/THREAT_MODEL.md` | P6 exit | — |
| REQ-SEC-002 | CORPUS_POLICY §Privacy | — | — | `docs/PRIVACY_AND_DATA_HANDLING.md`, `docs/CORPUS_POLICY.md` | P2 exit | revisit the day a dictionary ships; the audit the requirement names is moot until then |
| REQ-SEC-003 | ENCRYPTION_PROFILE (Batch D) | — | — | `docs/ENCRYPTION_PROFILE.md` | P6 (if scoped) | scope confirmation is the owner's (ADR-0009) |
| REQ-SEC-004 | FORMAT_LXZ §Checksums | `src/lexora/container.py` | `tests/test_container_lxz.py` (bit flips), `tests/test_reader_fuzz.py` | exit 7 refusal, documented | P1 exit | — |

## Gap summary (mandatory requirements without any verification means realized)

This section used to say every implementation link was a gap "because the repository contains no code".
"
        "That was true in Phase 0 and stopped being true months later. What is actually open now, in the
"
        "order it matters:
"
        "
"
        "- **REQ-CMP-004** (cost accounting audited against a real archive) and **REQ-CMP-003** (selection by
"
        "  cost rather than by pinned preset) — the cost model is a document, not a running check.
"
        "- **REQ-BMK-003** (an ADR-0001 verdict) — blocked on gate G2, i.e. the full-corpus protocol run (P0).
"
        "- **REQ-CAN-007** (the ≤1 % cleaning rate) — instrument built, sample unreviewed (P7.9).
"
        "- **REQ-EXP-002** (dictionary lineage audit) and **REQ-RES-003** (offline smoke test) — named by the
"
        "  requirement, not yet written.
"
        ""
        "- **REQ-RES-001** — measured on one machine class; REF-4G has never run (P4.3).
"
        "
"
        "Everything else in the table has a module and a test named against it.

## Maintenance rule

Any PR/commit touching implementation MUST update the matching row(s) here and in IMPLEMENTATION_MATRIX.md in the same session; a chain cell may only move forward with a committed evidence link.
