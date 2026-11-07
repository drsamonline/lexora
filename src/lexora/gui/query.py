"""The query view: search a compressed archive, preview what you found.

Architecture note (ADR-0011, which partly supersedes ADR-0008)
--------------------------------------------------------------
The GUI is a **client of the CLI**, not an in-process library consumer. So this
module shells out to `lexora db …` and parses JSON, rather than importing
`lexora.catalog` and opening the SQLite index itself. Three consequences, all
deliberate:

  * the CLI is the contract — anything the GUI can do, a script can do, and the
    two cannot drift because there is only one implementation;
  * a crash in the query path cannot take the window down with it;
  * the panel is testable without a display and without the catalog internals.

`lexora/gui/__init__.py` used to say the opposite ("MUST NOT shell out to the
CLI"). That was ADR-0008's rule and ADR-0011 replaced it; the docstring is now
corrected, because a stale binding statement is how the wrong rule gets followed
for months.

Threading
---------
A query is a subprocess, so it must not run on the UI thread. `QueryPanel` uses a
`QThread` worker; the widget-level tests call `run_search()` directly (synchronous,
no event loop needed) so they assert behaviour rather than timing.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass

DEFAULT_LIMIT = 50
TIMEOUT_S = 120


class QueryError(Exception):
    """A query failed. Carries the CLI's own message so the user sees the real reason."""


@dataclass(frozen=True)
class Hit:
    doc_id: int
    path: str
    version: int
    title: str | None
    stored_bytes: int
    canonical_bytes: int
    codec: str

    @classmethod
    def from_dict(cls, d: dict) -> Hit:
        return cls(
            doc_id=int(d["doc_id"]),
            path=str(d["path"]),
            version=int(d["version"]),
            title=d.get("title"),
            stored_bytes=int(d["stored_bytes"]),
            canonical_bytes=int(d["canonical_bytes"]),
            codec=str(d["codec"]),
        )


class QueryClient:
    """Thin wrapper over `lexora db`, speaking JSON.

    Every method raises `QueryError` with the CLI's stderr text rather than
    guessing at a cause — the CLI already produces precise refusal messages
    (catalog missing, blob corrupt, codec absent), and re-wording them here would
    make the two surfaces disagree.
    """

    def __init__(self, root: str, *, python: str | None = None,
                 timeout: int = TIMEOUT_S) -> None:
        self.root = str(root)
        self._python = python or sys.executable
        self._timeout = timeout

    # -- plumbing ---------------------------------------------------------

    def _run(self, argv: list[str], *, expect_json: bool = True) -> str:
        cmd = [self._python, "-m", "lexora.cli", "db", *argv]
        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True, timeout=self._timeout,
                env=os.environ.copy(),
            )
        except FileNotFoundError as exc:  # pragma: no cover - python always exists
            raise QueryError(f"cannot run {self._python}: {exc}") from exc
        except subprocess.TimeoutExpired as exc:
            raise QueryError(f"query timed out after {self._timeout}s") from exc
        if proc.returncode != 0:
            reason = (proc.stderr or proc.stdout).strip().splitlines()
            raise QueryError(reason[-1] if reason else f"exit {proc.returncode}")
        return proc.stdout

    # -- operations -------------------------------------------------------

    def search(self, query: str | None = None, *, filters: dict | None = None,
               limit: int = DEFAULT_LIMIT) -> list[Hit]:
        argv = ["search", "--root", self.root, "--limit", str(limit), "--json"]
        if query:
            argv += ["--query", query]
        for key, value in (filters or {}).items():
            argv += ["--filter", f"{key}={value}"]
        payload = json.loads(self._run(argv) or "[]")
        return [Hit.from_dict(d) for d in payload]

    def get_text(self, path: str) -> str:
        return self._run(["get", "--root", self.root, path], expect_json=False)

    def stats(self) -> dict:
        return json.loads(self._run(["stats", "--root", self.root]))

    def init(self) -> None:
        self._run(["init", "--root", self.root], expect_json=False)


# --------------------------------------------------------------------------- #
# Qt widgets — imported lazily so `import lexora.gui.query` stays Qt-free
# --------------------------------------------------------------------------- #

