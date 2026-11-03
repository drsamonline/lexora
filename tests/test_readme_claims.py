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
