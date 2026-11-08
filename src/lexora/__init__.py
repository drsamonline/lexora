"""LEXORA prototype package (Phase 1: canonicalization + Zstd core baseline).

Nothing here is a stable API. Version identifiers below are serialized into
archives and checked at verify time (REQ-CAN-004, REQ-CMP-002).
"""

__version__ = "0.1.0a1"   # keep in sync with pyproject.toml (tests assert it)

CANONICALIZER_VERSION = "lexcan-0.1"
# Level-neutral since ADR-0020 (2026-11-08). The old value named a level the archive
# was not necessarily compressed at (ADR-0012 moved the default to 9), so every
# archive carried a false statement. New archives write this id; `zstd-raw-l19`
# remains a READ-ONLY alias so archives written before the change still decode.
CODEC_ID_ZSTD = "zstd-raw"
CODEC_ID_ZSTD_LEGACY_L19 = "zstd-raw-l19"  # read-only; never written again
# ziptastic's CHCE stream (ADR-0014). A new id, never a reuse of the zstd one:
# the reader dispatches on this string, so an archive packed with CHCE must say
# so, and an older reader must refuse it rather than attempt a zstd decode.
CODEC_ID_ZIPTASTIC = "ziptastic-1"

# Default zstd level for every surface (library, CLI, GUI settings).
#
# Was 19 until Session 53. The sweep in docs/PERFORMANCE_BUDGET.md priced the
# curve on 8 MiB of real Gutenberg prose: 19 gives ratio 0.2678 at 0.7 MiB/s,
# level 9 gives 0.3043 at 6.2 MiB/s (+13.6 % bytes for ~9x the speed), and the
# returns flatten after 9 (12/15/19 buy ~3-6 % more bytes for a 3-9x slowdown).
# 9 therefore clears the soft >=2 MB/s target with headroom while keeping the
# size story respectable; 19 stays available explicitly for archival work.
DEFAULT_LEVEL = 9
