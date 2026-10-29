"""`lexora doctor` — is this install healthy, and what is it running on?

Support and bug reports are only as good as the facts in them, and the facts are
cheap to collect: versions, whether the codec actually round-trips, which optional
extras are present, where the config lives, and whether the corpus directories exist.
The most valuable check is the last one — a live pack/unpack round trip in memory —
because it answers "does this installation work at all?" rather than "does the
metadata look right?".

Qt-free by construction, so the GUI's About view can render the same report.
"""

from __future__ import annotations

import importlib.util
import os
import platform
import sys
from pathlib import Path

from lexora import CANONICALIZER_VERSION, DEFAULT_LEVEL, __version__
from lexora.container import (
    DEFAULT_MAX_BLOCK_COMPRESSED,
    DEFAULT_MAX_BLOCK_UNCOMPRESSED,
    DEFAULT_MAX_TOTAL_UNCOMPRESSED,
)

OK = "ok"
WARN = "warn"
FAIL = "fail"
INFO = "info"

MIN_PYTHON = (3, 12)
ZSTD_MIN, ZSTD_MAX = (0, 23), (0, 26)


def _check(name: str, status: str, detail: str) -> dict:
    return {"check": name, "status": status, "detail": detail}


def _version_tuple(text: str) -> tuple[int, ...]:
    parts = []
    for chunk in text.split("."):
        digits = "".join(ch for ch in chunk if ch.isdigit())
        if not digits:
            break
        parts.append(int(digits))
    return tuple(parts)


def _zstd_version() -> str | None:
    try:
        import zstandard

        return zstandard.__version__
    except Exception:  # pragma: no cover - import failure is reported by the check
        return None


def _corpus_facts(root: Path) -> list[dict]:
    """Report, never judge: corpus directories are data, not health."""
    facts = []
    for label, path in (("owner corpus (data/raw)", root / "data" / "raw"),
                        ("tier-1 snapshot (corpus/)", root / "corpus")):
        if not path.is_dir():
            facts.append(_check(label, INFO, "absent"))
            continue
        files = [p for p in path.rglob("*") if p.is_file()]
        total = sum(p.stat().st_size for p in files)
        facts.append(_check(label, INFO, f"{len(files)} file(s), {total / 2**20:.1f} MiB"))
    return facts


def run_checks(repo_root: Path | None = None) -> dict:
    """Collect every check. Each is (name, status, detail); statuses are ok / warn /
    fail / info, and only fail/warn affect the exit code."""
    root = Path(repo_root) if repo_root else Path.cwd()
    checks: list[dict] = []

    py = sys.version_info
    py_str = f"{py.major}.{py.minor}.{py.micro}"
    if (py.major, py.minor) >= MIN_PYTHON:
        checks.append(_check("python", OK, f"{py_str} ({platform.python_implementation()})"))
    else:
        checks.append(_check("python", FAIL,
                             f"{py_str} is older than the required "
                             f"{MIN_PYTHON[0]}.{MIN_PYTHON[1]} (ADR-0005)"))

    zstd = _zstd_version()
    if zstd is None:
        checks.append(_check("zstandard", FAIL, "not importable — the core codec is missing"))
    else:
        parsed = _version_tuple(zstd)[:2]
        if ZSTD_MIN <= parsed < ZSTD_MAX:
            checks.append(_check("zstandard", OK, zstd))
        else:
            checks.append(_check("zstandard", WARN,
                                 f"{zstd} is outside the pinned range "
                                 f">={ZSTD_MIN[0]}.{ZSTD_MIN[1]},<{ZSTD_MAX[0]}.{ZSTD_MAX[1]}"))

    checks.append(_check("lexora", INFO,
                         f"{__version__} (canonicalizer {CANONICALIZER_VERSION})"))
    checks.append(_check("platform", INFO,
                         f"{platform.system()} {platform.release()} {platform.machine()}"))

    # The check that actually answers "does this install work?"
    try:
        from lexora import container

        payload = b"doctor self-test: the round trip must hold\n" * 8
        archive = container.pack(payload, block_size=1024, level=1)
        ok = container.unpack(archive) == payload and container.verify_archive(archive).ok
        checks.append(_check("round trip", OK if ok else FAIL,
                             "pack -> verify -> unpack returned the original bytes"
                             if ok else "round trip returned different bytes"))
    except Exception as exc:  # noqa: BLE001 - the point is to report any failure
        checks.append(_check("round trip", FAIL, f"{type(exc).__name__}: {exc}"))

    if importlib.util.find_spec("PySide6") is not None:
        checks.append(_check("gui extra", OK, "PySide6 importable"))
    else:
        checks.append(_check("gui extra", INFO,
                             "PySide6 not installed (optional: pip install 'lexora[gui]')"))

    writable = os.access(root, os.W_OK)
    checks.append(_check("working directory", OK if writable else FAIL,
                         f"{root} is {'writable' if writable else 'NOT writable'}"))

    config_home = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    config_dir = Path(config_home) / "lexora"
    checks.append(_check("config directory", INFO, str(config_dir)))

    checks.append(_check("defaults", INFO,
                         f"level {DEFAULT_LEVEL}, block {DEFAULT_MAX_BLOCK_UNCOMPRESSED} B, "
                         f"LIM-01 {DEFAULT_MAX_BLOCK_UNCOMPRESSED} B, "
                         f"LIM-02 {DEFAULT_MAX_BLOCK_COMPRESSED} B, "
                         f"archive ceiling {DEFAULT_MAX_TOTAL_UNCOMPRESSED} B"))

    checks.extend(_corpus_facts(root))

    failures = sum(1 for c in checks if c["status"] == FAIL)
    warnings = sum(1 for c in checks if c["status"] == WARN)
    return {
        "healthy": failures == 0 and warnings == 0,
        "failures": failures,
        "warnings": warnings,
        "checks": checks,
    }


def format_report(report: dict) -> str:
    """One line per check, aligned, with a summary that says what to do next."""
    width = max(len(c["check"]) for c in report["checks"])
    marks = {OK: "ok  ", WARN: "warn", FAIL: "FAIL", INFO: "--  "}
    lines = [f"{'check':<{width}}  {'status':<4}  detail"]
    for c in report["checks"]:
        lines.append(f"{c['check']:<{width}}  {marks[c['status']]:<4}  {c['detail']}")
    lines.append("")
    if report["healthy"]:
        lines.append("healthy: no failures, no warnings")
    else:
        bits = []
        if report["failures"]:
            bits.append(f"{report['failures']} failure(s)")
        if report["warnings"]:
            bits.append(f"{report['warnings']} warning(s)")
        lines.append("attention needed: " + ", ".join(bits))
    return "\n".join(lines)
