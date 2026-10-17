"""App-service adapter for the LEXORA GUI (GUI-M1 scaffold, ADR-0008).

This is the ONLY layer between future Qt views and the shipped library.
Contract (ADR-0008 decision 3):

* Thin client: every operation delegates directly to
  `lexora.canonicalize` / `lexora.zstd_core` / `lexora.container`.
  No subprocess, no reimplementation, no silent clamping — parameter
  validation mirrors the CLI's bounds messaging (Session-26 precedent:
  `pack --block-size` out of range -> usage refusal *before* any I/O).
* Typed exceptions (`CanonicalizationError`, `CodecError`,
  `ContainerError`) propagate verbatim; each maps 1:1 to a frozen CLI
  exit code via `EXIT_BY_EXC` so GUI error surfaces and CLI behavior can
  never diverge silently.
* Qt isolation: this module imports PySide6 **lazily**, only inside
  `_make_qthread_worker()`. The pure functions and the `AppService`
  command methods are fully testable headless without Qt installed.
  Worker plumbing (signals/cancel) lands with GUI-M2 job runner.

Exit-code mapping source of truth: docs/CLI_REFERENCE.md + src/lexora/cli.py
(0 ok / 2 usage / 3 file / 4 canon / 5 codec / 6 roundtrip / 7 container).
"""

from __future__ import annotations

import contextlib
import dataclasses
import os
import tempfile
from pathlib import Path
from typing import Any, Callable

from lexora import __version__
from lexora.canonicalize import CanonicalizationError, canonicalize, canonicalize_with_meta
from lexora.container import ContainerError
from lexora.container import pack as lxz_pack
from lexora.container import read_index, unpack, verify_archive
from lexora.zstd_core import CodecError, compress, decompress

# Bounds mirror src/lexora/cli.py (MAX_BLOCK_SIZE = LIM-01 ceiling) and
# zstd level limits enforced by the codec library. Single source of the
# *numbers* stays in the library; these constants encode the CLI contract
# that the GUI must reproduce (usage-error class, exit 2 semantics).
MIN_LEVEL = 1
MAX_LEVEL = 22
MIN_BLOCK_SIZE = 1
MAX_BLOCK_SIZE = 8 * 1024 * 1024

#: Exception type -> frozen CLI exit code (ADR-0008 decision 3, parity rule).
EXIT_BY_EXC: dict[type[BaseException], int] = {
    CanonicalizationError: 4,
    CodecError: 5,
    # Round-trip failure (CLI exit 6) is surfaced by the container/codec
    # layers as ContainerError during pack/unpack verification; exit 6 is
    # specific to the CLI's explicit zround/pipe check, which AppService
    # exposes as run_zround()/run_pipe() below.
    ContainerError: 7,
}


class UsageError(ValueError):
    """Bad parameters refused before any I/O — GUI analogue of CLI exit 2."""


class FileOpError(OSError):
    """Input/output file failure — GUI analogue of CLI exit 3 (file errors)."""


def exit_code_for(exc: BaseException) -> int:
    """Frozen CLI exit code corresponding to a service-layer exception."""
    if isinstance(exc, UsageError):
        return 2
    if isinstance(exc, FileOpError):
        return 3
    for exc_type, code in EXIT_BY_EXC.items():
        if isinstance(exc, exc_type):
            return code
    return 1  # unexpected internal error (CLI has no dedicated code either)


def _check_level(level: int) -> None:
    if not isinstance(level, int) or isinstance(level, bool):
        raise UsageError(f"level must be an int, got {type(level).__name__}")
    if not MIN_LEVEL <= level <= MAX_LEVEL:
        raise UsageError(
            f"level {level} out of range [{MIN_LEVEL}, {MAX_LEVEL}] "
            "(mirrors `lexora zround/pipe/pack --level`)"
        )


def _check_block_size(block_size: int) -> None:
    if not isinstance(block_size, int) or isinstance(block_size, bool):
        raise UsageError(
            f"block size must be an int, got {type(block_size).__name__}"
        )
    if not MIN_BLOCK_SIZE <= block_size <= MAX_BLOCK_SIZE:
        raise UsageError(
            f"block size {block_size} out of range "
            f"[{MIN_BLOCK_SIZE}, {MAX_BLOCK_SIZE}] bytes (LIM-01; mirrors "
            "`lexora pack --block-size`)"
        )


