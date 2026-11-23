"""Third-party notices for the ``[gui]`` extra — the R3 obligation, made checkable.

**Why this module exists.** LEXORA's core install is Qt-free (ADR-0008), so the GUI is an
optional extra. The moment someone installs it, the distribution carries **LGPL-3.0
obligations** for PySide6/Qt, and `NOTICE` already states what those are. What was missing
until P2.4 was the mechanical half: the licence *texts* travelling with the distribution, and
a place in the application where a user can see the notice without opening a repository.

**What the LGPL actually requires here.** The texts must accompany the distribution, the user
must be able to replace the Qt libraries (satisfied by taking the PySide6 wheel as a shared
library, not a static build), and there must be a pointer to where the corresponding source can
be obtained. All three are in `GUI_NOTICES` below, and the texts ship as package data.

**Where the texts came from.** Not typed from memory — a licence text that has been
paraphrased is worse than no text at all, because it looks authoritative. Both files are the
canonical texts as published in the SPDX licence list (`spdx/license-list-data`,
`text/LGPL-3.0-only.txt` and `text/GPL-3.0-only.txt`), unmodified, and
`tests/test_gui_notices.py` pins their SHA-256 so an edit to them cannot pass unnoticed:

===========  ===========================================================  ========
File         SHA-256                                                      Bytes
===========  ===========================================================  ========
LGPL-3.0.txt 996af0513df21f7496288951c41428a03c174e9e4a9d63665c57d670f845ccb1  42098
GPL-3.0.txt  fb981668c18a279e285fc4d83fba1e836cc84dd4daa73c9697d3cfd2d8aca6e0  34674
===========  ===========================================================  ========

The GPL-3.0 text is here because LGPL-3.0 is written as a set of additional permissions on top
of GPL-3.0 and incorporates it by reference: shipping the LGPL alone ships a document that
points at a licence the reader does not have.

**Nothing here imports Qt**, deliberately. The About view is Qt-free (the thin-client posture
of ADR-0011), so the notices render on a machine where PySide6 was never installed — which is
also the only way this module can be tested in CI.
"""

from __future__ import annotations

from importlib import resources

#: Licence id -> the file shipped under ``lexora/gui/notice_texts/``.
NOTICE_FILES: dict[str, str] = {
    "LGPL-3.0": "LGPL-3.0.txt",
    "GPL-3.0": "GPL-3.0.txt",
}

#: Where the corresponding Qt/PySide6 source can be obtained (LGPL relink obligation).
QT_SOURCE_POINTER = "https://download.qt.io/official_releases/QtForPython/"

#: The human-readable notice. Rendered by the About view and printed by
#: ``python -m lexora.gui.notices``. Keep it true: every claim here is either a licence term
#: or something a test can check.
GUI_NOTICES = """\
Third-party notices — the GUI extra

LEXORA itself is PolyForm Noncommercial 1.0.0, © 2026 Dr. Sohil Momin, and that licence
requires this line to travel with every copy:

  Required Notice: Copyright 2026 Dr Sohil Momin

This GUI is built on PySide6, taken under LGPL-3.0-only. Qt and PySide6 are
© The Qt Company Ltd and contributors, and are not part of LEXORA. Distributing a GUI
build therefore carries three obligations, all met by this package:

  1. the LGPL-3.0 text travels with the distribution — it ships inside the package
     alongside this notice, together with GPL-3.0, which LGPL-3.0 incorporates by
     reference;
  2. the Qt libraries can be replaced — LEXORA uses the PySide6 wheel as a shared
     library, never a static build, and does not prohibit replacing those files;
  3. there is a pointer to the corresponding source:
     %s

LEXORA's own code stays under PolyForm Noncommercial. The LGPL governs Qt, not this
project: an application may carry any licence while linking LGPL components
dynamically. That is the same boundary the rest of the estate draws — a component's
licence governs the component.

The core install is Qt-free (ADR-0008); none of this applies unless the [gui] extra is
installed. Full statement, including the benchmark-only dependencies that never ship:
NOTICE at the repository root. This is a notice, not legal advice — the licence texts
are the authority.
""" % QT_SOURCE_POINTER


def licence_text(name: str) -> str:
    """Return the full text of a shipped licence.

    Read through :mod:`importlib.resources` rather than a filesystem path, so it works from a
    wheel, a zip, or a source checkout without the caller knowing which.
    """
    try:
        filename = NOTICE_FILES[name]
    except KeyError:
        raise KeyError(
            f"no licence text named {name!r}; shipped: {sorted(NOTICE_FILES)}"
        ) from None
    return resources.files(__package__).joinpath("notice_texts", filename).read_text(
        encoding="utf-8"
    )


def notice_texts_location() -> str:
    """A display string for where the licence texts live, for the About view.

    Display only — read them with :func:`licence_text`, which works from a zip as well.
    """
    return str(resources.files(__package__).joinpath("notice_texts"))


def format_notices_text() -> str:
    """The notice followed by both full licence texts — what ``python -m`` prints."""
    parts = [GUI_NOTICES.rstrip(), ""]
    for name in NOTICE_FILES:
        parts += ["=" * 78, f"{name} — full text", "=" * 78, "", licence_text(name).rstrip(), ""]
    return "\n".join(parts)


def main(argv: list[str] | None = None) -> int:
    """``python -m lexora.gui.notices`` — print the notice and the texts, exit 0."""
    print(format_notices_text())
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised by a subprocess test
    raise SystemExit(main())
