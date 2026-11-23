"""REQ-CAN-007's instrument, tested on what it can be tested on: its own arithmetic and its teeth.

The ≤1 % cleaning-error rate is a *human* measurement — ADR-0004 Option B, two reviewers, an
adjudicated sample. Nothing here produces that number, and no test here may be read as evidence
that the canonicaliser passes. What is tested is the thing that would otherwise be trusted on
faith: that the scoring arithmetic is the one the ADR defines, that the instrument refuses to
score a sample the protocol does not accept, and — the important one — that it *notices* when a
rule corrupts text it was told to leave alone.

That last test exists because of what happened on this instrument's first run: a whole-document
diff over repetitive text aligned ambiguously and reported a 20.4 % error rate on a canonicaliser
that had made no incorrect change at all. A measurement tool that invents errors is as dangerous
as one that hides them, so the alignment bug is pinned by a test as well as by its comment.
"""

from __future__ import annotations

import csv
import pathlib
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "benchmarks"))

import cleaning_audit as audit  # noqa: E402  (path insertion must come first)


def _doc(doc_id: str, canonical_bytes: int, language: str = "en") -> dict:
    return {
        "doc_id": doc_id,
        "language": language,
        "kind": "document",
        "rule_set": "lexcan-0.1",
        "char_offset": "",
        "before": "",
        "after": "",
        "bytes_changed": "",
        "canonical_bytes": str(canonical_bytes),
        "verdict": "",
        "note": "",
    }


def _change(doc_id: str, changed: int, verdict: str, language: str = "en") -> dict:
    return {
        "doc_id": doc_id,
        "language": language,
        "kind": "change",
        "rule_set": "lexcan-0.1",
        "char_offset": "0",
        "before": "\r\n",
        "after": "\n",
        "bytes_changed": str(changed),
        "canonical_bytes": "",
        "verdict": verdict,
        "note": "",
    }


def _full_sample(language: str = "en", docs: int = 200) -> list[dict]:
    return [_doc(f"{language}-{i}", 1000, language) for i in range(docs)]


# --------------------------------------------------------------------------- arithmetic

def test_the_rate_is_incorrect_bytes_over_canonical_bytes() -> None:
    """The ADR's fraction, with both halves defined: bytes changed, over stored canonical bytes."""
    rows = _full_sample(docs=200)                      # 200 × 1000 = 200 000 canonical bytes
    rows.append(_change("en-0", 1000, "incorrect"))    # 0.5 %
    rows.append(_change("en-1", 1000, "correct"))      # ignored — a correct change is not an error
    report = audit.score(rows)
    assert report["error_rate"] == pytest.approx(1000 / 200_000)
    assert report["incorrect_bytes"] == 1000
    assert report["canonical_bytes"] == 200_000
    assert report["verdict"] == "PASS"


def test_the_point_estimate_is_judged_against_one_percent() -> None:
    """≤1 % passes; above it does not. The boundary is the requirement, so it is pinned.

    The error is spread evenly across the sample on purpose: parked in one document it would
    also blow the bootstrap bound (drawing that document twice doubles the rate), and then this
    test would be measuring the second gate while claiming to measure the first.
    """
    at_the_line = _full_sample() + [_change(f"en-{i}", 10, "incorrect") for i in range(200)]
    assert audit.score(at_the_line)["error_rate"] == pytest.approx(0.01)
    assert audit.score(at_the_line)["verdict"] == "PASS"
    over = _full_sample() + [_change(f"en-{i}", 11, "incorrect") for i in range(200)]
    assert audit.score(over)["verdict"] == "FAIL"


def test_the_bootstrap_upper_bound_is_the_stricter_gate() -> None:
    """ADR-0004 also requires a 95 % upper bound ≤2 %; a point estimate under 1 % is not enough.

    Built so the point estimate passes and the bound cannot: one document carries all the error,
    so resampling documents sometimes draws it twice and sometimes not at all.
    """
    rows = _full_sample(docs=200) + [_change("en-0", 1900, "incorrect")]   # 0.95 % point
    report = audit.score(rows, bootstrap=500)
    assert report["error_rate"] == pytest.approx(0.0095)
    assert report["upper_bound_95"] > report["error_rate"], (
        "a cluster bootstrap over documents must widen the interval when the error sits in one "
        "document — if this ever equals the point estimate, the resampling has stopped happening"
    )


