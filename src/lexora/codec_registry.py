"""Codec registry: the one place that maps a header `codec_id` to an implementation.

ADR-0002 said the `codec_id` space holds Zstd plus promoted candidates, and
ADR-0007 froze v0's reader to hard-refuse any id it does not know (E-CMP-006).
This module is the list of ids that are no longer unknown, and the single
dispatch point for compress/decompress, so `container.py` stops hard-coding zstd
in five separate places.

Adding an entry is a **reader-visible** change: an archive written with a new
codec is refused by every older reader, which is the designed behaviour and not a
bug. That is why each new entry needs an ADR (see ADR-0014), not just a row here.

`magic` is the structural prefix a stored block must start with. It is a cheap
sanity check, not a security boundary — per-block SHA-256 is the boundary. It
exists so a mislabelled block fails with "not a <codec> frame" instead of a
confusing decode error from deep inside a third-party decoder.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from lexora import (CODEC_ID_PPMD, CODEC_ID_ZIPTASTIC, CODEC_ID_ZSTD,
                    CODEC_ID_ZSTD_LEGACY_L19)
from lexora import ppmd_core, ziptastic_core, zstd_core

# Zstd frame magic, little-endian 0xFD2FB528.
ZSTD_MAGIC = b"\x28\xb5\x2f\xfd"

DEFAULT_CODEC = "zstd"


class UnknownCodec(Exception):
    """A codec name (CLI) or registry id (header) that this build does not know."""


@dataclass(frozen=True)
class CodecSpec:
    """One registered codec.

    `name` is the CLI-facing name; `registry_id` is what is written into
    `codec_id[16]` and is therefore frozen once an archive using it exists.
    """

    name: str
    registry_id: str
    magic: bytes | None
    compress: Callable[..., bytes]
    decompress: Callable[..., bytes]
    #: Returns an error message when a level is illegal for this codec, else None.
    #: Defined by the codec module, called by the CLI at the boundary (ADR-0018).
    validate_level: Callable[[int], str | None]
    #: Registry ids this codec used to write. Read-only: `by_registry_id` maps them to
    #: this spec so old archives decode, but nothing ever writes them again (ADR-0020).
    legacy_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        # The header field is 16 bytes NUL-padded; a longer id would be silently
        # truncated on write and unreadable on read.
        if len(self.registry_id.encode("ascii")) > 16:
            raise ValueError(
                f"codec registry id {self.registry_id!r} exceeds the 16-byte "
                "codec_id header field"
            )


SPECS: tuple[CodecSpec, ...] = (
    CodecSpec(
        name="zstd",
        registry_id=CODEC_ID_ZSTD,
        magic=ZSTD_MAGIC,
        compress=zstd_core.compress,
        decompress=zstd_core.decompress,
        validate_level=zstd_core.validate_level,
        legacy_ids=(CODEC_ID_ZSTD_LEGACY_L19,),
    ),
    CodecSpec(
        name="ziptastic",
        registry_id=CODEC_ID_ZIPTASTIC,
        magic=ziptastic_core.MAGIC,
        compress=ziptastic_core.compress,
        decompress=ziptastic_core.decompress,
        validate_level=ziptastic_core.validate_level,
    ),
    CodecSpec(
        name="ppmd",
        registry_id=CODEC_ID_PPMD,
        magic=ppmd_core.MAGIC,
        compress=ppmd_core.compress,
        decompress=ppmd_core.decompress,
        validate_level=ppmd_core.validate_level,
    ),
)

_BY_NAME = {spec.name: spec for spec in SPECS}
_BY_ID = {spec.registry_id: spec for spec in SPECS}
# Legacy ids resolve to the same spec, so an archive written before ADR-0020 still
# decodes and still reports its own id on read.
_BY_ID.update({legacy: spec for spec in SPECS for legacy in spec.legacy_ids})


DEFAULT_CODEC_ID = _BY_NAME[DEFAULT_CODEC].registry_id


def names() -> tuple[str, ...]:
    """CLI-facing codec names, in registration order."""
    return tuple(spec.name for spec in SPECS)


def by_name(name: str) -> CodecSpec:
    try:
        return _BY_NAME[name]
    except KeyError:
        raise UnknownCodec(
            f"unknown codec {name!r}; this build knows {', '.join(names())}"
        ) from None


def by_registry_id(registry_id: str) -> CodecSpec:
    try:
        return _BY_ID[registry_id]
    except KeyError:
        raise UnknownCodec(
            f"unknown codec id {registry_id!r}; this build knows "
            f"{', '.join(spec.registry_id for spec in SPECS)}"
        ) from None
