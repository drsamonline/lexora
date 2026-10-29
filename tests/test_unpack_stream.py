"""Tests for the streaming decoder (container.unpack_stream / read_index_stream).

The streaming decode exists to bound memory on large archives, so its first
obligation is that it changes nothing about the bytes or the refusals: same
output as unpack(), same error codes, same zero-output-on-corruption guarantee
at the CLI boundary.
"""

from __future__ import annotations

import io
import pathlib

import pytest

from lexora import container
from lexora.cli import main as cli_main
from lexora.container import (
    ContainerError,
    pack,
    read_index,
    read_index_stream,
    unpack,
    unpack_stream,
)

GOLDEN_DIR = pathlib.Path(__file__).parent / "vectors" / "lxz_format"


def _decode_stream(archive: bytes, **kw) -> bytes:
    out = io.BytesIO()
    unpack_stream(io.BytesIO(archive), out, **kw)
    return out.getvalue()


@pytest.mark.parametrize("size", [0, 1, 7, 1024, 4096, 4097, 20000])
@pytest.mark.parametrize("block_size", [1024, 4096, 8 * 1024 * 1024])
def test_stream_decode_matches_buffered_unpack(size: int, block_size: int) -> None:
    data = bytes((i * 31 + 5) % 251 for i in range(size))
    archive = pack(data, block_size=block_size)
    assert _decode_stream(archive) == unpack(archive) == data


def test_stream_decode_reads_the_golden_vector() -> None:
    golden = (GOLDEN_DIR / "golden_1byte.lxz").read_bytes()
    assert _decode_stream(golden) == b"x"


def test_read_index_stream_agrees_with_read_index() -> None:
    archive = pack(b"index parity " * 5000, block_size=4096)
    a_info, a_off, a_len = read_index(archive)
    b_info, b_off, b_len = read_index_stream(io.BytesIO(archive))
    assert (a_off, a_len) == (b_off, b_len)
    assert a_info.total_uncompressed == b_info.total_uncompressed
    assert [(b.offset, b.compressed_size, b.uncompressed_size, b.sha256)
            for b in a_info.blocks] == [(b.offset, b.compressed_size, b.uncompressed_size, b.sha256)
                                        for b in b_info.blocks]


def test_only_block_parity_with_unpack() -> None:
    data = bytes(range(256)) * 200
    archive = pack(data, block_size=1024)
    for n in (0, 1, 5, len(read_index(archive)[0].blocks) - 1):
        assert _decode_stream(archive, only_block=n) == unpack(archive, only_block=n)


def test_only_block_out_of_range_is_refused() -> None:
    archive = pack(b"short", block_size=1024)
    with pytest.raises(ContainerError) as exc:
        _decode_stream(archive, only_block=7)
    assert exc.value.code == "E-FMT-IDX-006"


def test_corrupt_block_is_refused_by_streaming_decode() -> None:
    archive = bytearray(pack(b"integrity matters " * 500, block_size=512))
    archive[200] ^= 0xFF  # inside the first block's frame
    with pytest.raises(ContainerError) as exc:
        _decode_stream(bytes(archive))
    # depending on where the flipped byte lands the refusal is "not a zstd
    # frame", "decode failed" or "sha256 mismatch" — all three are refusals
    assert exc.value.code in {"E-INTEGRITY-001", "E-CMP-004", "E-CMP-003"}


def test_corrupt_header_is_refused_before_any_block_read() -> None:
    archive = bytearray(pack(b"header check " * 100))
    archive[20] ^= 0xFF  # inside the header's checksummed region
    with pytest.raises(ContainerError) as exc:
        _decode_stream(bytes(archive))
    assert exc.value.code == "E-FMT-HEAD-004"


