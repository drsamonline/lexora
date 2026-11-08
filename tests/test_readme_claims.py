"""Guards for the claims the docs make about the CLI and the test suite.

Two things in this repository are cheap to state and expensive to be wrong about:

1. **The verb list.** `docs/CLI_REFERENCE.md` is the reference a user reads before
   typing anything. A verb that exists but is undocumented is invisible; a verb that
   is documented but absent is a broken instruction. Both are drift, and neither was
   checked by anything until this file.

2. **The test count.** The README used to carry a static `tests-502 passed` shield.
   A number nothing recomputes is a claim that silently decays — the suite was at 510
   when this guard was written, so the badge had been wrong for a while and nothing
   said so. The rule now: the README carries no static test count. The live CI badge
   is the number, because CI recomputes it on every push.

Neither guard asserts a number. They assert a *shape*: same verbs on both sides, and
no un-recomputable count in the README. That way adding a test or a verb never turns
this file red, but forgetting the docs does.
"""

from __future__ import annotations

import pathlib
import re

import pytest

from lexora import cli

REPO = pathlib.Path(__file__).resolve().parents[1]
CLI_REFERENCE = REPO / "docs" / "CLI_REFERENCE.md"
README = REPO / "README.md"


def _implemented_verbs() -> set[str]:
    parser = cli.build_parser()
    for action in parser._actions:  # argparse exposes subparsers only this way
        choices = getattr(action, "choices", None)
        if isinstance(choices, dict) and choices:
            return set(choices)
    pytest.fail("no subparsers found on the CLI parser — has build_parser changed shape?")


def _documented_verbs() -> set[str]:
    text = CLI_REFERENCE.read_text(encoding="utf-8")
    return set(re.findall(r"^### `lexora ([a-z0-9-]+)`", text, flags=re.MULTILINE))


def test_every_implemented_verb_is_documented() -> None:
    """A verb a user can type must appear in the reference."""
    missing = _implemented_verbs() - _documented_verbs()
    assert not missing, (
        f"these verbs exist in the CLI but have no `### `lexora <verb>`` section in "
        f"docs/CLI_REFERENCE.md: {sorted(missing)}"
    )


def test_every_documented_verb_exists() -> None:
    """A verb the reference tells a user to type must exist."""
    phantom = _documented_verbs() - _implemented_verbs()
    assert not phantom, (
        f"docs/CLI_REFERENCE.md documents verbs the CLI does not implement: "
        f"{sorted(phantom)}"
    )


def test_the_documented_verb_list_is_not_empty() -> None:
    """A parse that finds nothing would make the two guards above vacuous."""
    assert len(_documented_verbs()) >= 5
    assert len(_implemented_verbs()) >= 5


def test_readme_carries_no_static_test_count() -> None:
    """The README must not claim a test count nothing recomputes.

    A static `tests-NNN` shield decays the moment a test is added or removed, and
    nothing fails when it does — that is a claim, not a measurement. The CI badge is
    the live number; the local count belongs in docs/STATUS.md, next to the date it
    was measured.
    """
    text = README.read_text(encoding="utf-8")
    static = re.findall(r"badge/tests-\d+[^)\s]*", text)
    assert not static, (
        "README carries a static test-count shield that nothing recomputes: "
        f"{static}. Use the CI badge for the live number and record the local count, "
        "with its date, in docs/STATUS.md."
    )


# --------------------------------------------------------------------------- #
# the verb count, which is prose and therefore needs a machine to hold it
# --------------------------------------------------------------------------- #

def test_documented_subcommand_count_matches_the_cli() -> None:
    """A count written in prose is a claim, and this one drifted silently.

    README and the landing page both said "nine subcommands" while the CLI had
    eleven (`db` and `zdecode` were added and nobody re-read the sentence). The
    same class of drift has now hit this repo three times — test counts, the
    default level, and this — so the number is pinned to the parser instead of
    being trusted.
    """
    import re

    from lexora.cli import build_parser

    parser = build_parser()
    verbs = sorted(parser._subparsers._group_actions[0].choices)
    assert len(verbs) == 11, f"verb count changed to {len(verbs)}: {verbs}"

    words = {9: "nine", 10: "ten", 11: "eleven", 12: "twelve"}
    expected = words[len(verbs)]

    readme = (REPO / "README.md").read_text()
    assert f"the {expected} subcommands" in readme, (
        f"README should say '{expected} subcommands' for {len(verbs)} verbs"
    )
    landing = (REPO / "docs" / "index.html").read_text()
    assert f"<b>{len(verbs)}</b><span>CLI subcommands" in landing, (
        f"landing page should show {len(verbs)} CLI subcommands"
    )
    # and every verb must appear in the landing page's tag line
    tag = re.search(r'<span class="tag">(canon · [^<]+)</span>', landing)
    assert tag, "landing page verb tag line not found"
    listed = {v.strip() for v in tag.group(1).split("·")}
    assert listed == set(verbs), f"landing page lists {sorted(listed)}, CLI has {verbs}"


# --------------------------------------------------------------------------- #
# the query-path probe must stay honest
# --------------------------------------------------------------------------- #

def test_index_rss_probe_runs_a_real_query_not_an_import_error(tmp_path) -> None:
    """The probe's own history is the reason for this test.

    Its first version reported every row "ok" while the CLI was failing to import — a
    relative PYTHONPATH broken by chdir — and its second reported the probe's own
    fixture as the CLI's memory, because a forked child inherits the parent's
    footprint before exec. Both failures were *silent*: the table looked plausible.

    So: run the probe small, and assert the child processes actually succeeded and
    that `get` costs more than `search` (the shape that proves the document decode is
    happening rather than being measured as a no-op).
    """
    import json
    import subprocess
    import sys

    out = tmp_path / "rss.json"
    proc = subprocess.run(
        [sys.executable, "benchmarks/index_rss_probe.py",
         "--sizes", "1", "--reps", "1", "--cap-mib", "512", "--out", str(out)],
        cwd=REPO, capture_output=True, text=True,
        env={**__import__("os").environ, "PYTHONPATH": str(REPO / "src")},
    )
    assert proc.returncode == 0, proc.stderr[-500:]
    doc = json.loads(out.read_text())
    row = doc["rows"][0]
    assert row["search_exit"] == 0, f"search did not run: {row.get('errors')}"
    assert row["get_exit"] == 0, f"get did not run: {row.get('errors')}"
    assert row["search_peak_rss_kib"] > 0 and row["get_peak_rss_kib"] > 0
    assert row["index_bytes"] > 0 and row["canonical_bytes"] > 0
    # Deliberately NOT asserting `get >= search`. It usually holds — `get` decodes a
    # document and `search` does not — but ru_maxrss is environment-dependent, and
    # under load the two land either side of each other. That made this test flaky,
    # and a flaky test trains people to re-run rather than read. The exit codes above
    # are the deterministic proof that the child really ran; the ordering is reported
    # in the artifact and left to a human.
    assert row["get_wall_s"] > 0 and row["search_wall_s"] > 0


def test_the_two_version_strings_agree() -> None:
    """pyproject and `lexora.__version__` drift silently — a release with two versions
    is a release nobody can trace. This has bitten projects far larger than this one."""
    import re

    from lexora import __version__

    pyproject = (REPO / "pyproject.toml").read_text()
    declared = re.search(r'^version = "([^"]+)"', pyproject, re.MULTILINE)
    assert declared, "no version in pyproject.toml"
    assert declared.group(1) == __version__, (
        f"pyproject says {declared.group(1)!r}, package says {__version__!r}"
    )
