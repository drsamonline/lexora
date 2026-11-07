# Next Session Resume Card

**Last verified state:** 2026-11-07, **Session 71 complete** (CHCE measured on lexora's own corpus class: **−19.75 % vs `xz -9`**, 19/19 files, smoke scope — the release binary works, so no build machine was needed. Gate **541 passed, 1 skipped** with the real binary present). Prior: **Session 70** (audit of lexora against
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

0. **Close gate G2 — it is now environmental, not analytical (Session 74).** R6 ran the
   protocol's *shape* (all three splits, 3 reps, 6 systems, leak audit clean) at 5.9 MB and
   CHCE reproduced at **−18.51 % vs `xz -9`** in every split, byte-stable across reps. What
   remains is scale and hardware, not analysis:
   - the **1.054 GiB** snapshot instead of 5.9 MB (it exists; it is just not in the repo);
   - a **second machine class** (REF-4G) for the reference profile;
   - **`xz` via the CLI** rather than `xz9-lzma`;
   - **owner sign-off**, then a published revision.
   Budget **hours, not minutes**: CHCE runs at 0.39–0.45 MiB/s and the harness compresses
   every file twice per rep (measurement + forked RSS probe). See
   [R6_PROTOCOL_SHAPED_2026-11-07.md](R6_PROTOCOL_SHAPED_2026-11-07.md).
   **When G2 closes**, `.lxdb` becomes buildable against
   [ADR-0013](ADR/ADR-0013-lxdb-layout.md) (Proposed: single file, embedded compressed
   index, append-payload/rewrite-index/commit-by-superblock-flip). Do not start it before —
   the owner declined to override the gate on 2026-11-07.

0. **GUI for the query archive (owner request, Session 73).** The backend is done and
   tested (`lexora db`, 21 tests); the panel is not. Per ADR-0011 the GUI shells out to
   the CLI, so the contract is fixed: search box → `db search --json`, result list,
   preview → `db get`. Needs a Qt-capable machine (PySide6 + `libegl1` for offscreen
   tests) and the same parity-test discipline as the existing panels.

1. **~~Measure CHCE on lexora's own corpus (OQ-16)~~ DONE — Session 71.** The assumed
   blocker (a build machine) was not one: ziptastic ships a prebuilt
   `ziptastic-1.2.0-linux-x86_64`. Measured on 19 Gutenberg texts (19.4 MB canonical,
   every codec on identical canonical bytes, every CHCE frame decoded and compared
   before its size counted): **CHCE −19.75 % vs `xz -9`**, −27.67 % vs zstd-9, smaller
   on **19/19** files; throughput 0.50 MiB/s against zstd-9's 15.9. Full write-up and
   artifact: [CHCE_SMOKE_2026-11-07.md](CHCE_SMOKE_2026-11-07.md),
   `benchmarks/results-chce-smoke.json`.
   **The harness can now run it (Session 72):** `chce-raw` and `lexora-chce` are
   registered systems, so the protocol comparison is one command —
   `--systems lexora,lexora19,zstd19,xz9-lzma,lexora-chce` — with the ziptastic
   binary on `PATH` or `$LEXORA_ZIPTASTIC`. A 5-file harness run already reproduces
   the smoke result (`lexora-chce` −21.55 % vs `lexora19`). Budget hours, not
   minutes: CHCE is ~30× slower than the zstd rows. **Next step is the protocol-scope version of the same comparison** — R4/R5 corpus,
   184 files / 1.054 GiB, three splits, `--systems` including the CHCE path — because
   that is what an ADR-0001 verdict needs. A default-codec flip waits on it; the
   recommendation on the table is to keep zstd default and CHCE as the max-ratio
   preset.
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
