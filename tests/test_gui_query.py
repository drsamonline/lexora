"""Offscreen tests for the query view (ADR-0011: the GUI is a CLI client).

These run without a display via `QT_QPA_PLATFORM=offscreen` and skip cleanly when
PySide6 is absent, which is the honest state for a base install — the GUI is an
optional extra.

What is asserted is the part that can silently rot: that the panel and the CLI agree
(the parity rule), that a failure shows a message instead of raising into the event
loop, and that the preview decodes only the document that was selected.
"""

from __future__ import annotations

import os
import pathlib
import sys

import pytest

pytest.importorskip("PySide6", reason="the [gui] extra is not installed")

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from lexora import cli  # noqa: E402
from lexora.gui.query import Hit, QueryClient, QueryError, build_panel  # noqa: E402

REPO = pathlib.Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication(sys.argv[:1])
    yield app


@pytest.fixture()
def archive(tmp_path: pathlib.Path, qapp) -> str:
    """A real catalog built through the CLI — the same path a user takes."""
    root = str(tmp_path / "db")
    cli.main(["db", "init", "--root", root])
    docs = {
        "whale.txt": b"the whale surfaced near the ship and sounded\n",
        "ship.txt": b"the ship held its course through the night\n",
        "harbour.txt": b"the harbour was quiet all winter\n",
    }
    for name, body in docs.items():
        src = tmp_path / name
        src.write_bytes(body)
        assert cli.main(["db", "add", "--root", root, "--in", str(src),
                         "--path", name, "--title", name.upper(),
                         "--meta", "lang=en"]) == cli.EXIT_OK
    return root


# --------------------------------------------------------------------------- #
# the client
# --------------------------------------------------------------------------- #

def test_client_search_returns_hits(archive: str) -> None:
    hits = QueryClient(archive).search("whale")
    assert [h.path for h in hits] == ["whale.txt"]
    assert isinstance(hits[0], Hit)
    assert hits[0].stored_bytes > 0 and hits[0].title == "WHALE.TXT"


def test_client_filter_narrows_results(archive: str) -> None:
    client = QueryClient(archive)
    assert len(client.search("ship")) == 2
    assert len(client.search("ship", filters={"lang": "fr"})) == 0
    assert len(client.search("ship", filters={"lang": "en"})) == 2


def test_client_get_text_returns_the_document(archive: str) -> None:
    assert "harbour" in QueryClient(archive).get_text("harbour.txt")


def test_client_stats_reports_the_catalog(archive: str) -> None:
    stats = QueryClient(archive).stats()
    assert stats["live_documents"] == 3


def test_client_raises_the_cli_message_not_a_generic_error(tmp_path: pathlib.Path) -> None:
    """The CLI's own refusal text must reach the user — that is the whole point."""
    with pytest.raises(QueryError) as excinfo:
        QueryClient(str(tmp_path / "nope")).search("x")
    assert "db init" in str(excinfo.value)


# --------------------------------------------------------------------------- #
# the panel
# --------------------------------------------------------------------------- #

def test_panel_search_populates_the_table(archive: str, qapp) -> None:
    panel = build_panel(archive)
    hits = panel.run_search("whale")
    assert len(hits) == 1
    assert panel.table.rowCount() == 1
    assert panel.table.item(0, 0).text() == "whale.txt"
    assert panel.table.item(0, 1).text() == "1"
    assert "1 result" in panel.status.text()


def test_panel_with_no_matches_says_so(archive: str, qapp) -> None:
    panel = build_panel(archive)
    assert panel.run_search("pterodactyl") == []
    assert panel.table.rowCount() == 0
    assert "no matches" in panel.status.text()


def test_panel_filter_box_is_parsed(archive: str, qapp) -> None:
    panel = build_panel(archive)
    panel.filter_edit.setText("lang=en")
    assert len(panel.run_search("ship")) == 2
    panel.filter_edit.setText("lang=fr")
    assert panel.run_search("ship") == []


def test_panel_rejects_a_malformed_filter(archive: str, qapp) -> None:
    panel = build_panel(archive)
    panel.filter_edit.setText("lang")
    with pytest.raises(QueryError):
        panel.run_search("ship")


def test_preview_decodes_only_the_selected_document(archive: str, qapp) -> None:
    """The reason a compressed archive is queryable at all: decode one document."""
    panel = build_panel(archive)
    panel.run_search("ship")
    text = panel.load_preview(0)
    assert "ship" in text.lower()
    # the other matching document's text must not be in the preview
    other = "whale" if "whale" not in text.lower() else "harbour"
    assert other not in text.lower()


def test_panel_shows_an_error_instead_of_raising_when_the_archive_is_missing(
        tmp_path: pathlib.Path, qapp) -> None:
    panel = build_panel(str(tmp_path / "absent"))
    with pytest.raises(QueryError):
        panel.run_search("x")
    # and the slot path swallows it into the status line
    panel._on_search_clicked()
    assert "error:" in panel.status.text()


def test_panel_requires_an_archive(archive: str, qapp) -> None:
    panel = build_panel("")
    with pytest.raises(QueryError) as excinfo:
        panel.run_search("x")
    assert "archive" in str(excinfo.value).lower()


def test_panel_and_cli_agree(archive: str, qapp) -> None:
    """Parity rule (ADR-0011): the GUI must not become a second implementation."""
    import json
    import subprocess

    proc = subprocess.run(
        [sys.executable, "-m", "lexora.cli", "db", "search", "--root", archive,
         "--query", "ship", "--json"],
        capture_output=True, text=True,
        env={**os.environ, "PYTHONPATH": str(REPO / "src") + os.pathsep + os.environ.get("PYTHONPATH", "")},
    )
    assert proc.returncode == 0, proc.stderr
    from_cli = [h["path"] for h in json.loads(proc.stdout)]
    from_gui = [h.path for h in build_panel(archive).run_search("ship")]
    assert from_gui == from_cli


def test_main_window_offers_the_query_view_and_opens_it(qapp) -> None:
    """The panel must be reachable from the app, not just importable."""
    from PySide6.QtWidgets import QApplication, QPushButton

    from lexora.gui.app import build_window

    win = build_window()
    buttons = {b.text(): b for b in win.findChildren(QPushButton)}
    assert "Query archive…" in buttons, sorted(buttons)

    buttons["Query archive…"].click()
    titles = {w.windowTitle() for w in QApplication.topLevelWidgets()}
    assert "LEXORA — query archive" in titles
