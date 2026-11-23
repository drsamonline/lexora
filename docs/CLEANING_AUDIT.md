# The cleaning-error audit — how REQ-CAN-007 is measured

> **Status:** Instrument built 2026-11-23 (`benchmarks/cleaning_audit.py`, 15 tests). **No
> cleaning-error rate has been measured on the real corpus.** The number needs a reviewed sample,
> and the reviewers are human — see §5.
> **Related:** [ADR-0004](ADR/ADR-0004-cleaning-error-metric.md) (the metric) · REQ-CAN-007 ·
> [CANONICALIZATION.md](CANONICALIZATION.md) (the rule table) · [CORPUS_POLICY.md](CORPUS_POLICY.md)
> (stratification and lineage)

## 1. What is being measured

ADR-0004 Option B, restated in one line:

$$
\text{error\_rate} = \frac{\text{bytes changed by rules the reviewer marked \emph{incorrect}}}{\text{canonical bytes of the sampled documents}}
$$

Pass requires **point estimate ≤ 1 %** *and* **95 % bootstrap upper bound ≤ 2 %**. The second
condition is not decoration: a small sample can land under 1 % by luck, and the bound is what
refuses to call that a pass.

Three parts of that fraction are defined here rather than left to the reader, because a metric
whose denominator is ambiguous is a metric two people can disagree about while both being right.

| Part | Definition | Why |
|---|---|---|
| **Bytes changed**, per review row | UTF-8 length of the text the rules removed **plus** UTF-8 length of what replaced it | A deletion counts its removed bytes; a replacement counts both sides. Counting only the output would let a rule that deletes a paragraph score as a zero-byte change |
| **Denominator** | Canonical bytes of the **sampled documents** | The claim is about what the archive stores, so the denominator is the stored form — not the raw input, not the whole corpus |
| **Bootstrap unit** | The **document**, not the row | Rows inside a document are correlated: a rule that misfires on a table misfires twenty times in that table. Resampling rows would report an interval narrower than the evidence deserves |

## 2. What a reviewer does

```bash
# 1. draw the sample (seeded; the draw is reproducible and recorded)
python benchmarks/cleaning_audit.py sample --corpus data/corpus --out audit/worksheet.csv

# 2. two reviewers fill the `verdict` column: correct | incorrect
#    the sheet arrives with every verdict blank, deliberately

# 3. score it
python benchmarks/cleaning_audit.py score --worksheet audit/worksheet.csv --out audit/report.json
```

The worksheet has one `document` row per sampled document (it carries the denominator) and one
`change` row per changed span: document, language, character offset, the text before and after,
the bytes changed, and a blank verdict. Reviewing means reading the `before`/`after` columns and
answering one question per row: **was this change right?** The reviewer instructions are in
[templates/CLEANING_REVIEW_WORKSHEET.md](templates/CLEANING_REVIEW_WORKSHEET.md).

Two reviewers, disagreements adjudicated and logged — ADR-0004's requirement, and the reason this
is not something a script can finish.

## 3. What the instrument refuses to do

A score produced from a sample the protocol does not accept is worse than no score, because it
will be quoted. So `score` **exits 2** rather than computing a rate when:

- any language has fewer than **200 documents** (ADR-0004's floor). One thin language refuses the
  whole sample: a fat English sample cannot carry a thin Hindi one;
- any `change` row has no verdict. A blank is not a "correct" — the refusal names the first
  offending row;
- the sheet has no `document` rows (no denominator), or the sampled documents are zero bytes.

The CLI exits 2 on a refusal so a shell pipeline cannot quietly use the output.

## 4. The selftest, and what it is not

```bash
python benchmarks/cleaning_audit.py selftest --out /tmp/audit
```

`selftest` builds a synthetic corpus whose truth is known **by construction** — injected CR, CRLF
and soft hyphens are legitimate to change; ZWJ/ZWNJ, ligatures (CAN-R06 deferred), form feeds
(CAN-R04 not implemented) and trailing spaces (CAN-R03 not implemented) are not — then samples,
adjudicates from that ground truth and scores it.

Result on 2026-11-23, on the shipped v0 rule set: **400 documents (200 en + 200 hi), 9,740 change
rows, 0 incorrect, 0.0 %, PASS.**

**That number is not evidence about the corpus and must never be quoted as REQ-CAN-007 evidence.**
It says the instrument works: a canonicaliser that behaves scores zero, and one that corrupts
protected text does not. The second half is a test, not a hope —
`test_the_instrument_catches_a_rule_that_corrupts_protected_text` monkeypatches an over-eager
canonicaliser (strips ZWJ/ZWNJ, expands ligatures, trims trailing whitespace) and asserts the
report comes back **FAIL**.

## 5. What is still missing before the requirement can be called met

| # | Item | Whose |
|---|---|---|
| 1 | A real corpus at `data/corpus/<language>/` (the harness's own layout) | Owner / build environment — the corpus is not in this repository |
| 2 | The seeded draw over it | A session |
| 3 | Two reviewers, adjudication logged | **Owner** — [PATH_TO_V1](PATH_TO_V1.md) §3 P7.9 |
| 4 | The scored report, attached to a revision | A session, once (3) exists |

Until those exist, REQ-CAN-007 stays **open** and `PATH_TO_V1` P3.5 stays open. What changed on
2026-11-23 is that the missing piece is now a review rather than a tool.

## 6. A finding from building it, recorded because it nearly became a false number

The first version diffed whole documents with `difflib.SequenceMatcher`. On the synthetic sample
it reported a **20.4 % error rate with 300 incorrect rows** — on a canonicaliser that had made no
incorrect change at all. The cause was alignment: repetitive text (which is exactly what a real
corpus is full of — it is this project's whole premise) has many equally valid alignments, and
SequenceMatcher chose one that produced a single enormous deletion swallowing a correct passage.
Every "error" was an artefact of the diff.

The fix is to diff **line by line**, which is the correct grain anyway: the v0 rules are
line-local (CAN-R02 rewrites line endings, CAN-R05 deletes a soft hyphen, CAN-R01 decodes) and
none of them adds or removes a line. If a future rule changes the line count, the instrument
falls back to one whole-document row rather than pretending to precision it does not have.

A measurement tool that invents errors is as dangerous as one that hides them. Both the bug and
the fix are pinned by tests.
