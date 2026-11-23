# Cleaning-review worksheet — reviewer instructions

> **Used with:** [CLEANING_AUDIT.md](../CLEANING_AUDIT.md) · [ADR-0004](../ADR/ADR-0004-cleaning-error-metric.md)
> **Template added** 2026-11-23, as ADR-0004's implementation note asked.

## What you are looking at

`benchmarks/cleaning_audit.py sample` writes a CSV. Two kinds of row:

| `kind` | What it is | What you do |
|---|---|---|
| `document` | One per sampled document. Carries `canonical_bytes`, the denominator | Nothing. Leave `verdict` blank |
| `change` | One per span the canonicaliser changed: `char_offset`, `before`, `after`, `bytes_changed` | **Fill `verdict` with `correct` or `incorrect`** |

## The one question

For each `change` row: **was this change right?**

Ask it against the rule table in [CANONICALIZATION.md](../CANONICALIZATION.md), not against what
you would have done. The v0 rules are:

| Rule | Allowed to | So this is **correct** |
|---|---|---|
| CAN-R01 | decode declared/detected charset to UTF-8 | mojibake repaired, or bytes re-encoded once |
| CAN-R02 | rewrite CRLF / CR to LF | a line ending changed, and only that |
| CAN-R05 | delete U+00AD soft hyphen | a soft hyphen removed, nothing else |

Everything else is **incorrect**, because the rules do not claim it:

- trailing whitespace trimmed (CAN-R03 is *not* implemented — tables need it first);
- ligatures expanded (CAN-R06 deferred);
- control characters or form feeds removed (CAN-R04 not implemented);
- ZWJ / ZWNJ or any combining mark moved, dropped or reordered (REQ-CAN-005 script safety);
- digits, spellings, punctuation or spacing "normalised" in any way;
- a change whose span is larger than the rule's own footprint — a `before` of half a paragraph for
  a line-ending rule is a corruption, whatever the `after` looks like.

## How to write a verdict

- `correct` — the rule did what the table says, on text it was allowed to touch.
- `incorrect` — anything else. **Use the `note` column** for one short phrase saying why
  ("trimmed trailing space", "ligature expanded", "ZWJ dropped"). A verdict without a reason
  cannot be adjudicated, and the adjudication is what makes the number defensible.
- Leave it **blank** only if you genuinely cannot tell — then say so in `note`. The scorer will
  refuse the whole sheet while a blank remains, which is the point: a blank is not a "correct".

## Two reviewers

ADR-0004 requires two independent passes and logged adjudication.

1. Reviewer A fills `verdict` and `note` on a copy: `worksheet.reviewer-a.csv`.
2. Reviewer B does the same **without seeing A's copy**: `worksheet.reviewer-b.csv`.
3. A third pass adjudicates only the rows where A and B disagree, and records the outcome in
   `worksheet.adjudicated.csv` plus a short note of what was settled and why.
4. Score the adjudicated sheet. The two earlier sheets are kept: they are the evidence that the
   review was independent.

## What not to do

- **Do not** fix the text. The worksheet records what the rules did; editing `before`/`after`
  destroys the measurement.
- **Do not** score a partial sheet. The instrument refuses one, and a rate from half a sample will
  be quoted as if it came from the whole.
- **Do not** re-draw the sample to get a better number. The seed is recorded in
  `worksheet.csv.sample.json` next to the sheet; a different draw is a different measurement and
  must be reported as one.
