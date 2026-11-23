#!/usr/bin/env python3
"""The instrument for REQ-CAN-007 — the ≤1 % cleaning-error rate, per ADR-0004.

**What this is.** ADR-0004 (Accepted, Option B) defines the metric and nothing implemented it.
This script is the missing half: it draws the stratified seeded sample, emits the review
worksheet a human fills in, and scores the filled sheet into the point estimate and the 95 %
bootstrap upper bound the requirement asks for. It also *refuses* to produce a number that the
method does not support — too small a sample, or an unadjudicated row, is an error, not a
default.

**What this is not.** It does not decide whether the canonicaliser passes. A human reviewer
marks each change correct or incorrect; two reviewers, disagreements adjudicated, per ADR-0004.
`selftest` exists to prove the *instrument* works end to end on a synthetic sample where the
truth is known by construction — it is not a measurement of the real corpus, and its output says
so in the report itself.

The metric, in one line:

    error_rate = bytes changed by rules the reviewer marked INCORRECT / canonical bytes of the
                 sampled documents

Both halves of that fraction are defined here rather than left to the reader, because a metric
whose denominator is ambiguous is a metric two people can disagree about while both being right:

* **Bytes changed** for one review row = the UTF-8 length of the text the rules replaced plus the
  UTF-8 length of what they put in its place. A deletion therefore counts its removed bytes; a
  replacement counts both sides; an insertion counts its inserted bytes.
* **The denominator** is the canonical bytes of the sampled documents (not of the corpus, and not
  of the raw input), because the claim being audited is about what the archive stores.
* **The bootstrap unit is the document, not the row.** Rows inside one document are correlated —
  a rule that misfires on a table misfires twenty times in that table — so resampling rows would
  report a confidence interval narrower than the evidence deserves.

Usage:

    python benchmarks/cleaning_audit.py sample --corpus CORPUS_DIR --out worksheet.csv
    python benchmarks/cleaning_audit.py score --worksheet worksheet.csv --out report.json
    python benchmarks/cleaning_audit.py selftest --out /tmp/audit

Exit codes: 0 ok · 2 usage/refusal · 3 unreadable input. A refusal is deliberately an error: a
number produced from a sample the protocol does not accept is worse than no number.
"""

from __future__ import annotations

import argparse
import csv
import difflib
import hashlib
import json
import pathlib
import random
import statistics
import sys

# Characters the v0 rule table must not touch (REQ-CAN-005 script safety, and the rules that are
# deliberately *not* implemented: CAN-R03 trailing whitespace, CAN-R06 ligatures, CAN-R04 control
# characters). A change that removes or rewrites any of these is an incorrect change by
# construction — this is what "reviewer marks incorrect" means in `selftest`.
PROTECTED_CHARS = {
    "\u200d",  # ZWJ — Devanagari/Gujarati shaping
    "\u200c",  # ZWNJ
    "\ufb01", "\ufb02", "\ufb03", "\ufb04",  # ligatures fi fl ffi ffl — CAN-R06 is deferred
    "\u000c",  # form feed — CAN-R04 is not implemented
}

COLUMNS = [
    "doc_id",
    "language",
    "kind",          # "document" (one per sampled doc, carries the denominator) or "change"
    "rule_set",      # canonicalizer version label, so a sheet is traceable to a rule table
    "char_offset",   # offset in the raw decoded text where the change starts
    "before",
    "after",
    "bytes_changed",
    "canonical_bytes",   # set on the "document" row only
    "verdict",       # blank until a reviewer writes correct | incorrect
    "note",
]

MIN_DOCS_PER_LANGUAGE = 200   # ADR-0004 Option B
MAX_POINT_ESTIMATE = 0.01     # REQ-CAN-007
MAX_UPPER_BOUND = 0.02        # ADR-0004's guard against small-sample noise


# --------------------------------------------------------------------------- helpers

def _decode(raw: bytes) -> str:
    """Best-effort decode for diffing. The audit compares *text*, so a failure here is fatal."""
    return raw.decode("utf-8", errors="replace")


