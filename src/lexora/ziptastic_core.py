"""ziptastic (CHCE) codec backend — a shell-out adapter, not a reimplementation.

Why this exists
---------------
lexora's Phase-1 backend is zstd. ziptastic's own measurements put CHCE 11.83 %
under `xz -9` on Silesia (10 files, 119 MB) and 24.9 % under `xz -9` on 2 MB of
English prose, while `xz -9` in turn beats zstd on most text. Swapping the
backend is therefore the largest ratio win available to this project, and it
needs no format change: the header already carries `codec_id[16]` (ADR-0007).

Contract — read from ziptastic `src/main.cpp` (commit 030c456), not guessed
----------------------------------------------------------------------------
  * `ziptastic c -9` with no file arguments filters **stdin -> stdout**.
  * `ziptastic d`    with no file arguments filters **stdin -> stdout**.
  * Output starts with the `CHCE` magic; detection is by magic, not extension.
  * `--version` prints `ziptastic <ver> (CHCE format vN)`.
  * `-9` is "maximum effort, no CM backend"; `--max-ratio` allows the CM backend
    (slowest, smallest).

Scope honesty
-------------
  * The binary is **not vendored**. `find_binary()` checks `$LEXORA_ZIPTASTIC`
    and then `PATH`. Every entry point raises a clear `CodecError` when it is
    absent — there is no silent fallback to zstd, because falling back would
    produce an archive whose header lies about its codec.
  * Speed is 0.3–0.6 MB/s at `-9`. This is the max-ratio path, never the default.
  * One process per block. At the 8 MiB default block that is 15–25 s of work per
    spawn, so spawn cost is noise; at 64 KiB blocks it would not be.
  * The container's per-block round-trip gate (SPEC §8.1) is what proves each
    stored frame decodes back to its input, so `compress()` here does not decode
    its own output a second time — that would double an already slow encode.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from functools import lru_cache

# One error type for every codec, so callers keep catching CodecError whichever
# backend they selected. Defined in zstd_core because that is where the first
# codec put it; re-exported here rather than duplicated.
from lexora.zstd_core import CodecError

BINARY_ENV = "LEXORA_ZIPTASTIC"
TIMEOUT_ENV = "LEXORA_ZIPTASTIC_TIMEOUT"
DEFAULT_TIMEOUT = 3600

MAGIC = b"CHCE"

# ziptastic has two effort presets, not a numeric level scale. `level=9` maps to
# `-9` (the documented max-effort preset) and `level=19` to `-9 --max-ratio`, so
# `--level` keeps meaning "more effort, smaller output" on both backends. Any
# other number is refused rather than silently rounded: an archive that says
# "level 15" while running `-9` would be a lie in the benchmark record.
LEVEL_TO_ARGS = {9: ("-9",), 19: ("-9", "--max-ratio")}
DEFAULT_LEVEL = 9


def find_binary() -> str | None:
    """Path to the ziptastic binary, or None. $LEXORA_ZIPTASTIC wins over PATH."""
    override = os.environ.get(BINARY_ENV)
    if override:
        return override if os.path.exists(override) else None
    return shutil.which("ziptastic")


def available() -> bool:
    return find_binary() is not None


def _require_binary(binary: str | None) -> str:
    path = binary or find_binary()
    if not path:
        raise CodecError(
            "the ziptastic codec needs the `ziptastic` binary on PATH "
            f"(or set ${BINARY_ENV} to its full path); it is not vendored. "
            "Build it from https://github.com/drsamonline/ziptastic, or use "
            "--codec zstd."
        )
    return path


def _run(argv: list[str], data: bytes, *, binary: str | None = None) -> bytes:
    """Run one ziptastic filter and return its stdout. Refuses on any failure."""
    path = _require_binary(binary)
    timeout = int(os.environ.get(TIMEOUT_ENV, DEFAULT_TIMEOUT))
    try:
        proc = subprocess.run(
            [path, *argv],
            input=data,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as exc:  # binary vanished between lookup and spawn
        raise CodecError(f"ziptastic binary not executable: {path}") from exc
    except subprocess.TimeoutExpired as exc:
        raise CodecError(
            f"ziptastic {argv[0]} exceeded {timeout}s on {len(data)} bytes "
            f"(raise ${TIMEOUT_ENV} for very large inputs)"
        ) from exc
    except OSError as exc:
        raise CodecError(f"cannot run ziptastic at {path}: {exc}") from exc
    if proc.returncode != 0:
        detail = proc.stderr.decode("utf-8", "replace").strip().splitlines()
        reason = detail[-1] if detail else "(no stderr)"
        raise CodecError(
            f"ziptastic {argv[0]} exited {proc.returncode} on {len(data)} bytes: {reason}"
        )
    return proc.stdout


@lru_cache(maxsize=1)
def _version_cached(path: str) -> str:
    proc = subprocess.run([path, "--version"], capture_output=True, check=False, timeout=60)
    text = (proc.stdout or proc.stderr).decode("utf-8", "replace").strip()
    return text.splitlines()[0] if text else "unknown"


def version(binary: str | None = None) -> str | None:
    """First line of `ziptastic --version`, or None when the binary is absent."""
    path = binary or find_binary()
    if not path:
        return None
    try:
        return _version_cached(path)
    except (OSError, subprocess.SubprocessError):  # pragma: no cover - env dependent
        return None


def compress(canonical: bytes, *, level: int = DEFAULT_LEVEL,
             binary: str | None = None) -> bytes:
    """Compress canonical bytes into one CHCE stream.

    Deterministic for a given binary and argument set (CHCE's serial path); the
    parallel path is not used here, which is what makes that true.
    """
    if not isinstance(canonical, bytes):
        raise CodecError("input must be bytes (canonical form), not str")
    if level not in LEVEL_TO_ARGS:
        raise CodecError(
            f"ziptastic has two effort presets, not a numeric scale: use level 9 "
            f"(-9) or 19 (-9 --max-ratio), got {level}"
        )
    frame = _run(["c", *LEVEL_TO_ARGS[level]], canonical, binary=binary)
    # A wrong binary on PATH is the realistic failure here, and it fails loudly
    # rather than producing an archive that cannot be decoded later.
    if not frame.startswith(MAGIC):
        raise CodecError(
            f"ziptastic produced {len(frame)} bytes without the CHCE magic — "
            "the binary on PATH is not ziptastic"
        )
    return frame


def decompress(frame: bytes, *, expected_original_size: int | None = None,
               binary: str | None = None) -> bytes:
    """Decode one CHCE stream back to canonical bytes.

    When the caller knows the original size (the container index does), a size
    mismatch is a refusal rather than best-effort output — the same rule
    zstd_core follows (REQ-CMP-006 spirit).
    """
    if not isinstance(frame, bytes):
        raise CodecError("input must be bytes")
    if not frame.startswith(MAGIC):
        raise CodecError("input does not start with the CHCE magic")
    out = _run(["d"], frame, binary=binary)
    if expected_original_size is not None and len(out) != expected_original_size:
        raise CodecError(
            f"decoded size {len(out)} != expected {expected_original_size} "
            "(truncation or wrong hint; refusing best-effort output)"
        )
    return out


def verify_roundtrip(canonical: bytes, *, level: int = DEFAULT_LEVEL,
                     binary: str | None = None) -> dict:
    """Encode->decode and assert byte equality; returns measured stats."""
    import hashlib

    blob = compress(canonical, level=level, binary=binary)
    back = decompress(blob, expected_original_size=len(canonical), binary=binary)
    return {
        "codec_profile": "ziptastic-chce",
        "library_version": version(binary) or "unknown",
        "input_bytes": len(canonical),
        "stored_bytes": len(blob),
        "ratio": (len(blob) / len(canonical)) if canonical else 1.0,
        "roundtrip_exact": back == canonical,
        "payload_sha256": hashlib.sha256(canonical).hexdigest(),
        "stored_sha256": hashlib.sha256(blob).hexdigest(),
    }
