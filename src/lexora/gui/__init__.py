"""LEXORA GUI package (ADR-0008: PySide6, same repo, opt-in `[gui]` extra).

Layering (DESIGN_GUI.md §2, binding via ADR-0008 decision 3):
    views/controllers  ->  app-service adapter (this package's `service`)
                        ->  lexora.canonicalize / lexora.zstd_core / lexora.container

The GUI is a thin client: it MUST NOT shell out to the CLI and MUST NOT
re-implement canonicalization, codec, or container logic.

Import policy: this top-level package imports NOTHING from Qt, so importing
`lexora.gui` never requires PySide6. Only `lexora.gui.service` touches Qt
(and only lazily, inside worker-thread factories), keeping the core install
Qt-free per ADR-0008 decision 1.

Status: GUI-M1 scaffold (Session 27). No console entry point yet — added by
a later session only when a runnable window exists (ADR-0008 decision 2).
"""

__all__ = ["service"]
