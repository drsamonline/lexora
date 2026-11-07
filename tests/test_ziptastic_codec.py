"""Tests for the codec registry and the ziptastic (CHCE) adapter.

Two things are being proved here, and only one of them is about ziptastic.

1. **The seam works.** `container.pack(codec=...)` writes the chosen registry id
   into the header, the reader dispatches on that id, and an id this build does
   not know is still refused with E-CMP-006 — i.e. adding a codec did not quietly
   widen what the reader accepts.

2. **The adapter fails loudly.** The ziptastic binary is not vendored, so the
   interesting states are "binary missing", "binary is not ziptastic", "binary
   exits non-zero", "binary returns the wrong number of bytes". Each must raise
   CodecError with a message that says what to do. A silent fallback to zstd
   would produce an archive whose header lies about its codec, which is worse
   than refusing.

The stub binary is a tiny Python script that speaks the documented contract
(`c`/`d` filtering stdin to stdout, `CHCE` magic, `--version`). It is NOT a
stand-in for CHCE's ratio — nothing here asserts anything about compression
quality, because a stub cannot tell you that. The one test that needs the real
binary is marked skipif and says so when it skips.
"""

from __future__ import annotations

import io
import os
import stat
import zlib
from pathlib import Path

import pytest

from lexora import CODEC_ID_ZIPTASTIC, CODEC_ID_ZSTD
from lexora import codec_registry, container, ziptastic_core
from lexora.zstd_core import CodecError

STUB = '''#!{python}
"""Minimal stand-in for the ziptastic CLI (contract only, no real ratio)."""
import sys, zlib

def main(argv):
    args = [a for a in argv[1:] if not a.startswith("-")]
    if "--version" in argv:
        sys.stdout.write("ziptastic 0.0.0-stub (CHCE format v1)\\n")
        return 0
    mode = "c"
    if args:
        mode = args[0]
    data = sys.stdin.buffer.read()
    if mode in ("c", "compress"):
        sys.stdout.buffer.write(b"CHCE" + zlib.compress(data, 9))
        return 0
    if mode in ("d", "decompress"):
        if not data.startswith(b"CHCE"):
            sys.stderr.write("ziptastic: not a CHCE stream\\n")
            return 1
        sys.stdout.buffer.write(zlib.decompress(data[4:]))
        return 0
    sys.stderr.write("ziptastic: unknown command\\n")
    return 2

if __name__ == "__main__":
    sys.exit(main(sys.argv))
'''


