"""ADR-0026 quotes a measurement; this holds the document and the artifact together.

The ADR proposes cost-based selection and quotes the trade a selector would make — 6.59 % smaller
for 6.0× the time — from `benchmarks/results-selector-probe.json`. A number in a decision record
that nothing recomputes is the failure this project has spent a day removing, so the ADR is held to
its artifact the same way ADR-0025 is.

The other half is honesty about a gap: the candidate a selector would most want to compare,
ziptastic (CHCE), could not be measured in this environment. The artifact says so in its own
`not_measured` field, and a test asserts that field is not quietly dropped.
"""

from __future__ import annotations

import json
import pathlib
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "benchmarks"))

import selector_probe  # noqa: E402  (path insertion must come first)

ARTIFACT = REPO / "benchmarks" / "results-selector-probe.json"
ADR = REPO / "docs" / "ADR" / "ADR-0026-cost-based-selection.md"

pytestmark = pytest.mark.skipif(
    not ARTIFACT.exists(), reason="results-selector-probe.json has not been generated"
)


@pytest.fixture(scope="module")
def artifact() -> dict:
    return json.loads(ARTIFACT.read_text(encoding="utf-8"))


def test_the_probe_still_measures_both_levels_on_a_small_input() -> None:
    """A probe that stopped measuring one side would leave the ADR quoting half a trade."""
    result = selector_probe.measure(b"the quick brown fox jumps over the lazy dog\n" * 400, reps=1)
    assert [row["level"] for row in result["rows"]] == list(selector_probe.LEVELS)
    assert all(row["stored_bytes"] > 0 for row in result["rows"])
    assert result["selector_would_pick"] in selector_probe.LEVELS


def test_the_adr_quotes_the_artifact(artifact) -> None:
    text = ADR.read_text(encoding="utf-8")
    assert f"{artifact['percent_smaller']} %" in text, (
        f"ADR-0026 does not quote {artifact['percent_smaller']} % — the artifact moved and the "
        "prose did not"
    )
    assert f"{artifact['time_multiplier']}×" in text
    for row in artifact["rows"]:
        assert f"{row['stored_bytes']:,} B" in text, f"the ADR does not quote {row['level']}'s bytes"


def test_the_unmeasured_candidate_stays_unmeasured(artifact) -> None:
    """ziptastic's absence is evidence too: estimating it would be the claim this repo refuses."""
    assert "ziptastic (CHCE)" in artifact["not_measured"]
    assert "binary absent" in artifact["not_measured"]["ziptastic (CHCE)"]
    assert "not measured" in ADR.read_text(encoding="utf-8")


def test_the_adr_is_proposed_and_says_so() -> None:
    """An implementation does not start from a Proposed ADR — the status is load-bearing."""
    text = ADR.read_text(encoding="utf-8")
    assert "**Status:** **Proposed**" in text
    assert "Nothing here is implemented" in text
