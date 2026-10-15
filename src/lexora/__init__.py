"""LEXORA prototype package (Phase 1: canonicalization + Zstd core baseline).

Nothing here is a stable API. Version identifiers below are serialized into
archives and checked at verify time (REQ-CAN-004, REQ-CMP-002).
"""

__version__ = "0.0.1.dev1"

CANONICALIZER_VERSION = "lexcan-0.1"
CODEC_ID_ZSTD = "zstd-raw-l19"  # registry-style ID; retired IDs are never reused