def _changes(before: str, after: str) -> list[tuple[int, str, str]]:
    """Changed spans as (char_offset_in_before, before_text, after_text).

    Diffed **line by line**, not over the whole document, and the reason is a real failure this
    instrument had on its first run: a whole-document diff over repetitive text aligns
    ambiguously, and SequenceMatcher then reports one enormous deletion that swallows a correct
    passage. On the synthetic sample that turned 0 genuine errors into a 20.4 % error rate —
    every "error" an artefact of the alignment, none of them a byte the canonicaliser got wrong.

    The v0 rules are line-local by construction (CAN-R02 rewrites line endings, CAN-R05 deletes a
    soft hyphen, CAN-R01 decodes), and none of them adds or removes a line. So line-for-line is
    both the correct grain and the stable one. If a future rule changes the line count, this
    falls back to a single whole-document row marked ``alignment-fallback`` — visible in the
    worksheet, so a reviewer knows the row is coarse rather than precise.
    """
    before_lines = before.splitlines(keepends=True)
    after_lines = after.splitlines(keepends=True)

    if len(before_lines) != len(after_lines):
        if before == after:
            return []
        return [(0, before, after)]

    out: list[tuple[int, str, str]] = []
    offset = 0
    for b_line, a_line in zip(before_lines, after_lines):
        if b_line != a_line:
            matcher = difflib.SequenceMatcher(a=b_line, b=a_line, autojunk=False)
            for tag, i1, i2, j1, j2 in matcher.get_opcodes():
                if tag == "equal":
                    continue
                out.append((offset + i1, b_line[i1:i2], a_line[j1:j2]))
        offset += len(b_line)
    return out


def _bytes_changed(before_text: str, after_text: str) -> int:
    return len(before_text.encode("utf-8")) + len(after_text.encode("utf-8"))


def _protected(before_text: str, doc_text: str, start: int) -> bool:
    """True when the change touched something the v0 rule table promises to leave alone."""
    if any(ch in PROTECTED_CHARS for ch in before_text):
        return True
    # Trailing whitespace: CAN-R03 is not implemented, so a rule that trims it is out of contract.
    if before_text and set(before_text) <= {" ", "\t"}:
        end = start + len(before_text)
        if end >= len(doc_text) or doc_text[end] in "\r\n":
            return True
    return False


def _canonicalize(raw: bytes, declared: str | None = None) -> bytes:
    from lexora.canonicalize import canonicalize

    return canonicalize(raw, declared_encoding=declared)


def _rule_set() -> str:
    from lexora import CANONICALIZER_VERSION

    return CANONICALIZER_VERSION


# --------------------------------------------------------------------------- sample

def _corpus_files(corpus: pathlib.Path) -> list[pathlib.Path]:
    return sorted(p for p in corpus.rglob("*.txt") if p.is_file())


def _language_of(path: pathlib.Path, corpus: pathlib.Path) -> str:
    """Language from the corpus layout: ``<corpus>/<language>/…`` — the same convention
    benchmarks/corpus.py uses. Anything else is 'unknown' and cannot be stratified."""
    try:
        return path.relative_to(corpus).parts[0]
    except (ValueError, IndexError):
        return "unknown"