@dataclasses.dataclass(frozen=True)
class JobResult:
    """Outcome of a synchronous service call (GUI-M1 shape; progress/cancel
    fields activate with the M2 job runner)."""

    ok: bool
    value: Any = None          # bytes | dict | VerifyResult-shaped dict
    error: str | None = None   # human-readable message, verbatim from lib
    exit_code: int = 0         # frozen CLI parity code


class AppService:
    """Thin stateless facade over the shipped library (DESIGN_GUI §2).

    Every method returns a `JobResult`; it never raises for expected user
    errors (parity: those become the matching exit code), but unexpected
    internal errors propagate for the crash handler (GUI-M2).
    """

    version = __version__

    # ---- G2 pipeline pieces -------------------------------------------
    def run_canon(self, raw: bytes, *, declared_encoding: str | None = None) -> JobResult:
        try:
            return JobResult(True, canonicalize(raw, declared_encoding=declared_encoding))
        except CanonicalizationError as exc:
            return JobResult(False, error=str(exc), exit_code=exit_code_for(exc))

    def run_canon_meta(self, raw: bytes, *, declared_encoding: str | None = None) -> JobResult:
        try:
            return JobResult(True, canonicalize_with_meta(raw, declared_encoding=declared_encoding))
        except CanonicalizationError as exc:
            return JobResult(False, error=str(exc), exit_code=exit_code_for(exc))

    def run_compress(self, canonical: bytes, *, level: int = 19) -> JobResult:
        try:
            _check_level(level)
            return JobResult(True, compress(canonical, level=level))
        except (UsageError, CodecError) as exc:
            return JobResult(False, error=str(exc), exit_code=exit_code_for(exc))

    def run_decompress(self, frame: bytes) -> JobResult:
        try:
            return JobResult(True, decompress(frame))
        except CodecError as exc:
            return JobResult(False, error=str(exc), exit_code=exit_code_for(exc))

    # ---- G3 container pieces ------------------------------------------
    def run_pack(self, canonical: bytes, *, level: int = 19,
                 block_size: int = MAX_BLOCK_SIZE) -> JobResult:
        try:
            _check_level(level)
            _check_block_size(block_size)
            blob = lxz_pack(canonical, level=level, block_size=block_size)
            return JobResult(True, {"archive": blob, "bytes_in": len(canonical),
                                    "bytes_out": len(blob)})
        except (UsageError, CodecError, ContainerError) as exc:
            return JobResult(False, error=str(exc), exit_code=exit_code_for(exc))

    def run_unpack(self, archive: bytes, *, only_block: int | None = None) -> JobResult:
        try:
            return JobResult(True, unpack(archive, only_block=only_block))
        except ContainerError as exc:
            return JobResult(False, error=str(exc), exit_code=exit_code_for(exc))

    # ---- file-level operations (views own dialogs; service owns I/O) ---
    # Parity note: these mirror the CLI's file handling — read errors map
    # to exit 3 (CLI_REFERENCE); writes are atomic temp+rename via
    # `atomic_write` so a failed write never leaves a partial output file
    # (same guarantee `unpack` gives at CLI level, REQ-SEC-004).
    @staticmethod
    def read_file(path: str | os.PathLike[str]) -> bytes:
        try:
            return Path(path).read_bytes()
        except OSError as exc:
            raise FileOpError(f"cannot read {path}: {exc}") from exc

    @staticmethod
    def atomic_write(data: bytes, path: str | os.PathLike[str]) -> None:
        dst = Path(path)
        fd, tmp_name = tempfile.mkstemp(dir=str(dst.parent or Path(".")),
                                        prefix=f".{dst.name}.", suffix=".tmp")
        try:
            with os.fdopen(fd, "wb") as fh:
                fh.write(data)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp_name, dst)
        except BaseException:
            with contextlib.suppress(OSError):
                os.unlink(tmp_name)
            raise

    def pack_file(self, in_path: str | os.PathLike[str], out_path: str | os.PathLike[str],
                  *, level: int = 19, block_size: int = MAX_BLOCK_SIZE,
                  canonicalize_first: bool = False,
                  declared_encoding: str | None = None) -> JobResult:
        """G2 one-shot: raw/canonical file -> .lxz file. Mirrors
        `lexora pack` (+ optional canon pre-pass like `pipe`)."""
        try:
            raw = self.read_file(in_path)
        except FileOpError as exc:
            return JobResult(False, error=str(exc), exit_code=exit_code_for(exc))
        if canonicalize_first:
            canon = self.run_canon(raw, declared_encoding=declared_encoding)
            if not canon.ok:
                return canon
            payload = canon.value
        else:
            payload = raw
        packed = self.run_pack(payload, level=level, block_size=block_size)
        if not packed.ok:
            return packed
        try:
            self.atomic_write(packed.value["archive"], out_path)
        except OSError as exc:
            return JobResult(False, error=f"cannot write {out_path}: {exc}", exit_code=3)
        return JobResult(True, {"bytes_in": packed.value["bytes_in"],
                                "bytes_out": packed.value["bytes_out"]})

    def unpack_file(self, in_path: str | os.PathLike[str], out_path: str | os.PathLike[str],
                    *, only_block: int | None = None) -> JobResult:
        """G3 one-shot: .lxz file -> payload file. Refusal happens BEFORE
        any byte is written (parity with CLI exit-7 no-output behavior)."""
        try:
            archive = self.read_file(in_path)
        except FileOpError as exc:
            return JobResult(False, error=str(exc), exit_code=exit_code_for(exc))
        res = self.run_unpack(archive, only_block=only_block)
        if not res.ok:
            return res
        try:
            self.atomic_write(res.value, out_path)
        except OSError as exc:
            return JobResult(False, error=f"cannot write {out_path}: {exc}", exit_code=3)
        return JobResult(True, {"bytes_in": len(archive), "bytes_out": len(res.value)})

    def inspect_file(self, in_path: str | os.PathLike[str]) -> JobResult:
        """G4 inspector feed for a file on disk."""
        try:
            archive = self.read_file(in_path)
        except FileOpError as exc:
            return JobResult(False, error=str(exc), exit_code=exit_code_for(exc))
        return self.run_inspect(archive)

    def verify_file(self, in_path: str | os.PathLike[str]) -> JobResult:
        """G4 'verify all' button feed for a file on disk."""
        try:
            archive = self.read_file(in_path)
        except FileOpError as exc:
            return JobResult(False, error=str(exc), exit_code=exit_code_for(exc))
        return self.run_verify(archive)

    def run_inspect(self, archive: bytes) -> JobResult:
        """G4 inspector feed: header+index metadata only (no payload decode)."""
        try:
            info, total_compressed, total_uncompressed = read_index(archive)
            return JobResult(True, {
                "header": dataclasses.asdict(info),
                "total_compressed": total_compressed,
                "total_uncompressed": total_uncompressed,
            })
        except ContainerError as exc:
            return JobResult(False, error=str(exc), exit_code=exit_code_for(exc))

    def run_verify(self, archive: bytes) -> JobResult:
        try:
            result = verify_archive(archive)
            return JobResult(True, dataclasses.asdict(result))
        except ContainerError as exc:
            return JobResult(False, error=str(exc), exit_code=exit_code_for(exc))

    # ---- end-to-end (zround/pipe parity) ------------------------------
    def run_zround(self, canonical: bytes, *, level: int = 19) -> JobResult:
        """Compress then byte-exact-decompress; failure => exit 6 (REQ-CMP-001)."""
        res = self.run_compress(canonical, level=level)
        if not res.ok:
            return res
        back = self.run_decompress(res.value)
        if not back.ok:
            return back
        if back.value != canonical:
            return JobResult(False, error="round-trip verification failed", exit_code=6)
        return JobResult(True, {"frame_len": len(res.value), "verified": True})

    def run_pipe(self, raw: bytes, *, declared_encoding: str | None = None,
                 level: int = 19) -> JobResult:
        canon = self.run_canon(raw, declared_encoding=declared_encoding)
        if not canon.ok:
            return canon
        zr = self.run_zround(canon.value, level=level)
        if not zr.ok:
            return zr
        return JobResult(True, {"canonical": canon.value, "frame_len": zr.value["frame_len"]})


def _make_qthread_worker(fn: Callable[[], Any]):
    """Lazy Qt boundary (GUI-M2 job runner will use this factory).

    Imported here — not at module top — so the whole service layer stays
    testable without PySide6 installed (ADR-0008 decision 1: core Qt-free).
    Deliberately untested until a view consumes it; placeholder behavior:
    raises ImportError with guidance if Qt is absent.
    """
    try:
        from PySide6.QtCore import QThread  # noqa: F401
    except ImportError as exc:  # pragma: no cover - depends on environment
        raise ImportError(
            "Qt worker plumbing requires the [gui] extra: pip install 'lexora[gui]'"
        ) from exc
    raise NotImplementedError("job runner lands with GUI-M2")