def test_truncated_archive_is_refused() -> None:
    archive = pack(b"truncate me " * 200, block_size=1024)
    with pytest.raises(ContainerError):
        _decode_stream(archive[: len(archive) // 2])


def test_non_seekable_source_is_refused() -> None:
    class _NoSeek:
        def read(self, n=-1):
            return b""

    with pytest.raises(ContainerError) as exc:
        read_index_stream(_NoSeek())
    assert exc.value.code == "E-USAGE-004"


class TestCliStreamingUnpack:
    def _make(self, tmp_path, data: bytes) -> pathlib.Path:
        src = tmp_path / "in.bin"
        src.write_bytes(data)
        arc = tmp_path / "a.lxz"
        assert cli_main(["pack", "--in", str(src), "--out", str(arc),
                         "--level", "1", "--block-size", "4096"]) == 0
        return arc

    def test_stream_and_buffered_outputs_are_identical(self, tmp_path) -> None:
        data = bytes((i * 17) % 256 for i in range(60_000))
        arc = self._make(tmp_path, data)
        streamed = tmp_path / "s.out"
        buffered = tmp_path / "b.out"
        assert cli_main(["unpack", "--in", str(arc), "--out", str(streamed)]) == 0
        assert cli_main(["unpack", "--in", str(arc), "--out", str(buffered),
                         "--no-stream"]) == 0
        assert streamed.read_bytes() == buffered.read_bytes() == data

    def test_stdout_path_emits_the_payload(self, tmp_path, capsysbinary) -> None:
        data = b"stdout decode path " * 400
        arc = self._make(tmp_path, data)
        assert cli_main(["unpack", "--in", str(arc), "--out", "-"]) == 0
        assert capsysbinary.readouterr().out == data

    def test_stdout_path_emits_nothing_on_corruption(self, tmp_path, capsysbinary) -> None:
        """The temp-file staging is what keeps a refusal byte-silent on stdout."""
        data = b"never emit unverified bytes " * 300
        arc = self._make(tmp_path, data)
        tampered = bytearray(arc.read_bytes())
        tampered[300] ^= 0xFF
        arc.write_bytes(bytes(tampered))
        rc = cli_main(["unpack", "--in", str(arc), "--out", "-"])
        assert rc == cli_main.__globals__["EXIT_CONTAINER"]
        assert capsysbinary.readouterr().out == b""

    def test_refusal_leaves_no_output_file(self, tmp_path) -> None:
        data = b"no partial files " * 300
        arc = self._make(tmp_path, data)
        tampered = bytearray(arc.read_bytes())
        tampered[300] ^= 0xFF
        arc.write_bytes(bytes(tampered))
        out = tmp_path / "back.txt"
        assert cli_main(["unpack", "--in", str(arc), "--out", str(out)]) != 0
        assert not out.exists()

    def test_meta_is_index_only(self, tmp_path, capsys) -> None:
        import json

        arc = self._make(tmp_path, b"meta path " * 2000)  # 18 KB -> several 4 KiB blocks
        assert cli_main(["unpack", "--in", str(arc), "--meta"]) == 0
        meta = json.loads(capsys.readouterr().out)
        assert meta["format"] == "LXZ-0.1"
        assert len(meta["blocks"]) >= 2

    def test_streaming_leaves_no_temp_files(self, tmp_path) -> None:
        arc = self._make(tmp_path, b"temp hygiene " * 200)
        out = tmp_path / "out.bin"
        assert cli_main(["unpack", "--in", str(arc), "--out", str(out)]) == 0
        assert sorted(p.name for p in tmp_path.iterdir()) == ["a.lxz", "in.bin", "out.bin"]

    def test_only_block_cli(self, tmp_path) -> None:
        data = bytes(range(256)) * 100
        arc = self._make(tmp_path, data)
        info, _, _ = read_index(arc.read_bytes())
        out = tmp_path / "block0.bin"
        assert cli_main(["unpack", "--in", str(arc), "--out", str(out), "--block", "0"]) == 0
        assert out.read_bytes() == data[: info.blocks[0].uncompressed_size]


def test_container_module_exports_the_streaming_pair() -> None:
    assert callable(container.unpack_stream)
    assert callable(container.read_index_stream)