def test_the_bootstrap_is_reproducible_from_its_seed() -> None:
    rows = _full_sample() + [_change(f"en-{i}", 100, "incorrect") for i in range(0, 200, 7)]
    a = audit.score(rows, bootstrap=400, seed=7)
    b = audit.score(rows, bootstrap=400, seed=7)
    assert a["upper_bound_95"] == b["upper_bound_95"]
    assert a["bootstrap_seed"] == 7


# --------------------------------------------------------------------------- refusals

def test_a_sample_below_the_adr_floor_is_refused_not_scored() -> None:
    rows = _full_sample(docs=199)
    with pytest.raises(ValueError) as excinfo:
        audit.score(rows)
    assert "200" in str(excinfo.value) and "en" in str(excinfo.value)


def test_one_thin_language_refuses_the_whole_sample() -> None:
    """Stratification is per language: a fat English sample cannot carry a thin Hindi one."""
    rows = _full_sample("en", 200) + _full_sample("hi", 12)
    with pytest.raises(ValueError) as excinfo:
        audit.score(rows)
    assert "hi" in str(excinfo.value)


def test_a_blank_verdict_is_a_refusal_and_names_the_row() -> None:
    rows = _full_sample() + [_change("en-5", 10, "")]
    with pytest.raises(ValueError) as excinfo:
        audit.score(rows)
    message = str(excinfo.value)
    assert "en-5" in message and "verdict" in message


def test_a_sheet_with_no_documents_is_refused() -> None:
    with pytest.raises(ValueError):
        audit.score([_change("en-0", 10, "correct")])


def test_the_cli_exits_2_on_a_refusal(tmp_path) -> None:
    """A refusal is an error code, so a shell pipeline cannot quietly use the output."""
    sheet = tmp_path / "sheet.csv"
    with sheet.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=audit.COLUMNS)
        writer.writeheader()
        writer.writerows(_full_sample(docs=5))
    assert audit.main(["score", "--worksheet", str(sheet)]) == 2


# --------------------------------------------------------------------------- sampling

def _tiny_corpus(root: pathlib.Path, docs: int = 6) -> pathlib.Path:
    for language in ("en", "hi"):
        d = root / language
        d.mkdir(parents=True)
        for i in range(docs):
            (d / f"d{i}.txt").write_text(
                f"line one\r\nsoft\u00adhyphen\r\nDevanagari \u0915\u094d\u200d\u0937\n",
                encoding="utf-8",
            )
    return root


def test_sampling_is_reproducible_from_its_seed(tmp_path) -> None:
    corpus = _tiny_corpus(tmp_path / "corpus")
    a = tmp_path / "a.csv"
    b = tmp_path / "b.csv"
    audit.sample(corpus, a, seed=99, per_language=4)
    audit.sample(corpus, b, seed=99, per_language=4)
    assert a.read_bytes() == b.read_bytes()
    manifest = a.with_suffix(".csv.sample.json")
    assert manifest.exists() and '"seed": 99' in manifest.read_text(encoding="utf-8")


def test_a_different_seed_draws_a_different_sample(tmp_path) -> None:
    corpus = _tiny_corpus(tmp_path / "corpus", docs=12)
    a = tmp_path / "a.csv"
    b = tmp_path / "b.csv"
    audit.sample(corpus, a, seed=1, per_language=4)
    audit.sample(corpus, b, seed=2, per_language=4)
    assert a.read_bytes() != b.read_bytes(), "a seed that does not change the draw is decoration"


def test_the_worksheet_leaves_every_verdict_blank(tmp_path) -> None:
    """The instrument must not pre-fill what a human is supposed to judge."""
    corpus = _tiny_corpus(tmp_path / "corpus")
    out = tmp_path / "w.csv"
    audit.sample(corpus, out, seed=3, per_language=2)
    rows = list(csv.DictReader(out.open(encoding="utf-8")))
    assert rows and all(r["verdict"] == "" for r in rows)
    assert {r["kind"] for r in rows} == {"document", "change"}


