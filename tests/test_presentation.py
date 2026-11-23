"""The fleet's presentation standard, held by tests instead of by a sweep.

`drsamonline/audit` → `tools/presentation_audit.py` audits every repo against the repo-presentation
skill and says what each one still needs. Run against `lexora` on 2026-11-23 it found three gaps:
no local badge set, no `data-support` marker on the landing page's support block, and no UPI intent
link. All three were real, and none of them was caught by anything in this repository — the audit
lives in another repo and is run by hand.

These tests are the part of that standard this repo can check by itself. They are deliberately about
the *claims*, not the styling: a badge that says "green" must be regenerable, the support block must
carry the handles it prints, and the UPI link must be a link rather than a string a phone cannot use.

Not covered, on purpose: the screenshot surface. `docs/assets/app-desktop.png` needs the `[gui]`
extra and a Qt-capable machine (`scripts/gen_screenshots.py` skips without PySide6), and
`app-mobile.png` would be a *mobile* screenshot of a desktop application — fabricating one to satisfy
a checklist is the failure this whole repository spent a day removing. The gap stays visible in the
audit until someone runs it on a machine with Qt.
"""

from __future__ import annotations

import pathlib
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]
LANDING = REPO / "docs" / "index.html"
ASSETS = REPO / "docs" / "assets"

BADGES = ["live", "tests", "build", "licence", "offline", "deps"]

#: The six handles the fleet's support block must carry, and the audit checks by exact string.
HANDLES = [
    "drsohilboi@ybl",
    "ko-fi.com/matneo",
    "paypal.me/drsohilmomin",
    "B08ZT331LY",
    "drsamonline.github.io",
    "sohilmomin2000@gmail.com",
]


@pytest.mark.parametrize("stem", BADGES)
def test_the_local_badge_exists_and_is_valid_svg(stem: str) -> None:
    path = ASSETS / f"badge-{stem}.svg"
    assert path.is_file(), f"missing {path.name} — run: python3 scripts/badges.py"
    ET.parse(path)                                   # raises if it is not well-formed SVG


def test_the_local_badges_are_current_with_their_generator() -> None:
    """A committed SVG that no longer matches `scripts/badges.py` is a claim with no source."""
    proc = subprocess.run([sys.executable, "scripts/badges.py", "--check"],
                          cwd=REPO, capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_the_tests_badge_carries_no_static_count() -> None:
    """The README may not quote a test count nothing recomputes — neither may a badge.

    `tests/test_readme_claims.py` forbids the static shield for the same reason: the number decays
    the moment a test is added, silently. The badge states a condition; CI carries the count.
    """
    text = (ASSETS / "badge-tests.svg").read_text(encoding="utf-8")
    assert not re.search(r"\b\d{2,4}\s+(?:passed|passing|tests)\b", text), (
        "the tests badge quotes a static count — put the count in the CI badge"
    )


def test_the_landing_page_marks_its_support_block() -> None:
    """`data-support` is what the fleet's audit looks for; without it the block is invisible."""
    assert "data-support" in LANDING.read_text(encoding="utf-8")


def test_the_support_block_carries_every_handle() -> None:
    landing = LANDING.read_text(encoding="utf-8")
    missing = [h for h in HANDLES if h not in landing]
    assert not missing, f"the support block lost these handles: {missing}"


def test_the_upi_payment_is_a_link_not_just_text() -> None:
    """A printed VPA is useless on the device that would pay it."""
    landing = LANDING.read_text(encoding="utf-8")
    intents = re.findall(r"upi://pay\?[^\"'\s]+", landing)
    assert intents, "no upi://pay intent link on the page"
    for link in intents:
        assert "am=" not in link, (
            f"the intent suggests an amount ({link}) — the fleet standard is an open amount"
        )
        assert "pa=drsohilboi@ybl" in link, "the intent does not name the payee VPA"
