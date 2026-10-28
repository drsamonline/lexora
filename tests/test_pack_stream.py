"""Tests for the streaming encoder (container.pack_stream + CLI wiring).

The streaming path exists to bound memory (see benchmarks/results-rss-core.json),
so its first obligation is that it changes NOTHING about the bytes: the frozen
LXZ-0.1 layout must come out identical to container.pack() for every input.
"""

from __future__ import annotations

import hashlib
import io
import pathlib

import pytest

from lexora import container
from lexora.cli import main as cli_main
from lexora.container import ContainerError, pack, pack_stream, unpack

GOLDEN_DIR = pathlib.Path(__file__).parent / "vectors" / "lxz_format"


def _pack_stream_bytes(data: bytes, **kw) -> bytes:
    out = io.BytesIO()
    pack_stream(io.BytesIO(data), out, **kw)
    return out.getvalue()


class _NonSeekable:
    def __init__(self) -> None:
        self.buf = bytearray()

    def write(self, b) -> int:
        self.buf += b
        return len(b)

    def flush(self) -> None:
        pass


@pytest.mark.parametrize("size", [0, 1, 7, 1024, 4096, 4097, 8192, 20000])
@pytest.mark.parametrize("block_size", [1024, 4096, 8 * 1024 * 1024])
def test_stream_is_byte_identical_to_pack(size: int, block_size: int) -> None:
    data = bytes((i * 37 + 11) % 251 for i in range(size))
    assert _pack_stream_bytes(data, block_size=block_size) == pack(data, block_size=block_size)


def test_stream_reproduces_the_golden_vector() -> None:
    """The pinned LXZ-0.1 golden vector must be produced by the streaming writer."""
    golden = (GOLDEN_DIR / "golden_1byte.lxz").read_bytes()
    streamed = _pack_stream_bytes(b"x", level=19, generator_version="lexora-golden")
    assert streamed == golden
    assert hashlib.sha256(streamed).hexdigest() == hashlib.sha256(golden).hexdigest()


def test_stream_generator_version_truncation_matches_pack() -> None:
    data = b"hello lexora" * 100
    long_gen = "a-very-long-generator-version-string"
    assert _pack_stream_bytes(data, generator_version=long_gen) == pack(
        data, generator_version=long_gen
    )


def test_stream_output_round_trips_through_unpack() -> None:
    data = b"the quick brown fox " * 5000
    archive = _pack_stream_bytes(data, block_size=4096)
    assert unpack(archive) == data
    info, _, _ = container.read_index(archive)
    assert len(info.blocks) == -(-len(data) // 4096)
    assert info.total_uncompressed == len(data)


def test_stream_empty_input_is_one_empty_block() -> None:
    archive = _pack_stream_bytes(b"")
    info, _, _ = container.read_index(archive)
    assert len(info.blocks) == 1
    assert info.blocks[0].uncompressed_size == 0
    assert unpack(archive) == b""


def test_stream_rejects_non_seekable_destination() -> None:
    with pytest.raises(ContainerError) as exc:
        pack_stream(io.BytesIO(b"data"), _NonSeekable())
    assert exc.value.code == "E-USAGE-003"


def test_stream_rejects_bad_block_size() -> None:
    with pytest.raises(ContainerError) as exc:
        pack_stream(io.BytesIO(b"data"), io.BytesIO(), block_size=0)
    assert exc.value.code == "E-USAGE-002"


def test_stream_enforces_archive_ceiling() -> None:
    with pytest.raises(ContainerError) as exc:
        pack_stream(io.BytesIO(b"x" * 5000), io.BytesIO(),
                    block_size=1024, max_total_uncompressed=4096)
    assert exc.value.code == "E-RES-003"


def test_stream_enforces_block_compressed_ceiling() -> None:
    # incompressible-ish payload with a 1-byte compressed ceiling
    with pytest.raises(ContainerError) as exc:
        pack_stream(io.BytesIO(b"x" * 4096), io.BytesIO(),
                    block_size=4096, max_block_compressed=1)
    assert exc.value.code == "E-RES-002"


def test_header_builder_is_shared_by_both_writers() -> None:
    """pack() and pack_stream() must agree on the header, byte for byte."""
    data = b"shared header check" * 64
    assert pack(data, block_size=256)[:128] == _pack_stream_bytes(data, block_size=256)[:128]


class TestCliStreaming:
    def test_cli_default_is_streaming_and_byte_identical_to_buffered(self, tmp_path) -> None:
        src = tmp_path / "in.bin"
        data = bytes((i * 13) % 256 for i in range(50_000))
        src.write_bytes(data)
        streamed = tmp_path / "streamed.lxz"
        buffered = tmp_path / "buffered.lxz"
        assert cli_main(["pack", "--in", str(src), "--out", str(streamed)]) == 0
        assert cli_main(["pack", "--in", str(src), "--out", str(buffered),
                         "--no-stream"]) == 0
        assert streamed.read_bytes() == buffered.read_bytes()
        assert streamed.read_bytes() == pack(data)

    def test_cli_stream_path_leaves_no_temp_files(self, tmp_path) -> None:
        src = tmp_path / "in.bin"
        src.write_bytes(b"temp file hygiene" * 1000)
        out = tmp_path / "out.lxz"
        assert cli_main(["pack", "--in", str(src), "--out", str(out)]) == 0
        assert sorted(p.name for p in tmp_path.iterdir()) == ["in.bin", "out.lxz"]

    def test_cli_stdout_path_still_works(self, tmp_path, capsysbinary) -> None:
        src = tmp_path / "in.bin"
        data = b"stdout path" * 500
        src.write_bytes(data)
        assert cli_main(["pack", "--in", str(src), "--out", "-"]) == 0
        captured = capsysbinary.readouterr()
        assert unpack(captured.out) == data
