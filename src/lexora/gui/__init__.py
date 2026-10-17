"""LEXORA GUI package (ADR-0008: PySide6, same repo, opt-in `[gui]` extra).

Layering (DESIGN_GUI.md §2, binding via ADR-0008 decision 3):
    views/controllers  ->  app-service adapter (this package's `service`)
                        ->  lexora.canonicalize / lexora.zstd_core / lexora.container

The GUI is a thin client: it MUST NOT shell out to the CLI and MUST NOT
re-implement canonicalization, codec, or container logic.

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

__all__ = ["app", "service"]


def main(argv: list[str] | None = None) -> int:
    """`python -m lexora.gui` entry: delegates to lexora.gui.app.main()."""
    from lexora.gui.app import main as _main

    return _main(argv)
