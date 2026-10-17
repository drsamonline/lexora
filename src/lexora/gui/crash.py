"""Crash diagnostics wiring for the LEXORA GUI (GUI-M3, DESIGN_GUI §3).

ADR-0008 thin-client rule holds: this module owns no business logic — it
only captures *evidence* when something escapes the tested service paths.

Two layers:

* ``faulthandler`` — enabled in :func:`install` so hard crashes (SIGSEGV
  etc., e.g. inside Qt itself) dump a Python traceback to stderr instead
  of dying silently. Standard-library only; no Qt import anywhere here.
* :class:`CrashLog` — appends one record per uncaught exception to a
  JSON-lines file under the user's config dir (same root as G7 settings,
  deliberately a *separate* file so neither can corrupt the other), and
  installs itself as ``sys.excepthook`` so main-thread tracebacks land in
  the log before the default handler prints them.

Privacy note (DESIGN_GUI §3): records contain the exception type/message
and traceback text — which may quote file *paths* the user worked on —
but never file *contents*. Paths are kept because without them a report
is unactionable; this trade-off is recorded here rather than hidden.
"""

from __future__ import annotations

import faulthandler
import json
import os
import sys
import time
import traceback
from pathlib import Path


def crash_log_path() -> Path:
    """crash.log.jsonl next to the GUI settings file (same config root)."""
    from lexora.gui.service import _config_root  # local import: keep light

    return _config_root() / "crash.log.jsonl"


class CrashLog:
    """Append-only JSONL crash sink + sys.excepthook installer."""

    def __init__(self, path: Path | None = None) -> None:
        self._path = path if path is not None else crash_log_path()
        self._previous_hook = sys.excepthook

    @property
    def path(self) -> Path:
        return self._path

    def read_records(self) -> list[dict]:
        """All logged records (oldest first); [] when the log is absent."""
        try:
            raw = self._path.read_text(encoding="utf-8")
        except OSError:
            return []
        out = []
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                continue  # tolerate torn final lines
            if isinstance(rec, dict):
                out.append(rec)
        return out

    def record_exception(self, exc: BaseException) -> dict:
        """Append one record; returns it. Best-effort: if the write fails
        there is nothing left to do but keep the original traceback alive
        downstream, so errors here are swallowed after a stderr note."""
        rec = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "version": getattr(sys.modules.get("lexora"), "__version__", "?"),
            "type": type(exc).__name__,
            "message": str(exc),
            "traceback": "".join(
                traceback.format_exception(type(exc), exc, exc.__traceback__)
            ),
        }
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(rec) + "\n")
                fh.flush()
        except OSError as write_exc:  # pragma: no cover - disk-level failure
            print(f"lexora-gui: cannot write crash log {self._path}: {write_exc}",
                  file=sys.stderr)
        return rec

    def excepthook(self, etype, value, tb) -> None:
        """Log the escaped exception, then chain to the previous hook so
        interactive consoles/IDEdiagnostics still see the normal output."""
        if issubclass(etype, KeyboardInterrupt):
            self._previous_hook(etype, value, tb)  # Ctrl-C: don't log as crash
            return
        if value is not None:
            self.record_exception(value)
        self._previous_hook(etype, value, tb)

    def install(self) -> None:
        sys.excepthook = self.excepthook


def install(path: Path | None = None) -> CrashLog:
    """Enable faulthandler + install the excepthook sink. Idempotent-safe:
    calling twice just re-wraps (previous hook chains harmlessly)."""
    try:
        faulthandler.enable(all_threads=True)
    except Exception:  # pragma: no cover - stderr closed/weird environments
        pass
    log = CrashLog(path)
    log.install()
    return log
