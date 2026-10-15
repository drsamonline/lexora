# Runbook: Recovery

> **Status:** Draft (procedure for the designed system; `.lxdb` recovery is explicitly **deferred — not designed**, so this runbook covers archive/pipeline-state recovery only — verified 2026-10-15)
> **Owner:** Documentation architect (delegated)
> **Related:** [../FORMAT_LXDB.md](../FORMAT_LXDB.md) (DEFERRED) · [../ERROR_HANDLING.md](../ERROR_HANDLING.md) recovery semantics · [CORRUPTION_TRIAGE.md](CORRUPTION_TRIAGE.md) · [../SECURITY_ARCHITECTURE.md](../SECURITY_ARCHITECTURE.md)

## When to use

Crash/power loss/interrupted process during: encode run, benchmark harness, dictionary training, manifest update, or (future) `.lxdb` commit. Goal: reach a state where you know *exactly* what is trustworthy and what must be rebuilt.

## Principles

1. **Atomic-write contract**: completed artifacts appear via temp+fsync+rename ([../ERROR_HANDLING.md](../ERROR_HANDLING.md)). Anything still named `*.tmp`/in-flight is *not* an artifact — never promote it manually.
2. **Rebuild beats repair** whenever source originals exist. LEXORA archives are derived data; originals are the asset ([../PRIVACY_AND_DATA_HANDLING.md](../PRIVACY_AND_DATA_HANDLING.md)).
3. **Manifest is the ledger.** If the manifest doesn't record an artifact as committed, treat the artifact as uncommitted regardless of its presence on disk.

## Steps by interrupted stage

| Interrupted during | Likely leftovers | Action |
|---|---|---|
| Ingest/canonicalization | Partial canonical cache | Discard partials (they lack a completion record); re-run stage — determinism makes redo safe and cheap relative to risk |
| Encode (archive write) | `*.tmp` archive | Delete tmp; prior archive (if any) untouched by rename semantics; verify old archive digest vs manifest before trusting it |
| Verify step | Archive written but verification incomplete | Treat archive as NOT committed; re-run verify or rebuild; a passing-looking but unverified archive is forbidden output |
| Dictionary training | Partial grammar/dict sidecar | Discard; retrain from pinned train split; never "resume" a half-trained representation whose ID/hash lineage is unclear |
| Manifest/catalog update | Two manifests (old/new) or torn write | Keep the newest *complete, parseable* one; if both parse, prefer the one whose recorded digests match on-disk reality; document which was chosen |
| Benchmark run | Partial result files | Never merge partial results into BENCHMARK_RESULTS.md; discard and rerun per [BENCHMARK_RUNBOOK.md](BENCHMARK_RUNBOOK.md) |
| `.lxdb` operations | n/a today | **Out of scope** — database mode deferred; when designed, blueprint §7.4 requires previous-or-complete committed state only, with crash tests at block-append, index update, root commit, compaction |

## Post-recovery checklist

- [ ] Digest sweep: every artifact listed in the chosen manifest recomputes to its recorded hash.
- [ ] Orphan sweep: files on disk not in manifest are quarantined (moved aside, not deleted, until owner decides).
- [ ] Round-trip spot check on recovered archives (decode → hash compare against manifest's canonical-bytes hash).
- [ ] Recovery event logged in [../SESSION_LOG.md](../SESSION_LOG.md) with cause, choices made, and anything lost.

## Do NOT

- Rename a `.tmp` file into place to "save time."
- Edit checksums/indexes by hand to make a damaged archive open (that path belongs to [CORRUPTION_TRIAGE.md](CORRUPTION_TRIAGE.md) external byte-surgery on copies, with untrusted labeling).
- Reuse a dictionary ID after rebuilding it with different content — IDs never silently change meaning.
