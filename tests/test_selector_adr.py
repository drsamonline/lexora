"""ADR-0026 quotes a measurement; this holds the document and the artifact together.

The ADR proposes cost-based selection and quotes what a selector would have to choose between —
CHCE at 23.49 % smaller than the shipped default, for ~24× its time. Those numbers come from
`benchmarks/results-selector-probe.json`, and a number in a decision record that nothing recomputes
is the failure this project spent a day removing.

Two lessons from this file's first version are baked into it, because both were real:

* it originally asserted the *levels* it measured, and broke the moment the probe learned to measure
  external binaries. It now asserts the **shape** — every row names its candidate, has bytes and a
  ratio, and the ranking agrees with the artifact — so adding a candidate never turns it red;
* it originally required ziptastic to be recorded as *unmeasured*, which was true only while this
  container had no binary. It now asserts the **mechanism**: point the probe at an empty directory
  and every external candidate must come back under `not_measured` with a reason. A missing tool is
  recorded, never silently dropped.
"""

from __future__ import annotations

import json
import pathlib
import re
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

SAMPLE = b"the quick brown fox jumps over the lazy dog\n" * 400


@pytest.fixture(scope="module")
def artifact() -> dict:
    return json.loads(ARTIFACT.read_text(encoding="utf-8"))


def test_the_probe_still_measures_the_shipped_codec_and_reports_a_pick() -> None:
    result = selector_probe.measure(SAMPLE, reps=1, bin_dir=None)
    names = [row["candidate"] for row in result["rows"]]
    assert any("zstd L9" in n for n in names), "the shipped default must always be measured"
    assert result["selector_would_pick"] in names
    assert result["rows"] == sorted(result["rows"], key=lambda r: r["stored_bytes"]), (
        "rows must be ranked by size, or 'the pick' is whatever happened to be first"
    )


def test_a_tiny_input_does_not_divide_by_zero() -> None:
    """Found in CI, not here: a fast codec rounds to 0.0000 s on a small input, and the time
    multiplier divided by it. Six decimals and a guard, because "it passed locally" is not a
    measurement of the machine that matters."""
    result = selector_probe.measure(b"tiny\n" * 4, reps=1, bin_dir=None)
    assert result["rows"], "a tiny input still produces a row"
    assert result["time_multiplier"] is None or result["time_multiplier"] >= 1


def test_a_missing_binary_is_recorded_not_dropped(tmp_path, monkeypatch) -> None:
    """The mechanism, not the instance: with nothing findable, every external candidate is recorded.

    `shutil.which` is stubbed as well as the bin dir emptied, because the probe falls back to PATH
    by design — and the CI runner *has* `xz`, which made the first version of this test pass here
    and fail there. A test that depends on the machine's installed tools is not testing the probe.
    """
    import shutil

    monkeypatch.setattr(shutil, "which", lambda name, *a, **k: None)
    result = selector_probe.measure(SAMPLE, reps=1, bin_dir=tmp_path)
    assert "chce (ziptastic)" in result["not_measured"]
    assert "xz -9 (CLI)" in result["not_measured"]
    assert all(reason for reason in result["not_measured"].values()), (
        "a candidate recorded as unmeasured must say why, or it reads as 'we forgot'"
    )


def test_every_row_carries_what_makes_it_usable(artifact) -> None:
    assert artifact["rows"], "the artifact has no measurements"
    for row in artifact["rows"]:
        assert row["candidate"] and row["stored_bytes"] > 0
        assert 0 < row["ratio"] < 2, f"ratio {row['ratio']} for {row['candidate']} is not credible"
    assert artifact["tool_versions"], "a number without its tool version is unusable"
    assert artifact["scope"].startswith("ONE FILE"), "the scope label must travel with the numbers"


def test_the_adr_quotes_the_artifact(artifact) -> None:
    text = ADR.read_text(encoding="utf-8")
    for row in artifact["rows"]:
        assert f"{row['stored_bytes']:,} B" in text, (
            f"ADR-0026 does not quote {row['stored_bytes']:,} B for {row['candidate']} — the "
            "artifact moved and the prose did not"
        )
        assert f"{row['ratio']:.4f}" in text, f"ratio for {row['candidate']} is not in the ADR"
    # Sizes are exact, so the percentage is asserted exactly. The *time* multiplier is not: it is
    # wall-clock on a shared container and moved between 21× and 24× across three runs of the same
    # probe. Asserting its exact value would be a flaky test dressed as rigour — so the guard
    # requires that a multiplier is stated, and the artifact is where the measured value lives.
    assert f"{artifact['percent_smaller']} %" in text
    assert re.search(r"\d+(\.\d+)?× its time", text), "the ADR states no time multiplier at all"


def test_the_adr_names_the_tools_and_their_versions(artifact) -> None:
    """The measurement used the estate's binaries, not the pinned ones — say so, with versions."""
    text = ADR.read_text(encoding="utf-8")
    for tool, version in artifact["tool_versions"].items():
        marker = version.split("(")[0].strip().split(":")[0].strip()
        assert marker in text or tool in text, f"the ADR does not name {tool} ({version})"


def test_the_adr_is_proposed_and_says_so() -> None:
    """An implementation does not start from a Proposed ADR — the status is load-bearing."""
    text = ADR.read_text(encoding="utf-8")
    assert "**Status:** **Proposed**" in text
    assert "Nothing here is implemented" in text
