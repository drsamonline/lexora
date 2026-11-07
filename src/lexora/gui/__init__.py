"""LEXORA GUI package (ADR-0008: PySide6, same repo, opt-in `[gui]` extra).

Layering (DESIGN_GUI.md §2, binding via ADR-0008 decision 3):
    views/controllers  ->  app-service adapter (this package's `service`)
                        ->  lexora.canonicalize / lexora.zstd_core / lexora.container

Layering was ADR-0008's "thin client over an in-process service"; **ADR-0011
(accepted 2026-10-29) partly supersedes that: the GUI is a client of the CLI.**
So the binding rules are now:

  * the GUI **shells out to `lexora <verb>`** for archive operations — one
    implementation, one contract, and a crash in a worker cannot take the window
    down (see `gui/query.py`, which speaks `lexora db … --json`);
  * the GUI still **MUST NOT re-implement** canonicalization, codec, container or
    catalog logic — calling the CLI is not re-implementing it;
  * the Qt-free core and the opt-in `[gui]` extra still stand (ADR-0008
    decisions 1–2, untouched by ADR-0011).

`gui/service.py` still contains the in-process adapter from ADR-0008; moving it
onto subprocess calls is the open half of ADR-0011 (PATH_TO_V1 P2).

Import policy: this top-level package imports NOTHING from Qt, so importing
`lexora.gui` never requires PySide6. `lexora.gui.service` touches Qt only
lazily (worker-thread factory), and `lexora.gui.app` (G1/G2/G3/G4 shell)
keeps every Qt import inside functions — core installs stay Qt-free per
ADR-0008 decision 1.

Status: GUI-M1 scaffold + runnable window shell (Session 27/28). Launch with
`python -m lexora.gui` when the `[gui]` extra is installed; a console entry
point (`lexora-gui`) lands in pyproject only once owner has run the window
(ADR-0008 decision 2).
"""

__all__ = ["app", "crash", "service"]


def main(argv: list[str] | None = None) -> int:
    """`python -m lexora.gui` entry: delegates to lexora.gui.app.main()."""
    from lexora.gui.app import main as _main

    return _main(argv)
