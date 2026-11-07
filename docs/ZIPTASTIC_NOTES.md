# What LEXORA can take from ziptastic

A note for anyone working on lexora. ziptastic is the sibling project
(`github.com/drsamonline/ziptastic`): a lossless archiver in C++20 with the same
central idea as lexora — **transform the data, prove byte-exact recovery, store a
recipe**. Where lexora canonicalises *text*, ziptastic parses *containers*.

Both repos are written by the same sole author, so code may be moved between them
freely. This note records what is worth taking and, more usefully, what has already
been measured and lost.

---

## 1. The biggest win available to lexora: replace the codec

> **Update 2026-11-07 — this is now built.** The backend is selectable:
> `lexora pack --codec ziptastic` (ADR-0014). The container dispatches on
> `codec_id` through `src/lexora/codec_registry.py`, and the adapter is
> `src/lexora/ziptastic_core.py`. What is **not** done is the measurement on
> lexora's own corpus, so zstd remains the default. See
> [AUDIT_2026-11-07.md](AUDIT_2026-11-07.md).

lexora's Phase-1 backend is **zstd** — at **level 9** since ADR-0012 (this note
said 19, which was true until Session 53).

Measured on Silesia, **10 files, 119,259,397 bytes** — a *subset* of the 12-file
211,938,580-byte corpus. `webster` (41 MiB, a dictionary) and `mozilla` (51 MiB,
binary) are **unmeasured** in ziptastic: both exceed its 300 s per-command limit at
every block size tried.

| codec | total |
|---|---|
| `xz -9` | 27,035,452 |
| **ziptastic** | **23,838,035 (−11.83%)** |

The win is concentrated in text and XML, which is lexora's corpus class: `reymont`
−22.2 %, `mr` −18.2 %, `osdb` −17.6 %, `xml` −17.3 %, `dickens` −16.8 %,
`nci` −16.7 %. It is **not** general: `samba` −0.64 % and `sao` −0.001 % are binary
files where CHCE is level with `xz`. Read the headline as "a large text win", not
as "a large win".

ziptastic beats `xz -9` on every file it measured, and `xz -9` beats zstd-19 on most
text. So **lexora's ratio is currently leaving a double-digit percentage on the
table**, and the fix is not a lexora change — it is swapping the backend.

The container was already codec-agnostic in *layout* (`codec_id[16]` in the
header) but not in code: zstd was hard-coded in five places — the id written, the
reader's accept-list, and three literal frame-magic checks. That is now a registry
(`src/lexora/codec_registry.py`), and `ziptastic_core.py` sits beside
`zstd_core.py` shelling out to the binary, exactly as this note proposed.

Caveat worth knowing before you start: ziptastic encodes at roughly **0.3–0.5 MB/s**
at `-9`. It is a ratio codec, not a speed codec. lexora should keep zstd for its
fast path and offer ziptastic for a max-ratio path.

---

## 2. Text transforms: mostly measured and lost

This is the part that will save the most time. Every one of these was implemented in
ziptastic and measured on real corpora, and every one **lost**:

| idea | measured result |
|---|---|
| word-dictionary stage | **−0.38%** on English, **+0.93%** on Polish |
| delta preprocessing (1/2/4-byte) | +1.7% to +91% **worse** |
| byte-shuffle / bitshuffle | +4.8% to +27.6% **worse** |
| LZP before BWT | −0.02% to +1.9% (a wash) |
| Gorilla leading-zero float XOR | worse than plain 8-byte XOR |
| Rice coding | +10% to +20% worse than zigzag+varint |

**The rule that explains all of them:**

> A transform pays only if it removes redundancy the backend cannot already capture.
> Otherwise it adds cost and removes nothing.

A BWT/PPMd-class backend already models byte and symbol statistics extremely well.
Text-level canonicalisation mostly removes redundancy the coder was already
collecting — which is why the word dictionary, the most promising of these on paper,
came out at −0.38%.

---

## 3. A specific warning about CAN-R01

**Encoding normalisation to UTF-8 makes compression worse**, and lexora's CAN-R01 does
exactly that.

Converting CP1251, Latin-1 or Shift-JIS text to UTF-8 roughly **doubles the byte
count** for non-ASCII content. That is correct for lexora's stated purpose — canonical
text, comparable across sources — but it is a loss for any byte-level compressor
downstream, because the coder must now encode twice as many bytes carrying the same
information.

This is not a reason to change CAN-R01. It is a reason to be clear that canonical
UTF-8 and minimum compressed size are **different objectives**, and that lexora has
chosen the first. Worth stating in the docs so nobody benchmarks the two against each
other and concludes the canonicaliser is "hurting compression" — it is doing its job.

If a max-ratio mode is ever wanted, the honest design is: canonicalise for the
semantic guarantees, but compress the **original bytes** with a recipe for the
canonicalisation, the way ziptastic stores a recipe for its container transforms.

---

## 4. Things ziptastic does that lexora already does better

Not everything runs one way. These are lexora's ideas, and ziptastic should be
copying them:

- **Validate-before-allocate.** lexora checks the header hash, the limits, the sum of
  declared sizes and the offsets against file size *before* decoding anything.
  ziptastic has had desync bugs whose symptom was a `std::bad_alloc` from a corrupt
  size field. lexora's ordering is the correct defence.
- **Per-block integrity with an index and trailer.** lexora verifies SHA-256 per
  block, so a corrupt block costs that block, not the archive. ziptastic has a single
  CRC-32 over the whole original, so one bad byte loses everything.
- **Stated determinism.** "Same input + level ⇒ byte-identical archive" is a promise
  lexora makes and tests. ziptastic makes no such claim and should.

---

## 5. Shared discipline worth keeping identical in both repos

1. **Verify before use.** ziptastic has turned five would-be corruptions into
   declined transforms by checking `decode(encode(x)) == x` on that exact input
   before committing. lexora's `pack` already does the equivalent.
2. **Check the transform actually engaged.** Reading the flags byte rather than
   trusting a smaller output has caught four real bugs in ziptastic. The analogue in
   lexora is checking the applied-rule list in the metadata rather than assuming.
3. **Measure, don't predict.** Three predictors in ziptastic were wrong, every time
   in the direction that costs ratio. Where a structural fact about the input exists,
   use it instead of an estimate.
4. **Record failures as failures.** Half of ziptastic's `docs/` is negative results,
   and those are the documents that save the most time.

---

## 6. Where to look in ziptastic

| file | why |
|---|---|
| `docs/BENCHMARKS.md` | every measured result, including the failures |
| `docs/AI_REVIEWS_SYNTHESIS.md` | twelve external reviews, what survived scrutiny |
| `docs/ALGORITHMS_FROM_PAPERS.md` | ranked techniques plus the "measured and closed" table |
| `docs/NUMERIC_RESIDUAL_EXPERIMENT.md` | what a text/number transform actually pays |
| `docs/SESSION_HANDOFF.md` | current state and next steps |

The single most useful habit to copy: **ziptastic writes down what failed and why**,
with the number that killed it. That is what stops the same idea being re-proposed
every few months.
