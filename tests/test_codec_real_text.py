"""Every shipped codec, round-tripped over real varied text — the fix for the PPMd mistake.

Regeneration recipe (only when the corpus changes)::

    python3 - <<'EOF'
    import pathlib
    from lexora.canonicalize import canonicalize
    parts = []
    for f in sorted(pathlib.Path("corpus-big").glob("pg*.txt")):
        d = canonicalize(f.read_bytes())
        if len(d) >= 8192 * 3:
            parts.append(d[len(d)//2 : len(d)//2 + 8192])
    pathlib.Path("tests/vectors/real_text/gutenberg_slices.txt").write_bytes(b"\\n".join(parts))
    EOF

Why this file exists
--------------------
The `ppmd` codec shipped and was withdrawn the same day: `pyppmd` corrupted 3–8 % of real
documents (ADR-0021). The test that let it through packed **one sentence repeated 400 times** —
the input least likely to expose a model-state bug. Every codec now has to survive 720 KB of
88 different books, plus adversarial inputs, at several block sizes.

What this test can and cannot catch is stated in the fixture's README rather than implied.
"""

from __future__ import annotations

import importlib.util
import pathlib

import pytest

from lexora import codec_registry, container, ziptastic_core

FIXTURE = pathlib.Path(__file__).parent / "vectors" / "real_text" / "gutenberg_slices.txt"
FIXTURE_SHA256 = "9a4c666970a1114e0667885c2679cdd00fb0f6c0b53f599692ca452327d7ad96"

# Inputs that are not prose but must still round-trip exactly. Generated, not committed.
def _adversarial() -> dict[str, bytes]:
    return {
        "empty": b"",
        "one_byte": b"x",
        "all_byte_values": bytes(range(256)) * 64,
        "nul_heavy": b"\x00" * 4096,
        "long_single_line": b"a" * 200_000,
        "crlf_text": b"line one\r\nline two\r\n" * 2000,
        "devanagari": "नमस्ते दुनिया। यह एक परीक्षण है।\n".encode() * 500,
        "cjk": "天地玄黄，宇宙洪荒。日本語のテキスト。\n".encode() * 500,
        "mixed_script": ("Latin, देवनागरी, 中文, العربية, Ελληνικά.\n" * 400).encode(),
        "high_entropy": bytes((i * 37 + 11) % 256 for i in range(50_000)),
    }


def _codecs() -> list[str]:
    """Every registered codec whose external dependency is present."""
    names = []
    for name in codec_registry.names():
        if name == "ziptastic" and not ziptastic_core.available():
            continue
        names.append(name)
    return names


@pytest.fixture(scope="module")
def real_text() -> bytes:
    assert FIXTURE.exists(), f"fixture missing: {FIXTURE}"
    data = FIXTURE.read_bytes()
    import hashlib

    assert hashlib.sha256(data).hexdigest() == FIXTURE_SHA256, (
        "the real-text fixture changed — regenerate deliberately (recipe in the module docstring)"
    )
    return data


def test_the_fixture_is_actually_varied(real_text: bytes) -> None:
    """A fixture that is not varied is the bug this file exists to prevent.

    Asserts the properties that made the old single-sentence fixture useless: distinct
    vocabulary, non-ASCII content, and enough size to cross a default block boundary.
    """
    assert len(real_text) > 500_000, "fixture too small to be realistic"
    words = set(real_text.split())
    assert len(words) > 15_000, f"only {len(words)} distinct words — not varied enough"
    assert sum(1 for b in real_text if b > 127) > 5_000, "no meaningful non-ASCII content"
    # Big enough that a small block size forces several blocks (see the multi-block test).
    assert len(real_text) > 512_000


@pytest.mark.parametrize("codec", _codecs())
def test_real_text_round_trips_exactly(codec: str, real_text: bytes) -> None:
    """The test that would have caught PPMd before it reached main."""
    archive = container.pack(real_text, codec=codec)
    info, _, _ = container.read_index(archive)
    assert info.codec_id == codec_registry.by_name(codec).registry_id
    assert container.unpack(archive) == real_text, f"{codec} corrupted real text"
    assert container.verify_archive(archive).ok is True


@pytest.mark.parametrize("codec", _codecs())
# Both sizes force >1 block over a ~700 KB fixture; 1 MiB would not.
@pytest.mark.parametrize("block_size", [64 * 1024, 256 * 1024])
def test_multi_block_archives_round_trip(codec: str, block_size: int,
                                         real_text: bytes) -> None:
    """Multi-block paths are where per-block state bugs live; one block hides them."""
    archive = container.pack(real_text, codec=codec, block_size=block_size)
    info, _, _ = container.read_index(archive)
    assert len(info.blocks) > 1, "expected a multi-block archive"
    assert container.unpack(archive) == real_text


@pytest.mark.parametrize("codec", _codecs())
@pytest.mark.parametrize("name", sorted(_adversarial()))
def test_adversarial_inputs_round_trip(codec: str, name: str) -> None:
    data = _adversarial()[name]
    archive = container.pack(data, codec=codec)
    assert container.unpack(archive) == data, f"{codec} corrupted {name}"


@pytest.mark.parametrize("codec", _codecs())
def test_a_single_flipped_bit_is_never_silently_accepted(codec: str, real_text: bytes) -> None:
    """Corruption must be refused, not decoded into plausible text.

    The PPMd failure mode was exactly this: wrong bytes, no error. The container's
    per-block SHA-256 is the backstop, and this asserts it holds for every codec.
    """
    archive = bytearray(container.pack(real_text, codec=codec, block_size=64 * 1024))
    archive[200] ^= 0x01                      # inside the first block's payload
    with pytest.raises(container.ContainerError):
        container.unpack(bytes(archive))


def test_the_known_bad_library_is_still_absent() -> None:
    """If pyppmd is installed for benchmarking, it still must not be a shipped codec."""
    assert "ppmd" not in codec_registry.names()
    if importlib.util.find_spec("pyppmd") is not None:  # pragma: no cover - dev extra
        # The withdrawal record, not this test, is what explains why (ADR-0021).
        assert all(spec.registry_id != "ppmd-1" for spec in codec_registry.SPECS)