def test_changes_are_diffed_line_by_line_not_whole_document(tmp_path) -> None:
    """The alignment bug from the first run, pinned.

    Repetitive text is what a real corpus is full of — that is the project's whole premise — and
    a whole-document diff over it produces one enormous span that swallows correct passages. The
    span here must be the CRLF and the soft hyphen, nothing else.
    """
    before = "same line\r\nsame line\r\nso\u00adft\r\nsame line\r\n"
    after = "same line\nsame line\nsoft\nsame line\n"
    changes = audit._changes(before, after)
    # Each CRLF surfaces as the removed CR (the LF it leaves behind matches), and the soft hyphen
    # as itself. Precise, small, and attributable — which is what a reviewer needs to adjudicate.
    assert [b for _, b, _ in changes] == ["\r", "\r", "\u00ad", "\r", "\r"]
    assert all(len(b) <= 2 for _, b, _ in changes), (
        f"a change span of more than the rule's own footprint is an alignment artefact: {changes}"
    )


# --------------------------------------------------------------------------- teeth

@pytest.fixture(scope="module")
def synthetic(tmp_path_factory):
    """One synthetic sample, shared: it satisfies ADR-0004's floor so nothing bypasses the protocol."""
    out = tmp_path_factory.mktemp("audit")
    corpus = audit.build_synthetic(out, docs=audit.MIN_DOCS_PER_LANGUAGE, seed=20261123)
    worksheet = out / "worksheet.csv"
    audit.sample(corpus, worksheet, seed=20261123, per_language=audit.MIN_DOCS_PER_LANGUAGE)
    audit.adjudicate(worksheet, corpus)
    return corpus, worksheet


def test_the_instrument_sees_the_shipped_rules_as_correct(synthetic) -> None:
    """The v0 rules only touch what they promise: CR/CRLF, soft hyphens, encoding."""
    _, worksheet = synthetic
    report = audit.score(audit._read_sheet(worksheet), bootstrap=300)
    assert report["incorrect_rows"] == 0, (
        f"the shipped canonicaliser changed text it promised to leave alone: "
        f"{report['incorrect_bytes']} bytes over {report['change_rows']} changes"
    )
    assert report["verdict"] == "PASS"


def test_the_instrument_catches_a_rule_that_corrupts_protected_text(synthetic, tmp_path, monkeypatch) -> None:
    """The test that makes the instrument worth having.

    An over-eager canonicaliser — one that also strips ZWJ/ZWNJ, expands ligatures and trims
    trailing whitespace — must be reported as a failure. If this passes when it should fail, the
    metric is decorative.
    """
    corpus, _ = synthetic

    def over_eager(raw: bytes, *, declared_encoding: str | None = None) -> bytes:
        text = raw.decode("utf-8")
        for bad in ("\u200d", "\u200c", "\u000c"):
            text = text.replace(bad, "")
        text = text.replace("\ufb01", "fi").replace("\ufb02", "fl")
        text = "\n".join(line.rstrip(" \t") for line in text.split("\n"))
        return text.replace("\r\n", "\n").replace("\r", "\n").replace("\u00ad", "").encode("utf-8")

    monkeypatch.setattr(audit, "_canonicalize", lambda raw, declared=None: over_eager(raw))

    worksheet = tmp_path / "mutant.csv"
    audit.sample(corpus, worksheet, seed=20261123, per_language=audit.MIN_DOCS_PER_LANGUAGE)
    audit.adjudicate(worksheet, corpus)
    report = audit.score(audit._read_sheet(worksheet), bootstrap=300)

    assert report["incorrect_rows"] > 0, "the instrument did not notice text it was told to protect"
    assert report["error_rate"] > audit.MAX_POINT_ESTIMATE
    assert report["verdict"] == "FAIL", (
        f"a corrupting canonicaliser scored {report['error_rate']:.2%} and passed"
    )