@pytest.fixture()
def stub_binary(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    """A working fake ziptastic on $LEXORA_ZIPTASTIC."""
    path = tmp_path / "ziptastic"
    path.write_text(STUB.format(python=os.sys.executable))
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    monkeypatch.setenv(ziptastic_core.BINARY_ENV, str(path))
    ziptastic_core._version_cached.cache_clear()
    return str(path)


@pytest.fixture()
def no_binary(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(ziptastic_core.BINARY_ENV, raising=False)
    monkeypatch.setattr(ziptastic_core.shutil, "which", lambda _name: None)


# --------------------------------------------------------------------------- #
# registry
# --------------------------------------------------------------------------- #

def test_registry_ids_fit_the_header_field() -> None:
    for spec in codec_registry.SPECS:
        assert len(spec.registry_id.encode("ascii")) <= 16, spec


def test_registry_has_no_duplicate_ids_or_names() -> None:
    assert len({s.registry_id for s in codec_registry.SPECS}) == len(codec_registry.SPECS)
    assert len({s.name for s in codec_registry.SPECS}) == len(codec_registry.SPECS)


def test_registry_round_trips_both_ways() -> None:
    for spec in codec_registry.SPECS:
        assert codec_registry.by_name(spec.name) is spec
        assert codec_registry.by_registry_id(spec.registry_id) is spec


def test_default_codec_is_zstd() -> None:
    # The default must not move by accident: it decides what every archive
    # written without a flag contains.
    assert codec_registry.DEFAULT_CODEC == "zstd"
    assert codec_registry.DEFAULT_CODEC_ID == CODEC_ID_ZSTD


def test_unknown_codec_name_is_refused_with_the_list() -> None:
    with pytest.raises(codec_registry.UnknownCodec) as excinfo:
        codec_registry.by_name("lzma")
    assert "zstd" in str(excinfo.value) and "ziptastic" in str(excinfo.value)


def test_unknown_registry_id_is_refused() -> None:
    with pytest.raises(codec_registry.UnknownCodec):
        codec_registry.by_registry_id("lzma-fake")


def test_overlong_registry_id_is_a_construction_error() -> None:
    with pytest.raises(ValueError):
        codec_registry.CodecSpec(
            name="x", registry_id="a" * 17, magic=None,
            compress=lambda b, **k: b, decompress=lambda b, **k: b,
            validate_level=lambda level: None,
        )


# --------------------------------------------------------------------------- #
# adapter: failure modes come first
# --------------------------------------------------------------------------- #

def test_missing_binary_raises_with_guidance(no_binary: None) -> None:
    assert ziptastic_core.find_binary() is None
    assert ziptastic_core.available() is False
    with pytest.raises(CodecError) as excinfo:
        ziptastic_core.compress(b"hello")
    message = str(excinfo.value)
    assert ziptastic_core.BINARY_ENV in message
    assert "--codec zstd" in message


def test_binary_that_is_not_ziptastic_is_refused(tmp_path: Path,
                                                 monkeypatch: pytest.MonkeyPatch) -> None:
    # A wrong `ziptastic` on PATH is the realistic failure. It must not produce
    # an archive that cannot be decoded later.
    impostor = tmp_path / "ziptastic"
    impostor.write_text(f"#!{os.sys.executable}\nimport sys\n"
                        "sys.stdin.buffer.read()\nsys.stdout.buffer.write(b'not-chce')\n")
    impostor.chmod(0o755)
    monkeypatch.setenv(ziptastic_core.BINARY_ENV, str(impostor))
    with pytest.raises(CodecError) as excinfo:
        ziptastic_core.compress(b"payload")
    assert "CHCE" in str(excinfo.value)


def test_nonzero_exit_surfaces_stderr_tail(tmp_path: Path,
                                           monkeypatch: pytest.MonkeyPatch) -> None:
    failing = tmp_path / "ziptastic"
    failing.write_text(f"#!{os.sys.executable}\nimport sys\n"
                       "sys.stdin.buffer.read()\n"
                       "sys.stderr.write('out of memory\\n')\nsys.exit(3)\n")
    failing.chmod(0o755)
    monkeypatch.setenv(ziptastic_core.BINARY_ENV, str(failing))
    with pytest.raises(CodecError) as excinfo:
        ziptastic_core.compress(b"payload")
    assert "exited 3" in str(excinfo.value)
    assert "out of memory" in str(excinfo.value)


def test_decompress_refuses_a_wrong_size_hint(stub_binary: str) -> None:
    frame = ziptastic_core.compress(b"0123456789")
    with pytest.raises(CodecError) as excinfo:
        ziptastic_core.decompress(frame, expected_original_size=4)
    assert "refusing best-effort" in str(excinfo.value)


def test_decompress_refuses_a_non_chce_stream(stub_binary: str) -> None:
    with pytest.raises(CodecError):
        ziptastic_core.decompress(b"PK\x03\x04 not chce")


def test_numeric_level_that_is_not_a_preset_is_refused(stub_binary: str) -> None:
    # ziptastic has two presets, not a 1..22 scale. Rounding silently would put a
    # false level in the benchmark record.
    with pytest.raises(CodecError) as excinfo:
        ziptastic_core.compress(b"x", level=15)
    assert "presets" in str(excinfo.value)


def test_compress_rejects_str(stub_binary: str) -> None:
    with pytest.raises(CodecError):
        ziptastic_core.compress("text")  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# adapter: the happy path, and what it feeds the container
# --------------------------------------------------------------------------- #

def test_roundtrip_through_the_stub(stub_binary: str) -> None:
    payload = b"canonical text\n" * 500
    stats = ziptastic_core.verify_roundtrip(payload)
    assert stats["roundtrip_exact"] is True
    assert stats["codec_profile"] == "ziptastic-chce"
    assert "stub" in stats["library_version"]


def test_version_is_reported(stub_binary: str) -> None:
    assert ziptastic_core.version().startswith("ziptastic ")


def test_container_writes_the_chosen_codec_id(stub_binary: str) -> None:
    payload = b"the header must say what actually compressed this\n" * 40
    archive = container.pack(payload, codec="ziptastic", block_size=1024)
    info, _, _ = container.read_index(archive)
    assert info.codec_id == CODEC_ID_ZIPTASTIC
    assert info.codec_id != CODEC_ID_ZSTD
    assert container.unpack(archive) == payload


def test_container_stream_path_matches_buffered_path_for_the_new_codec(
        stub_binary: str) -> None:
    payload = b"stream parity " * 400
    out = io.BytesIO()
    container.pack_stream(io.BytesIO(payload), out, codec="ziptastic", block_size=512)
    assert out.getvalue() == container.pack(payload, codec="ziptastic", block_size=512)


def test_verify_accepts_a_ziptastic_archive(stub_binary: str) -> None:
    archive = container.pack(b"verify me\n" * 100, codec="ziptastic", block_size=256)
    result = container.verify_archive(archive)
    assert result.ok is True
    assert all(block_ok for _, block_ok, _ in result.blocks)


def test_default_pack_is_still_byte_identical_zstd() -> None:
    # The new parameter must not change one byte of what a default pack produces.
    payload = b"default must not move\n" * 64
    assert container.pack(payload) == container.pack(payload, codec="zstd")
    assert container.pack(payload) == container.pack(payload, level=9)


def test_unknown_codec_on_pack_is_a_usage_refusal() -> None:
    with pytest.raises(container.ContainerError) as excinfo:
        container.pack(b"x", codec="lzma")
    assert excinfo.value.code == "E-USAGE-004"


def test_reader_still_refuses_an_unknown_header_codec(stub_binary: str) -> None:
    # Build a valid archive, then relabel the header as a codec we do not have.
    # The reader must refuse it rather than guess.
    import hashlib

    archive = bytearray(container.pack(b"relabel me\n" * 20, block_size=128))
    archive[16:32] = b"lzma-fake".ljust(16, b"\x00")
    archive[96:128] = hashlib.sha256(bytes(archive[:96])).digest()
    with pytest.raises(container.ContainerError) as excinfo:
        container.read_index(bytes(archive))
    assert excinfo.value.code == "E-CMP-006"


def test_unpack_without_the_binary_names_the_codec_not_a_crash(
        stub_binary: str, monkeypatch: pytest.MonkeyPatch) -> None:
    archive = container.pack(b"packed with chce\n" * 30, codec="ziptastic", block_size=128)
    # Simulate the archive arriving on a machine that has no ziptastic installed.
    monkeypatch.delenv(ziptastic_core.BINARY_ENV, raising=False)
    monkeypatch.setattr(ziptastic_core.shutil, "which", lambda _name: None)
    with pytest.raises(container.ContainerError) as excinfo:
        container.unpack(archive)
    assert excinfo.value.code == "E-CMP-004"
    assert "ziptastic" in excinfo.value.message


def test_cli_pack_codec_flag_reaches_the_header(stub_binary: str, tmp_path: Path) -> None:
    from lexora import cli

    src = tmp_path / "in.txt"
    src.write_bytes(b"cli codec selection\n" * 50)
    out = tmp_path / "out.lxz"
    assert cli.main(["pack", "--in", str(src), "--out", str(out),
                     "--codec", "ziptastic", "--block-size", "512"]) == cli.EXIT_OK
    info, _, _ = container.read_index(out.read_bytes())
    assert info.codec_id == CODEC_ID_ZIPTASTIC


# --------------------------------------------------------------------------- #
# the real binary, when it exists
# --------------------------------------------------------------------------- #

REAL = ziptastic_core.shutil.which("ziptastic")


@pytest.mark.skipif(REAL is None,
                    reason="the real ziptastic binary is not installed here; the "
                           "adapter's contract is covered by the stub, but its ratio "
                           "and throughput are not (see ADR-0014)")
def test_real_binary_roundtrip(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(ziptastic_core.BINARY_ENV, REAL)
    payload = ("The quick brown fox jumps over the lazy dog. " * 200).encode()
    stats = ziptastic_core.verify_roundtrip(payload)
    assert stats["roundtrip_exact"] is True
    assert stats["stored_bytes"] < len(payload)


# --------------------------------------------------------------------------- #
# audit finding: a bounded decode must name the block the caller asked for
# --------------------------------------------------------------------------- #

def test_only_block_failure_reports_the_absolute_index() -> None:
    """`unpack --block N` used to report "block 0" for any N.

    The loop enumerated the *selected* list rather than the archive's block
    indices, so the one number a caller can act on was replaced by the position
    within a one-element selection. Found by audit 2026-11-07.
    """
    payload = b"0123456789abcdef" * 64
    archive = bytearray(container.pack(payload, block_size=256))
    info, _, _ = container.read_index(bytes(archive))
    assert len(info.blocks) >= 3
    target = 2
    # Corrupt the target block's stored bytes so its decode cannot match.
    entry = info.blocks[target]
    archive[entry.offset:entry.offset + 8] = b"\x00" * 8
    with pytest.raises(container.ContainerError) as excinfo:
        container.unpack(bytes(archive), only_block=target)
    assert f"block {target}" in excinfo.value.message
    assert "block 0" not in excinfo.value.message
