"""Tests for `lexora doctor` — the install-health report.

Doctor's value is that a bug report can carry facts instead of guesses, so the tests
care about three things: the checks exist and are honest about their statuses, the
report never claims health it has not verified, and the exit code reflects what the
report says (0 healthy, 1 attention needed).
"""

from __future__ import annotations

import json
import pathlib

import pytest

from lexora import cli, doctor


def test_report_is_healthy_on_a_working_install() -> None:
    report = doctor.run_checks()
    names = [c["check"] for c in report["checks"]]
    assert "python" in names and "zstandard" in names and "round trip" in names
    assert report["failures"] == 0
    assert report["healthy"] is True


def test_the_round_trip_check_actually_round_trips() -> None:
    """The one check that answers 'does this install work?' rather than 'does the
    metadata look right?' — it must be present and passing, not decorative."""
    report = doctor.run_checks()
    rt = next(c for c in report["checks"] if c["check"] == "round trip")
    assert rt["status"] == doctor.OK
    assert "original bytes" in rt["detail"]


def test_gui_extra_is_reported_without_being_a_failure() -> None:
    report = doctor.run_checks()
    gui = next(c for c in report["checks"] if c["check"] == "gui extra")
    # ok when PySide6 is installed, informational when not — never a failure,
    # because the GUI is an optional extra (ADR-0008)
    assert gui["status"] in (doctor.OK, doctor.INFO)


def test_corpus_directories_are_reported_as_facts(tmp_path) -> None:
    (tmp_path / "corpus" / "gutenberg").mkdir(parents=True)
    (tmp_path / "corpus" / "gutenberg" / "a.txt").write_bytes(b"x" * 2048)
    report = doctor.run_checks(repo_root=tmp_path)
    corpus = next(c for c in report["checks"] if "tier-1" in c["check"])
    assert corpus["status"] == doctor.INFO
    assert "1 file(s)" in corpus["detail"]
    owner = next(c for c in report["checks"] if "owner corpus" in c["check"])
    assert owner["detail"] == "absent"


def test_absent_corpus_never_makes_the_report_unhealthy(tmp_path) -> None:
    report = doctor.run_checks(repo_root=tmp_path)
    assert report["healthy"] is True  # data is not health


def test_config_directory_follows_xdg(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    report = doctor.run_checks()
    cfg = next(c for c in report["checks"] if c["check"] == "config directory")
    assert cfg["detail"] == str(tmp_path / "cfg" / "lexora")


def test_a_failing_check_makes_the_report_unhealthy_and_changes_the_exit_code(
    monkeypatch, capsys
) -> None:
    monkeypatch.setattr(doctor, "MIN_PYTHON", (99, 0))  # force the python check to fail
    report = doctor.run_checks()
    assert report["healthy"] is False
    assert report["failures"] >= 1
    assert cli.main(["doctor"]) == cli.EXIT_PARTIAL
    assert "attention needed" in capsys.readouterr().out


def test_format_report_lists_every_check_with_a_status() -> None:
    report = doctor.run_checks()
    text = doctor.format_report(report)
    for c in report["checks"]:
        assert c["check"] in text
    assert "healthy: no failures, no warnings" in text
    assert text.splitlines()[0].startswith("check")  # header row


def test_json_matches_the_library_report(capsys) -> None:
    assert cli.main(["doctor", "--json"]) == cli.EXIT_OK
    printed = json.loads(capsys.readouterr().out)
    assert printed == doctor.run_checks()
    assert set(printed) == {"healthy", "failures", "warnings", "checks"}


def test_text_mode_writes_nothing_to_stderr(tmp_path, capsys) -> None:
    assert cli.main(["doctor"]) == cli.EXIT_OK
    captured = capsys.readouterr()
    assert captured.err == ""
    assert "healthy" in captured.out
