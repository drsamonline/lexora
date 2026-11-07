# Next Session Resume Card

**Last verified state:** 2026-11-07, **Session 70 complete** (audit of lexora against
ziptastic + the second codec landed: a codec registry, `--codec ziptastic` (CHCE,
ADR-0014), four defects fixed, suite **540 passed, 2 skipped**). Full findings:
[AUDIT_2026-11-07.md](AUDIT_2026-11-07.md). Prior: **Session 69** (CI collection
failure fixed — `pytest` does not put the CWD on `sys.path`; landing page brought up
to date).

**Current phase:** P1 complete; P2 (benchmark harness & first numbers) in progress.
The load-bearing open items are unchanged in kind but one is now cheaper: the
protocol-scope benchmark run, and a write-scoped credential (the brokered GitHub
credential is read-only, so every change arrives as a patch).

**Working-tree state:** Session-70 work is uncommitted on the fetched tree; **push
is still blocked** by the read-only credential.

## Read first
- [ ] `docs/AUDIT_2026-11-07.md` — the four findings, what was fixed, and the
      correction to ziptastic's −11.83 % headline (it is a 10-file subset; the two
      largest files are unmeasured there)
- [ ] `docs/ADR/ADR-0014-ziptastic-codec.md` — why zstd stays the default, and the
      determinism caveat (per pinned binary, not per format)
- [ ] `src/lexora/codec_registry.py` — the one place a codec is named now
- [ ] `docs/ZIPTASTIC_NOTES.md` — updated: the codec seam is built, the negative
      results that must not be re-proposed, and the CAN-R01 objective conflict
- [ ] `docs/ADR/ADR-0012-default-encode-level.md` + `tests/test_level_default.py` —
      the drift class that produced finding F2

## Tasks in order

1. **Measure CHCE on lexora's own corpus (OQ-16 — the default-codec decision).**
   The seam exists; the measurement does not. Needs a machine with **cmake + ninja
   + g++** and the 23 vendored submodules (none exist in the agent sandbox, so the
   adapter's ratio is untested here by necessity — its contract is covered by a stub).
   ```bash
   # on a build machine, once ziptastic is built and on PATH:
   lexora doctor                                   # should report the ziptastic row
   lexora pack --in corpus_sample.txt --out a.lxz --codec ziptastic
   lexora pack --in corpus_sample.txt --out b.lxz                  # zstd-9, the default
   lexora inspect --in a.lxz ; lexora verify --in a.lxz
   ```
   Then the same on the R5 corpus at the protocol block size, and compare against
   `xz -9` and zstd-19 per split. **Do not move the default on the Silesia number
   alone** — that corpus is not this corpus, and its largest English-text file
   (`webster`, a dictionary) is unmeasured even there.
2. **Decide finding F1 — the `codec_id` string.** `CODEC_ID_ZSTD` is `zstd-raw-l19`
   while `DEFAULT_LEVEL` is 9, so every default archive names a level it did not
   use and a level-9 archive is indistinguishable from a level-19 one. It is a
   frozen format field (ADR-0007), so this needs an ADR, not an edit. Cheapest at
   the v0→v1 boundary, where a rename costs nothing. Options are in the audit.
3. **`.lxdb` byte layout (ADR-0013).** Gated, not blocked: the corpus half of G2 is
   met (2395 files / 1.054 GiB). What remains is a protocol-scope benchmark run plus
   owner sign-off. Note the new codec changes the calculus: an `.lxdb` of CHCE
   members is a different size/speed point than one of zstd members.
4. **GUI process separation (ADR-0011 implementation).** Needs a Qt-capable machine:
   replace `AppService` bodies with subprocess calls, re-aim the parity test at argv
   construction, add Qt-free tests against the real CLI. Start from the now-consistent
   `run_compress`/`run_pack` defaults (F2 was fixed in Session 70).
5. **Documentation reconciliation (finding F5).** `SESSION_LOG.md` ends at Session 69
   (2026-10-29) but `DECISIONS.md` records OQ-6/OQ-15 resolved 2026-10-30 and
   `STATUS.md` a 2026-11-03 verification — that work has no session record. Also:
   `IMPLEMENTATION_MATRIX.md` has no row for the codec registry or `--codec`, and
   `docs/index.md` should link the audit.

## Environment notes (this container)
- `pip install "zstandard>=0.23,<0.26" pytest` then `PYTHONPATH=src python3 -m pytest -q`.
- GUI tests skip without PySide6 (+`libegl1` for offscreen Qt); the first skip in the
  gate is that. The second is the real-ziptastic round trip.
- **No cmake, ninja, g++ or zig here** — ziptastic cannot be built in the agent
  sandbox, which is why the codec adapter ships with a stub-based contract test and
  a `skipif` for the real binary.
- This box is 2 vCPU / 2 GiB and noisy: **wall-clock and throughput numbers from it
  are not quotable.**