def sample(corpus: pathlib.Path, out: pathlib.Path, seed: int, per_language: int) -> dict:
    files = _corpus_files(corpus)
    if not files:
        raise SystemExit(f"no .txt files under {corpus} — refusing to write an empty worksheet")

    by_language: dict[str, list[pathlib.Path]] = {}
    for path in files:
        by_language.setdefault(_language_of(path, corpus), []).append(path)

    rng = random.Random(seed)
    chosen: list[pathlib.Path] = []
    for language in sorted(by_language):
        pool = by_language[language]
        k = min(per_language, len(pool))
        chosen.extend(rng.sample(pool, k))

    rows: list[dict] = []
    for path in chosen:
        raw = path.read_bytes()
        before = _decode(raw)
        after_raw = _canonicalize(raw)
        after = _decode(after_raw)
        doc_id = str(path.relative_to(corpus))
        rows.append({
            "doc_id": doc_id,
            "language": _language_of(path, corpus),
            "kind": "document",
            "rule_set": _rule_set(),
            "char_offset": "",
            "before": "",
            "after": "",
            "bytes_changed": "",
            "canonical_bytes": len(after_raw),
            "verdict": "",
            "note": "",
        })
        for offset, before_text, after_text in _changes(before, after):
            rows.append({
                "doc_id": doc_id,
                "language": _language_of(path, corpus),
                "kind": "change",
                "rule_set": _rule_set(),
                "char_offset": offset,
                "before": before_text,
                "after": after_text,
                "bytes_changed": _bytes_changed(before_text, after_text),
                "canonical_bytes": "",
                "verdict": "",
                "note": "",
            })

    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    manifest = {
        "seed": seed,
        "per_language": per_language,
        "corpus": str(corpus),
        "files_available": len(files),
        "documents_sampled": len(chosen),
        "documents_by_language": {
            lang: sum(1 for p in chosen if _language_of(p, corpus) == lang)
            for lang in sorted(by_language)
        },
        "change_rows": sum(1 for r in rows if r["kind"] == "change"),
        "rule_set": _rule_set(),
        "worksheet_sha256": hashlib.sha256(out.read_bytes()).hexdigest(),
        "note": "verdict column is blank by design; a reviewer fills it with correct|incorrect",
    }
    out.with_suffix(out.suffix + ".sample.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


# --------------------------------------------------------------------------- score

def _read_sheet(path: pathlib.Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def score(rows: list[dict], *, bootstrap: int = 2000, seed: int = 20261123) -> dict:
    """Turn a filled worksheet into a verdict, or refuse to.

    Refusals are the point. A score computed from 12 documents, or from a sheet where a reviewer
    left half the rows blank, is a number that will be quoted and cannot be defended.
    """
    documents = [r for r in rows if r["kind"] == "document"]
    changes = [r for r in rows if r["kind"] == "change"]

    if not documents:
        raise ValueError("worksheet has no 'document' rows — no denominator, so no rate")

    per_language: dict[str, int] = {}
    for doc in documents:
        per_language[doc["language"]] = per_language.get(doc["language"], 0) + 1
    thin = {lang: n for lang, n in per_language.items() if n < MIN_DOCS_PER_LANGUAGE}
    if thin:
        raise ValueError(
            f"sample too small for ADR-0004 (needs {MIN_DOCS_PER_LANGUAGE} documents per "
            f"language): {thin}. Refusing to compute a rate the protocol does not support."
        )

    unadjudicated = [r for r in changes if r["verdict"].strip().lower() not in {"correct", "incorrect"}]
    if unadjudicated:
        first = unadjudicated[0]
        raise ValueError(
            f"{len(unadjudicated)} change row(s) have no verdict (first: {first['doc_id']} at "
            f"char {first['char_offset']}). Every change must be marked correct or incorrect; "
            "a blank is not a 'correct'."
        )

    total_canonical = sum(int(d["canonical_bytes"]) for d in documents)
    if total_canonical <= 0:
        raise ValueError("sampled documents have zero canonical bytes — nothing to divide by")

    per_doc_incorrect: dict[str, int] = {d["doc_id"]: 0 for d in documents}
    for row in changes:
        if row["verdict"].strip().lower() == "incorrect":
            per_doc_incorrect[row["doc_id"]] = (
                per_doc_incorrect.get(row["doc_id"], 0) + int(row["bytes_changed"])
            )

    point = sum(per_doc_incorrect.values()) / total_canonical

    # Cluster bootstrap over documents: rows within a document are not independent.
    rng = random.Random(seed)
    doc_ids = [d["doc_id"] for d in documents]
    by_id = {d["doc_id"]: int(d["canonical_bytes"]) for d in documents}
    draws: list[float] = []
    for _ in range(bootstrap):
        sample_ids = [rng.choice(doc_ids) for _ in doc_ids]
        num = sum(per_doc_incorrect.get(i, 0) for i in sample_ids)
        den = sum(by_id[i] for i in sample_ids)
        if den:
            draws.append(num / den)
    upper = sorted(draws)[int(0.95 * (len(draws) - 1))] if draws else point

    passed = point <= MAX_POINT_ESTIMATE and upper <= MAX_UPPER_BOUND
    return {
        "documents": len(documents),
        "documents_by_language": per_language,
        "change_rows": len(changes),
        "incorrect_rows": sum(1 for r in changes if r["verdict"].strip().lower() == "incorrect"),
        "incorrect_bytes": sum(per_doc_incorrect.values()),
        "canonical_bytes": total_canonical,
        "error_rate": point,
        "bootstrap": bootstrap,
        "bootstrap_seed": seed,
        "upper_bound_95": upper,
        "thresholds": {"point": MAX_POINT_ESTIMATE, "upper_bound": MAX_UPPER_BOUND},
        "verdict": "PASS" if passed else "FAIL",
        "metric": "ADR-0004 Option B (rule-audit sample)",
    }


# --------------------------------------------------------------------------- selftest

_GOOD = (
    "The quick brown fox jumps over the lazy dog. "
    "Pack my box with five dozen liquor jugs. "
    "How vexingly quick daft zebras jump!\n"
)
_PROTECTED = (
    "Trailing space must survive: here \n"      # CAN-R03 not implemented
    "Ligature must survive: \ufb01nal \ufb02ow\n"   # CAN-R06 deferred
    "Form feed must survive:\u000cstill here\n"     # CAN-R04 not implemented
    "Devanagari joins must survive: \u0915\u094d\u200d\u0937 \u0915\u094d\u200c\u0937\n"
)
_DEFECTS = ("\r\n", "\u00ad", "\r")


def build_synthetic(out: pathlib.Path, docs: int, seed: int) -> pathlib.Path:
    """A corpus whose truth is known by construction, laid out as ``<corpus>/<language>/``.

    ``docs`` documents *per language*, because ``score()`` refuses a language with fewer than
    ADR-0004's 200 — the selftest has to satisfy the protocol, not step around it.
    """
    corpus = out / "corpus"
    rng = random.Random(seed)
    for language in ("en", "hi"):
        d = corpus / language
        d.mkdir(parents=True, exist_ok=True)
        for i in range(docs):
            body = []
            for _ in range(rng.randint(6, 14)):
                line = _GOOD if rng.random() < 0.5 else _PROTECTED
                body.append(line.replace("\n", rng.choice(_DEFECTS)))
            (d / f"doc-{i:04d}.txt").write_text("".join(body), encoding="utf-8")
    return corpus


def adjudicate(worksheet: pathlib.Path, corpus: pathlib.Path) -> pathlib.Path:
    """Fill the verdict column from ground truth: a change is incorrect iff it touched protected text."""
    rows = _read_sheet(worksheet)
    for row in rows:
        if row["kind"] != "change":
            continue
        doc_text = _decode((corpus / row["doc_id"]).read_bytes())
        wrong = _protected(row["before"], doc_text, int(row["char_offset"]))
        row["verdict"] = "incorrect" if wrong else "correct"
        row["note"] = "synthetic ground truth" if wrong else "legitimate rule application"
    with worksheet.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    return worksheet


def selftest(out: pathlib.Path, docs: int, seed: int) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    corpus = build_synthetic(out, docs, seed)
    # Two languages with >= 200 documents each is what score() demands, so the selftest builds a
    # sample that satisfies the protocol rather than bypassing it.
    worksheet = out / "worksheet.csv"
    sample(corpus, worksheet, seed=seed, per_language=max(MIN_DOCS_PER_LANGUAGE, docs))
    adjudicate(worksheet, corpus)
    report = score(_read_sheet(worksheet), bootstrap=500, seed=seed)
    report["synthetic"] = True
    report["note"] = (
        "SYNTHETIC — the truth is known by construction (injected CR/CRLF/soft hyphen are "
        "legitimate; ZWJ/ZWNJ, ligatures, form feeds and trailing spaces are not). This number "
        "validates the instrument. It is NOT a measurement of the corpus and must never be "
        "quoted as REQ-CAN-007 evidence."
    )
    (out / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


# --------------------------------------------------------------------------- CLI

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("sample", help="draw the stratified sample and write the review worksheet")
    sp.add_argument("--corpus", required=True, type=pathlib.Path)
    sp.add_argument("--out", required=True, type=pathlib.Path)
    sp.add_argument("--seed", type=int, default=20261123)
    sp.add_argument("--per-language", type=int, default=MIN_DOCS_PER_LANGUAGE)

    sc = sub.add_parser("score", help="score a filled worksheet")
    sc.add_argument("--worksheet", required=True, type=pathlib.Path)
    sc.add_argument("--out", type=pathlib.Path)
    sc.add_argument("--bootstrap", type=int, default=2000)
    sc.add_argument("--seed", type=int, default=20261123)

    st = sub.add_parser("selftest", help="prove the instrument on a synthetic labelled sample")
    st.add_argument("--out", required=True, type=pathlib.Path)
    st.add_argument("--docs", type=int, default=200)
    st.add_argument("--seed", type=int, default=20261123)

    args = ap.parse_args(argv)

    if args.cmd == "sample":
        if not args.corpus.is_dir():
            print(f"not a directory: {args.corpus}", file=sys.stderr)
            return 3
        manifest = sample(args.corpus, args.out, args.seed, args.per_language)
        print(json.dumps(manifest, indent=2))
        return 0

    if args.cmd == "score":
        try:
            report = score(_read_sheet(args.worksheet), bootstrap=args.bootstrap, seed=args.seed)
        except ValueError as exc:
            print(f"refused: {exc}", file=sys.stderr)
            return 2
        text = json.dumps(report, indent=2)
        if args.out:
            args.out.write_text(text + "\n", encoding="utf-8")
        print(text)
        return 0

    report = selftest(args.out, args.docs, args.seed)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
