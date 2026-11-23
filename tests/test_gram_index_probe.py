"""The gram-index probe, and the ADR that quotes it, must not drift apart.

`benchmarks/results-gram-index.json` exists because the number it replaces did not: the "5× the
stored payload" figure in the CHANGELOG came from a generator nobody committed, so it could not
be re-derived, checked or corrected — and when it was finally measured properly it turned out to
be one point on a curve that runs from 3.15× to 13.29× (ADR-0025).

Two guards here. The probe still runs and still writes the shape the ADR reads; and the ADR's
table still matches the committed artifact, so a re-run that moves a number cannot leave the
document claiming the old one. The second is the one that matters: prose is not recomputed.
"""

from __future__ import annotations

import json
import pathlib
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "benchmarks"))

import gram_index_probe as probe  # noqa: E402  (path insertion must come first)

ARTIFACT = REPO / "benchmarks" / "results-gram-index.json"
ADR = REPO / "docs" / "ADR" / "ADR-0025-gram-index-layout.md"

pytestmark = pytest.mark.skipif(
    not ARTIFACT.exists(), reason="results-gram-index.json has not been generated"
)


@pytest.fixture(scope="module")
def artifact() -> dict:
    return json.loads(ARTIFACT.read_text(encoding="utf-8"))


def test_the_probe_still_runs_and_measures_every_layout(monkeypatch, tmp_path) -> None:
    """A probe that stopped measuring a layout would leave the ADR quoting a column nobody checks."""
    monkeypatch.setattr(probe, "SHAPES", (("tiny", 2, 200),))
    out = tmp_path / "r.json"
    assert probe.main(["--out", str(out)]) == 0
    doc = json.loads(out.read_text(encoding="utf-8"))
    shape = doc["shapes"]["tiny"]
    assert set(shape["layouts"]) == set(probe.VARIANTS)
    for name, data in shape["layouts"].items():
        assert data["rows"] > 0, f"{name} measured nothing"
        assert data["bytes"] > 0, f"{name} has no pages — dbstat did not report"


def test_the_artifact_covers_the_shapes_the_adr_tabulates(artifact) -> None:
    assert set(artifact["shapes"]) == {label for label, _, _ in probe.SHAPES}
    for label, shape in artifact["shapes"].items():
        assert shape["gram_doc_pairs"] > 0, label
        assert shape["stored_payload_bytes_zstd9"] > 0, label


def test_the_adr_quotes_the_artifact_and_not_the_other_way_round(artifact) -> None:
    """Every ratio the ADR prints must be the one in the JSON, to two decimal places.

    This is the claims gate for ADR-0025. Re-running the probe and committing a new artifact
    without re-reading the ADR turns this red, which is the entire point.
    """
    text = ADR.read_text(encoding="utf-8")
    for label, shape in artifact["shapes"].items():
        current = shape["current_vs_stored_payload"]
        best = shape["best_packing_vs_stored_payload"]
        assert f"{current:.2f}×" in text, (
            f"ADR-0025 does not quote {current:.2f}× (the current layout's cost for {label}); "
            "the artifact moved and the prose did not"
        )
        assert f"{best:.2f}×" in text, (
            f"ADR-0025 does not quote {best:.2f}× (the best packing for {label})"
        )
    # the three headline costs, spelled out rather than derived, because they are the finding
    assert "3.15×" in text and "6.61×" in text and "13.29×" in text


def test_the_hashing_finding_is_still_true(artifact) -> None:
    """The ADR's central claim: packing the gram saves a sixth at best. If that ever inverts,
    the decision to keep the layout needs re-reading, not the test."""
    for label, shape in artifact["shapes"].items():
        layouts = shape["layouts"]
        assert layouts["c_hash4"]["vs_current"] < 1.5, (
            f"hashing bought {layouts['c_hash4']['vs_current']}× on {label} — more than the ADR "
            "says, so ADR-0025's decision needs re-reading"
        )


def test_the_single_document_case_still_disfavours_the_inverted_index(artifact) -> None:
    """ADR-0025's second finding: postings lose on one document, win on a shared vocabulary."""
    single = artifact["shapes"]["one-document-20k"]["layouts"]
    assert single["d_posting32"]["vs_current"] < 1.0, (
        "the inverted index no longer loses on a single document — re-read ADR-0025 before "
        "quoting the 0.76× row"
    )
    corpus = artifact["shapes"]["small-corpus-50x4k"]["layouts"]
    assert corpus["d_posting32"]["vs_current"] > 1.5
