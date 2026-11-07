"""An out-of-range `--level` is a usage error (exit 2) on every surface — ADR-0018.

Before this, the same input produced two answers:

    lexora pack --level 99          -> 5  (codec error)
    AppService.run_pack(level=99)   -> 2  (usage error)

and `service.py`'s own comment claimed the GUI "mirrors `lexora pack --level`".
The CLI was the odd one out: the same command already returns 2 for an
out-of-range `--block-size`, and exit 5 asserts "the codec failed" when the codec
was never given a valid level to fail on.

These tests exist so the two surfaces cannot drift apart again without a red run.
"""

from __future__ import annotations

import io

import pytest

from lexora import cli


@pytest.mark.parametrize("argv", [
    ["pack", "--in", "x", "--out", "y"],
    ["batch", "--in", "x", "--out-dir", "y", "--op", "pack"],
    ["zround", "--in", "x"],
    ["pipe", "--in", "x", "--out", "y"],
])
@pytest.mark.parametrize("level", ["0", "23", "99", "-1"])
def test_out_of_range_level_is_a_usage_error_everywhere(argv, level, tmp_path,
                                                       capsys) -> None:
    src = tmp_path / "x"
    src.write_bytes(b"payload\n")
    real = [str(src) if a == "x" else (str(tmp_path / "out") if a == "y" else a)
            for a in argv]
    assert cli.main([*real, "--level", level]) == 2
    assert "usage error" in capsys.readouterr().err


@pytest.mark.parametrize("level", ["1", "9", "19", "22"])
def test_valid_zstd_levels_still_work(level, tmp_path) -> None:
    src = tmp_path / "in.txt"
    src.write_bytes(b"payload\n")
    out = tmp_path / "out.lxz"
    assert cli.main(["pack", "--in", str(src), "--out", str(out),
                     "--level", level]) == cli.EXIT_OK


def test_ziptastic_presets_are_enforced_at_the_boundary(tmp_path, capsys) -> None:
    """CHCE has two presets, not a scale — 15 is a usage error, 19 is legal."""
    src = tmp_path / "in.txt"
    src.write_bytes(b"payload\n")
    out = tmp_path / "out.lxz"
    assert cli.main(["pack", "--in", str(src), "--out", str(out),
                     "--level", "15", "--codec", "ziptastic"]) == 2
    assert "presets" in capsys.readouterr().err


def test_gui_and_cli_agree_on_the_exit_code_for_a_bad_level(tmp_path) -> None:
    """The parity claim ADR-0011 relies on, asserted rather than assumed."""
    from lexora.gui.service import AppService

    src = tmp_path / "in.txt"
    src.write_bytes(b"payload\n")
    cli_code = cli.main(["pack", "--in", str(src), "--out", str(tmp_path / "o.lxz"),
                         "--level", "99"])
    gui_code = AppService().run_pack(b"payload\n", level=99).exit_code
    assert cli_code == gui_code == 2


def test_block_size_and_level_now_agree_within_one_command(tmp_path, capsys) -> None:
    """The inconsistency that decided ADR-0018: two bad flags, one command, one code."""
    src = tmp_path / "in.txt"
    src.write_bytes(b"payload\n")
    out = tmp_path / "o.lxz"
    bs = cli.main(["pack", "--in", str(src), "--out", str(out), "--block-size", "0"])
    lvl = cli.main(["pack", "--in", str(src), "--out", str(out), "--level", "99"])
    assert bs == lvl == 2