def build_panel(root: str = "", *, parent=None):
    """Construct the query panel. Raises ImportError with guidance if Qt is absent."""
    try:
        from PySide6.QtCore import QThread, Signal
        from PySide6.QtWidgets import (
            QFileDialog, QHBoxLayout, QLabel, QLineEdit, QPushButton,
            QTableWidget, QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget,
        )
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise ImportError(
            "the query view needs the [gui] extra: pip install 'lexora[gui]'"
        ) from exc

    class _SearchWorker(QThread):
        done = Signal(object)
        failed = Signal(str)

        def __init__(self, client: QueryClient, query: str, filters: dict) -> None:
            super().__init__()
            self._client, self._query, self._filters = client, query, filters

        def run(self) -> None:  # pragma: no cover - exercised via the panel
            try:
                self.done.emit(self._client.search(self._query, filters=self._filters))
            except QueryError as exc:
                self.failed.emit(str(exc))

    class QueryPanel(QWidget):
        """Search box + result table + preview pane.

        `run_search()` and `load_preview()` are public and synchronous so tests can
        drive the widget without spinning an event loop; the buttons call the
        threaded path.
        """

        def __init__(self, root_path: str = "", parent=None) -> None:
            super().__init__(parent)
            self._worker: _SearchWorker | None = None
            self._hits: list[Hit] = []

            layout = QVBoxLayout(self)

            root_row = QHBoxLayout()
            root_row.addWidget(QLabel("Archive:"))
            self.root_edit = QLineEdit(root_path)
            self.root_edit.setPlaceholderText("catalog directory (the --root of `lexora db init`)")
            root_row.addWidget(self.root_edit, 1)
            self.browse_button = QPushButton("Browse…")
            self.browse_button.clicked.connect(self._on_browse)
            root_row.addWidget(self.browse_button)
            layout.addLayout(root_row)

            query_row = QHBoxLayout()
            query_row.addWidget(QLabel("Search:"))
            self.query_edit = QLineEdit()
            self.query_edit.setPlaceholderText("full text — leave empty to list by filter")
            self.query_edit.returnPressed.connect(self._on_search_clicked)
            query_row.addWidget(self.query_edit, 2)
            query_row.addWidget(QLabel("Filter:"))
            self.filter_edit = QLineEdit()
            self.filter_edit.setPlaceholderText("key=value")
            query_row.addWidget(self.filter_edit, 1)
            self.search_button = QPushButton("Search")
            self.search_button.clicked.connect(self._on_search_clicked)
            query_row.addWidget(self.search_button)
            layout.addLayout(query_row)

            self.table = QTableWidget(0, 4)
            self.table.setHorizontalHeaderLabels(["Path", "v", "Stored", "Title"])
            self.table.itemSelectionChanged.connect(self._on_selection)
            layout.addWidget(self.table, 2)

            self.preview = QTextEdit()
            self.preview.setReadOnly(True)
            self.preview.setPlaceholderText("select a result to read it (only that document is decoded)")
            layout.addWidget(self.preview, 3)

            self.status = QLabel("")
            layout.addWidget(self.status)

        # -- helpers ------------------------------------------------------

        def _client(self) -> QueryClient:
            root = self.root_edit.text().strip()
            if not root:
                raise QueryError("choose an archive directory first")
            # Fail fast on the common mistake (a mistyped path) instead of showing
            # "searching…" and then surfacing a subprocess error a second later.
            if not os.path.isdir(root):
                raise QueryError(f"no such archive directory: {root}")
            return QueryClient(root)

        @staticmethod
        def _parse_filters(text: str) -> dict:
            out: dict = {}
            for chunk in text.split(","):
                chunk = chunk.strip()
                if not chunk:
                    continue
                if "=" not in chunk:
                    raise QueryError(f"filter {chunk!r} is not key=value")
                key, _, value = chunk.partition("=")
                out[key.strip()] = value.strip()
            return out

        def _set_status(self, text: str) -> None:
            self.status.setText(text)

        # -- synchronous core (what the tests drive) ----------------------

        def run_search(self, query: str | None = None, filters: dict | None = None) -> list[Hit]:
            """Run one search and populate the table. Raises QueryError on failure."""
            client = self._client()
            hits = client.search(
                self.query_edit.text().strip() if query is None else query,
                filters=self._parse_filters(self.filter_edit.text()) if filters is None else filters,
            )
            self._hits = hits
            self.table.setRowCount(len(hits))
            for row, hit in enumerate(hits):
                self.table.setItem(row, 0, QTableWidgetItem(hit.path))
                self.table.setItem(row, 1, QTableWidgetItem(str(hit.version)))
                self.table.setItem(row, 2, QTableWidgetItem(f"{hit.stored_bytes:,}"))
                self.table.setItem(row, 3, QTableWidgetItem(hit.title or ""))
            self._set_status(
                f"{len(hits)} result(s)" if hits else "no matches"
            )
            return hits

        def load_preview(self, row: int) -> str:
            """Decode and show one result. Raises QueryError on failure."""
            hit = self._hits[row]
            text = self._client().get_text(hit.path)
            self.preview.setPlainText(text)
            self._set_status(f"{hit.path} — {len(text):,} characters decoded")
            return text

        # -- slots --------------------------------------------------------

        def _on_search_clicked(self) -> None:
            try:
                client = self._client()
                filters = self._parse_filters(self.filter_edit.text())
            except QueryError as exc:
                self._set_status(f"error: {exc}")
                return
            self._set_status("searching…")
            self.search_button.setEnabled(False)
            self._worker = _SearchWorker(client, self.query_edit.text().strip(), filters)
            self._worker.done.connect(self._on_results)
            self._worker.failed.connect(self._on_failed)
            self._worker.finished.connect(lambda: self.search_button.setEnabled(True))
            self._worker.start()

        def _on_results(self, hits: list[Hit]) -> None:
            self._hits = hits
            self.table.setRowCount(len(hits))
            for row, hit in enumerate(hits):
                self.table.setItem(row, 0, QTableWidgetItem(hit.path))
                self.table.setItem(row, 1, QTableWidgetItem(str(hit.version)))
                self.table.setItem(row, 2, QTableWidgetItem(f"{hit.stored_bytes:,}"))
                self.table.setItem(row, 3, QTableWidgetItem(hit.title or ""))
            self._set_status(f"{len(hits)} result(s)" if hits else "no matches")

        def _on_failed(self, message: str) -> None:
            self._set_status(f"error: {message}")

        def _on_selection(self) -> None:
            rows = {i.row() for i in self.table.selectedItems()}
            if len(rows) != 1:
                return
            try:
                self.load_preview(rows.pop())
            except QueryError as exc:
                self._set_status(f"error: {exc}")

        def _on_browse(self) -> None:
            chosen = QFileDialog.getExistingDirectory(self, "Choose an archive directory")
            if chosen:
                self.root_edit.setText(chosen)

    return QueryPanel(root, parent=parent)
