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
import threading
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
    """Outcome of a service call. Sync M1 calls and async M2 jobs share this
    shape; an async-cancelled job is signalled separately via
    ``JobCancelled`` and never arrives as a JobResult."""

    ok: bool
    value: Any = None          # bytes | dict | VerifyResult-shaped dict
    error: str | None = None   # human-readable message, verbatim from lib
    exit_code: int = 0         # frozen CLI parity code


# ---- G7 settings (GUI-M2c; app-level only, no format impact) ---------------
# DESIGN_GUI §3 G7: persisted defaults for the pack form. These values never
# touch the .lxz format — they only pre-fill widgets (ADR-0008 thin-client:
# even persistence is plain stdlib JSON in a platform config dir, so this
# module stays Qt-free and headless-testable).

SETTINGS_FILENAME = "gui-settings.json"
DEFAULT_SETTINGS: dict[str, Any] = {
    "level": 3,                    # matches the CLI `pack --level` default
    "block_size": MAX_BLOCK_SIZE,  # LIM-01 ceiling, matches CLI default
}


def _config_root() -> Path:
    """Platform-appropriate per-user config directory.

    Honors XDG_CONFIG_HOME / APPDATA when set (also makes tests hermetic);
    falls back to ~/.config (POSIX) or ~/.lexora (other)."""
    env = os.environ.get("XDG_CONFIG_HOME") or os.environ.get("APPDATA")
    root = Path(env) if env else (Path.home() / ".config")
    return root / "lexora"


def settings_path() -> Path:
    return _config_root() / SETTINGS_FILENAME


def load_settings(path: str | os.PathLike[str] | None = None) -> dict[str, int]:
    """Read persisted GUI defaults; missing/corrupt file -> defaults.

    Validation mirrors the bounds contract: any stored value outside the
    enforced range is discarded silently (defaults win) rather than raising —
    settings must never block the app from starting."""
    p = Path(path) if path is not None else settings_path()
    out = dict(DEFAULT_SETTINGS)
    try:
        import json
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return out
    if isinstance(data, dict):
        lvl = data.get("level")
        if isinstance(lvl, int) and not isinstance(lvl, bool) \
                and MIN_LEVEL <= lvl <= MAX_LEVEL:
            out["level"] = lvl
        blk = data.get("block_size")
        if isinstance(blk, int) and not isinstance(blk, bool) \
                and MIN_BLOCK_SIZE <= blk <= MAX_BLOCK_SIZE:
            out["block_size"] = blk
    return out


def save_settings(values: dict[str, Any],
                  path: str | os.PathLike[str] | None = None) -> Path:
    """Validate then atomically persist GUI defaults. Raises UsageError
    (exit-2 class) on out-of-range values — refusing bad settings before
    writing, same posture as every other bounds refusal here."""
    level = values.get("level", DEFAULT_SETTINGS["level"])
    block = values.get("block_size", DEFAULT_SETTINGS["block_size"])
    _check_level(level)
    _check_block_size(block)
    p = Path(path) if path is not None else settings_path()
    payload = f'{{"level": {int(level)}, "block_size": {int(block)}}}\n'
    p.parent.mkdir(parents=True, exist_ok=True)
    AppService.atomic_write(payload.encode("utf-8"), p)
    return p


def resolve_path(path: str) -> tuple[Path | None, str | None]:
    """Resolve a user-supplied path string for file-picker pre-fills.

    Returns ``(resolved_or_None, error_or_None)`` — mirrors the CLI's
    ``_resolve_input_path`` posture (exit-3 class problems surface as
    ``FileOpError`` in the run flows; here we only need a lenient
    resolution to seed dialogs, so failures return ``(None, message)``).
    Accepts bare names, relative paths, directories, and ``~`` expansion.
    """
    if not path:
        return None, None
    try:
        candidate = Path(path).expanduser()
    except RuntimeError as exc:  # expanduser fails when home is unset
        return None, f"cannot expand path {path!r}: {exc}"
    if candidate.is_dir():
        return candidate, None
    if candidate.exists():
        return candidate.parent if candidate.parent.is_dir() else None, None
    # Missing file: seed the dialog at its parent directory if that exists.
    parent = candidate.parent
    if parent != candidate and parent.is_dir():
        return parent, None
    return None, f"path does not exist: {path!r}"


# ---- GUI-M2 job runner (Qt-free core) --------------------------------------
# DESIGN_GUI §2: "one thin adapter: async job runner, progress, cancellation"
# and §3: long operations run on worker threads with cooperative cancellation;
# the UI thread never blocks. The core below is deliberately Qt-free so it is
# testable without PySide6 (ADR-0008 decision 1); `_make_qthread_worker`
# adapts it to QThread + signals for the views.

