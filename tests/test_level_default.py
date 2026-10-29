"""One source of truth for the default encode level.

Session 53 found the three surfaces disagreeing: the CLI and library defaulted to
19, the GUI settings default was hardcoded 3, and a comment claimed the GUI value
"matches the CLI `pack --level` default". They are now pinned to
`lexora.DEFAULT_LEVEL`, and these tests are what keep them pinned — a drift here
is invisible until someone compares two archives produced by different surfaces.
"""

from __future__ import annotations

import io

from lexora import DEFAULT_LEVEL
from lexora import cli, container
from lexora.gui.service import DEFAULT_SETTINGS


def test_default_level_is_documented_and_in_range() -> None:
    assert isinstance(DEFAULT_LEVEL, int)
    assert 1 <= DEFAULT_LEVEL <= 22
    # Session 53 chose 9 from the measured sweep; changing it should be deliberate
    assert DEFAULT_LEVEL == 9


def test_library_defaults_follow_the_constant() -> None:
    data = b"level default parity " * 100
    assert container.pack(data) == container.pack(data, level=DEFAULT_LEVEL)
    out_a, out_b = io.BytesIO(), io.BytesIO()
    container.pack_stream(io.BytesIO(data), out_a)
    container.pack_stream(io.BytesIO(data), out_b, level=DEFAULT_LEVEL)
    assert out_a.getvalue() == out_b.getvalue() == container.pack(data)


def test_cli_parsers_follow_the_constant() -> None:
    parser = cli.build_parser()
    # every subcommand that takes --level must agree with the library default
    for argv, expect in (
        (["zround", "--in", "x"], DEFAULT_LEVEL),
        (["pipe", "--in", "x", "--out", "y"], DEFAULT_LEVEL),
        (["pack", "--in", "x", "--out", "y"], DEFAULT_LEVEL),
        (["batch", "--in", "x", "--out-dir", "y"], DEFAULT_LEVEL),
    ):
        args = parser.parse_args(argv)
        assert args.level == expect, f"{argv[0]} default level drifted"


def test_gui_settings_default_follows_the_constant() -> None:
    assert DEFAULT_SETTINGS["level"] == DEFAULT_LEVEL


def test_cli_pack_with_no_level_matches_the_library_default(tmp_path) -> None:
    payload = tmp_path / "in.bin"
    payload.write_bytes(b"cli default level " * 200)
    out = tmp_path / "a.lxz"
    assert cli.main(["pack", "--in", str(payload), "--out", str(out)]) == cli.EXIT_OK
    assert out.read_bytes() == container.pack(payload.read_bytes())
