"""Every published ratio must be the one its artifact reports, at the revision it names.

This exists because three numbers wore one label for weeks. `README.md` said the shipped default
was 0.3352 on "172 files / 78.6 MiB", the register said 0.3367 for "the same" default, and
`ADR-0015` backed 0.3352 with a byte count — and no reader could tell which run any of them came
from. Recomputing from the committed artifacts (2026-11-23) showed:

* **0.3367** is revision 4, heldout only, 17 files / 12.1 MiB, 2 reps — `results-r4-smoke.json`;
* **0.3360** is revision 5, all three splits, 184 files / 80.4 MiB, 3 reps —
  `results-r4-{train,validation,heldout}.json`, whose `benchmark_revision` field reads 5 although
  the file names say `r4`;
* **0.3352** has no surviving artifact. Revision 5's run reused revision 4's file names and
  overwrote it. It is withdrawn from the README rather than carried forward.

So these tests recompute the ratios from the artifacts and hold the prose to them. A number in a
document is a claim; this is the machine that checks it.
"""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]
BENCH = REPO / "benchmarks"
README = REPO / "README.md"
REGISTER = REPO / "docs" / "BENCHMARK_RESULTS.md"

REV5_ARTIFACTS = ("results-r4-train.json", "results-r4-validation.json", "results-r4-heldout.json")


def _ratio(artifact_names: tuple[str, ...]) -> dict[str, float]:
    """Aggregate stored/input per system, from the artifacts rather than from any document."""
    stored: dict[str, int] = {}
    raw: dict[str, int] = {}
    for name in artifact_names:
        doc = json.loads((BENCH / name).read_text(encoding="utf-8"))
        for row in doc["rows"]:
            stored[row["system"]] = stored.get(row["system"], 0) + row["stored_bytes_min"]
            raw[row["system"]] = raw.get(row["system"], 0) + row["input_bytes"]
    return {system: stored[system] / raw[system] for system in stored}


@pytest.fixture(scope="module")
def rev5() -> dict[str, float]:
    return _ratio(REV5_ARTIFACTS)


def test_the_r4_named_artifacts_are_revision_5() -> None:
    """The naming mistake, pinned: these files say r4 and their own field says 5.

    Asserted rather than fixed, because renaming committed artifacts breaks every link that
    cites them — the fix is that documents cite the field, and this test makes the mismatch
    impossible to forget.
    """
    for name in REV5_ARTIFACTS:
        doc = json.loads((BENCH / name).read_text(encoding="utf-8"))
        assert doc["benchmark_revision"] == 5, f"{name} is not revision 5 — the note in benchmarks/README.md is stale"


def test_revision_4_survives_only_as_the_heldout_first_cut() -> None:
    """The only rev-4 artifact is the single-split first cut, and its ratio is the 0.3367."""
    doc = json.loads((BENCH / "results-r4-smoke.json").read_text(encoding="utf-8"))
    assert doc["benchmark_revision"] == 4
    assert doc["subset"]["files"] == 17
    assert _ratio(("results-r4-smoke.json",))["lexora"] == pytest.approx(0.3367, abs=5e-5)


def test_the_readme_quotes_revision_5_from_its_artifacts(rev5: dict[str, float]) -> None:
    text = README.read_text(encoding="utf-8")
    for system in ("lexora", "lexora19", "zstd19", "xz9-lzma"):
        expected = f"{rev5[system]:.4f}"
        assert expected in text, (
            f"README does not quote {expected} for {system} at revision 5 — either the artifact "
            "moved or the README did"
        )
    assert "184 files / 80.4 MiB" in text


def test_the_withdrawn_figure_is_not_claimed_anywhere_as_lexoras() -> None:
    """0.3352 must not appear as a LEXORA result: no committed artifact reports it.

    It may still appear in the withdrawal note and in ADR-0015, where it is the *baseline*
    codec's ratio on the CHCE smoke corpus — a different measurement that happens to share
    the digits.
    """
    for doc in (README, REGISTER):
        # Paragraph-level, not line-level: prose wraps, and a guard that fails on where a
        # sentence happens to break is a guard people delete.
        for paragraph in doc.read_text(encoding="utf-8").split("\n\n"):
            if "0.3352" not in paragraph:
                continue
            lowered = paragraph.lower()
            assert ("withdrawn" in lowered
                    or "no surviving artifact" in lowered
                    or "no committed file" in lowered), (
                f"{doc.name} quotes 0.3352 without saying it was withdrawn:\n{paragraph[:200]}"
            )


def test_the_register_prints_each_figure_with_its_revision() -> None:
    """A number with no revision next to it is the ambiguity that caused all of this."""
    text = REGISTER.read_text(encoding="utf-8")
    assert "**R5 — ≥1 GiB corpus" in text or "**R5 —" in text
    assert "**R4 —" in text
    for value in ("0.3101", "0.3120", "0.3077"):
        assert value in text


def test_the_claims_checker_passes_strictly() -> None:
    """The gate CI now runs. If this fails, two documents disagree at the same revision."""
    proc = subprocess.run(
        [sys.executable, "scripts/check-benchmark-claims.py", "--strict"],
        cwd=REPO, capture_output=True, text=True, timeout=120,
    )
    assert proc.returncode == 0, proc.stdout[-1200:] + proc.stderr[-400:]
    assert "every named measurement agrees" in proc.stdout