class JobCancelled(Exception):
    """Raised by cancel-aware work functions when cancellation is requested."""


class CancelToken:
    """Cooperative cancellation flag shared between runner thread and UI."""

    def __init__(self) -> None:
        self._ev = threading.Event()

    def cancel(self) -> None:
        self._ev.set()

    @property
    def cancelled(self) -> bool:
        return self._ev.is_set()

    def check(self) -> None:
        if self._ev.is_set():
            raise JobCancelled("job cancelled")


#: Progress-reporting callback signature: (done_units, total_units).
ProgressFn = Callable[[int, int], None]


def _run_stages(
    steps: list[tuple[str, Callable[[], None]]],
    cancel: CancelToken,
) -> None:
    """Run ordered named stages, checking `cancel` before each one.

    Cancellation is cooperative at stage boundaries only (read / write): the
    expensive library calls themselves (`lxz_pack`, canonicalize) expose no
    interrupt seam and the thin-client rule forbids reimplementing them in
    chunks. A cancelled job therefore stops before the next stage begins —
    notably never reaching the write stage after cancellation during read."""
    for _, fn in steps:
        cancel.check()
        fn()


def pack_file_job(
    svc: AppService,
    in_path: str | os.PathLike[str],
    out_path: str | os.PathLike[str],
    *,
    level: int = 19,
    block_size: int = MAX_BLOCK_SIZE,
    canonicalize_first: bool = False,
    declared_encoding: str | None = None,
    progress_cb: ProgressFn | None = None,
    cancel: CancelToken | None = None,
) -> JobResult:
    """Cancel/progress-aware variant of `AppService.pack_file`.

    Same validation order and same JobResult/exit-code contract — the only
    differences are the `cancel.check()` points between stages and per-stage
    progress reporting. Bounds errors still refuse BEFORE any file I/O.
    """
    cancel = cancel or CancelToken()
    try:
        _check_level(level)
        _check_block_size(block_size)
    except UsageError as exc:
        return JobResult(False, error=str(exc), exit_code=exit_code_for(exc))

    st = {"raw_len": 0, "blob_len": 0, "out": b""}

    def read_step() -> None:
        raw = svc.read_file(in_path)          # FileOpError propagates
        st["raw_len"] = len(raw)
        if canonicalize_first:
            canon = svc.run_canon(raw, declared_encoding=declared_encoding)
            if not canon.ok:
                raise _StepFailure(canon)
            payload = canon.value
        else:
            payload = raw
        packed = svc.run_pack(payload, level=level, block_size=block_size)
        if not packed.ok:
            raise _StepFailure(packed)
        st["out"] = packed.value["archive"]
        st["blob_len"] = packed.value["bytes_out"]
        if progress_cb is not None:
            progress_cb(st["raw_len"], max(st["raw_len"] + st["blob_len"], 1))

    def write_step() -> None:
        try:
            svc.atomic_write(st["out"], out_path)
        except OSError as exc:
            raise _WriteError(f"cannot write {out_path}: {exc}") from exc
        if progress_cb is not None:
            progress_cb(st["raw_len"] + st["blob_len"],
                        max(st["raw_len"] + st["blob_len"], 1))

    try:
        _run_stages([("read", read_step), ("write", write_step)], cancel)
    except _StepFailure as fail:
        return fail.result
    except _WriteError as exc:
        return JobResult(False, error=str(exc), exit_code=3)
    except FileOpError as exc:
        return JobResult(False, error=str(exc), exit_code=exit_code_for(exc))
    return JobResult(True, {"bytes_in": st["raw_len"], "bytes_out": st["blob_len"]})


class _StepFailure(Exception):
    """Internal: unwraps a failed JobResult from a composed library call."""

    def __init__(self, result: JobResult) -> None:
        super().__init__(result.error)
        self.result = result


class _WriteError(OSError):
    """Internal: output-write failure -> exit 3 (parity with CLI)."""


def unpack_file_job(
    svc: AppService,
    in_path: str | os.PathLike[str],
    out_path: str | os.PathLike[str],
    *,
    only_block: int | None = None,
    progress_cb: ProgressFn | None = None,
    cancel: CancelToken | None = None,
) -> JobResult:
    """Cancel/progress-aware variant of `AppService.unpack_file`. Refusal
    (tampered archive) still happens BEFORE any byte is written."""
    cancel = cancel or CancelToken()
    st = {"in_len": 0, "out_len": 0, "payload": b""}

    def read_step() -> None:
        archive = svc.read_file(in_path)
        st["in_len"] = len(archive)
        res = svc.run_unpack(archive, only_block=only_block)
        if not res.ok:
            raise _StepFailure(res)
        st["payload"] = res.value
        st["out_len"] = len(res.value)
        if progress_cb is not None:
            progress_cb(st["in_len"], max(st["in_len"] + st["out_len"], 1))

    def write_step() -> None:
        try:
            svc.atomic_write(st["payload"], out_path)
        except OSError as exc:
            raise _WriteError(f"cannot write {out_path}: {exc}") from exc
        if progress_cb is not None:
            progress_cb(st["in_len"] + st["out_len"],
                        max(st["in_len"] + st["out_len"], 1))

    try:
        _run_stages([("read", read_step), ("write", write_step)], cancel)
    except _StepFailure as fail:
        return fail.result
    except _WriteError as exc:
        return JobResult(False, error=str(exc), exit_code=3)
    except FileOpError as exc:
        return JobResult(False, error=str(exc), exit_code=exit_code_for(exc))
    return JobResult(True, {"bytes_in": st["in_len"], "bytes_out": st["out_len"]})


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


