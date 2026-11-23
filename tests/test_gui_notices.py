"""P2.4 / R3: the GUI's third-party notices, held to what they claim.

The ``[gui]`` extra takes PySide6 under **LGPL-3.0-only**, so a GUI distribution carries
obligations that a README sentence does not discharge: the licence texts must travel with it,
the Qt libraries must be replaceable, and there must be a pointer to the corresponding source.

`NOTICE` already stated all three. What nothing checked was the mechanical half — that the
texts are actually in the package, that they are the *canonical* texts rather than a
paraphrase, and that the application shows the notice. That is what this file pins.

The SHA-256 values are deliberate. A licence text that has been edited to say something
slightly different is worse than a missing one, because it looks authoritative; if the texts
are ever regenerated, these two constants must be updated in the same commit, on purpose.
"""

from __future__ import annotations

import hashlib
import pathlib
import re
import subprocess
import sys

import pytest

from lexora.gui import notices
from lexora.gui.app import format_about_text

REPO = pathlib.Path(__file__).resolve().parents[1]

#: The canonical texts as published in the SPDX licence list (`spdx/license-list-data`,
#: `text/LGPL-3.0-only.txt` and `text/GPL-3.0-only.txt`), unmodified.
PINNED_SHA256 = {
    "LGPL-3.0": "996af0513df21f7496288951c41428a03c174e9e4a9d63665c57d670f845ccb1",
    "GPL-3.0": "fb981668c18a279e285fc4d83fba1e836cc84dd4daa73c9697d3cfd2d8aca6e0",
}

FIRST_LINE = {
    "LGPL-3.0": "GNU LESSER GENERAL PUBLIC LICENSE",
    "GPL-3.0": "GNU GENERAL PUBLIC LICENSE",
}


def test_the_notice_names_the_licence_the_project_actually_takes() -> None:
    """PySide6 is triple-licensed; the notice must say which one LEXORA takes, and name Qt."""
    text = notices.GUI_NOTICES
    assert "LGPL-3.0-only" in text, "the notice does not say which PySide6 licence is taken"
    assert "PySide6" in text and "Qt" in text
    assert "PolyForm Noncommercial" in text, (
        "the notice must keep LEXORA's own licence distinct from Qt's — the two are different "
        "questions and conflating them is how a distribution ends up out of terms"
    )


def test_the_required_notice_line_travels() -> None:
    """PolyForm Noncommercial requires its `Required Notice:` line in every copy."""
    assert "Required Notice: Copyright 2026 Dr Sohil Momin" in notices.GUI_NOTICES
    assert "Required Notice: Copyright 2026 Dr Sohil Momin" in format_about_text(), (
        "the About view is a copy of the software as far as a user is concerned"
    )


def test_the_notice_points_at_the_corresponding_source() -> None:
    """LGPL-3.0 §4/§6: a user must be able to find the source of the library they received."""
    assert notices.QT_SOURCE_POINTER.startswith("https://")
    assert notices.QT_SOURCE_POINTER in notices.GUI_NOTICES
    assert notices.QT_SOURCE_POINTER in format_about_text()


@pytest.mark.parametrize("name", sorted(PINNED_SHA256))
def test_the_shipped_licence_text_is_the_canonical_text(name: str) -> None:
    """Read back through importlib.resources — the same route an installed wheel uses."""
    text = notices.licence_text(name)
    assert text.startswith(FIRST_LINE[name]), (
        f"{name} does not begin with {FIRST_LINE[name]!r} — is this the right licence?"
    )
    assert "Version 3, 29 June 2007" in text[:200], "not the version-3 text this project relies on"
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    assert digest == PINNED_SHA256[name], (
        f"{name} has changed (sha256 {digest}). If that was deliberate, update PINNED_SHA256 "
        "in this file and NOTICE in the same commit; if it was not, the text has been altered."
    )
    assert len(text) > 30_000, f"{name} is {len(text)} bytes — a truncated licence is not a licence"


def test_gpl_ships_because_lgpl_incorporates_it() -> None:
    """LGPL-3.0 is additional permissions on top of GPL-3.0 and references it by name."""
    lgpl = notices.licence_text("LGPL-3.0")
    assert "GNU General Public License" in lgpl, (
        "the LGPL text refers to the GPL; if this assertion ever fails the reasoning in "
        "notices.py needs re-reading, not deleting"
    )
    assert "GPL-3.0" in notices.NOTICE_FILES


def test_an_unknown_licence_name_says_what_is_shipped() -> None:
    """A KeyError that lists the alternatives is a fix; a bare one is a puzzle."""
    with pytest.raises(KeyError) as excinfo:
        notices.licence_text("MIT")
    assert "LGPL-3.0" in str(excinfo.value) and "GPL-3.0" in str(excinfo.value)


def test_the_about_view_shows_the_notice_without_qt() -> None:
    """The About view is Qt-free (ADR-0011), so the notice must render with no PySide6."""
    text = format_about_text()
    assert "Third-party notices" in text
    assert "LGPL-3.0-only" in text
    assert "python -m lexora.gui.notices" in text, (
        "the About view must tell a user how to read the full texts"
    )


def test_python_m_prints_the_notice_and_both_texts() -> None:
    """`python -m lexora.gui.notices` is the route that works with no GUI installed."""
    proc = subprocess.run(
        [sys.executable, "-m", "lexora.gui.notices"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr[-400:]
    assert "Third-party notices" in proc.stdout
    for name in PINNED_SHA256:
        assert FIRST_LINE[name] in proc.stdout, f"the full {name} text was not printed"


def test_the_licence_texts_are_declared_as_package_data() -> None:
    """A text on disk that the wheel does not carry is not a text that travels.

    This asserts the declaration, not the wheel — building one in a unit test would cost
    minutes. The declaration is the thing that gets lost when packaging is reorganised.
    """
    pyproject = (REPO / "pyproject.toml").read_text(encoding="utf-8")
    block = re.search(
        r"\[tool\.setuptools\.package-data\](.*?)(?=\n\[)", pyproject, re.DOTALL
    )
    assert block, "no [tool.setuptools.package-data] section"
    assert "notice_texts/*.txt" in block.group(1), (
        "the licence texts are not declared as package data, so a built wheel would not carry "
        "them and every GUI distribution would be out of terms"
    )
    shipped = sorted(p.name for p in (REPO / "src/lexora/gui/notice_texts").glob("*.txt"))
    assert shipped == sorted(notices.NOTICE_FILES.values()), (
        f"declared {sorted(notices.NOTICE_FILES.values())} but found {shipped}"
    )