class JobRunner:
    """Qt adapter around the cancel-aware job functions (GUI-M2).

    Runs one job at a time on a QThread worker so the UI thread never blocks
    (DESIGN_GUI §3). The worker emits `progressed(int,int)` /
    `finished_job(object)` / `cancelled()` / `failed(object)` signals; with
    Qt.AutoConnection, receivers created on the UI thread get queued
    invocations — widget-safe by construction. Direct callables
    (`on_finished`/`on_cancelled`/`on_error`) are additionally connected for
    non-Qt consumers (offscreen tests use them with an event loop).
    All Qt imports stay lazy inside `_make_qthread_worker` so the rest of the
    module remains Qt-free-testable (ADR-0008 decision 1).
    """

    def __init__(self) -> None:
        self._token: CancelToken | None = None
        self._worker = None
        self._live = False

    @property
    def running(self) -> bool:
        return self._live

    def start(
        self,
        fn: Callable[..., JobResult],
        *args: Any,
        progress_cb: ProgressFn | None = None,
        on_finished: Callable[[JobResult], None] | None = None,
        on_cancelled: Callable[[], None] | None = None,
        on_error: Callable[[BaseException], None] | None = None,
        **kwargs: Any,
    ) -> CancelToken:
        """Launch `fn(*args, cancel=<token>, progress_cb=<signal bridge>,
        **kwargs)` on a worker thread. Returns the cancellation token."""
        if self._live:
            raise RuntimeError("JobRunner already has a running job")
        token = CancelToken()
        self._token = token
        self._live = True
        self._worker = _make_qthread_worker(
            self, fn, args, kwargs, token,
            progress_cb=progress_cb, on_finished=on_finished,
            on_cancelled=on_cancelled, on_error=on_error)
        self._worker.start()
        return token

    def _settle(self) -> None:
        """Called by the worker when its run() body returns (any outcome)."""
        self._live = False

    def cancel(self) -> None:
        if self._token is not None:
            self._token.cancel()

    def wait(self, timeout_ms: int = 5000) -> bool:
        return self._worker.wait(timeout_ms) if self._worker is not None else True


def _make_qthread_worker(
    runner: JobRunner,
    fn: Callable[..., JobResult],
    args: tuple,
    kwargs: dict,
    token: CancelToken,
    *,
    progress_cb: ProgressFn | None = None,
    on_finished: Callable[[JobResult], None] | None = None,
    on_cancelled: Callable[[], None] | None = None,
    on_error: Callable[[BaseException], None] | None = None,
):
    """Create the QThread worker object (lazy Qt boundary, GUI-M2).

    Raises ImportError with guidance if Qt is absent (ADR-0008 decision 1
    fallback message)."""
    try:
        from PySide6.QtCore import QThread, Signal
    except ImportError as exc:  # pragma: no cover - depends on environment
        raise ImportError(
            "Qt worker plumbing requires the [gui] extra: pip install 'lexora[gui]'"
        ) from exc

    class _Worker(QThread):
        progressed = Signal(int, int)
        finished_job = Signal(object)
        cancelled = Signal()
        failed = Signal(object)

        def run(self) -> None:  # runs ON the worker thread
            try:
                res = fn(*args, cancel=token, progress_cb=self.progressed.emit,
                         **kwargs)
            except JobCancelled:
                runner._settle()
                self.cancelled.emit()
                if on_cancelled is not None:
                    on_cancelled()
                return
            except BaseException as exc:  # unexpected internal error -> G6
                runner._settle()
                self.failed.emit(exc)
                if on_error is not None:
                    on_error(exc)
                return
            runner._settle()
            # Deliver AFTER settling: by the time a (direct or queued)
            # callback runs, `runner.running` already reflects reality, so
            # consumers can immediately start the next job.
            if on_finished is not None:
                on_finished(res)
            self.finished_job.emit(res)

    w = _Worker()
    if progress_cb is not None:
        w.progressed.connect(progress_cb)
    return w
