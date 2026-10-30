#!/usr/bin/env python3
"""Generate canonicalization golden vectors under tests/vectors/canonicalization/.

P1-T2 gate (docs/CANONICALIZATION.md "Test vectors"): each vector is a
directory with input.bin, expected_output.bin and meta.json (canonicalizer
version + applied rules). Expected outputs are produced by the CURRENT
implementation and then reviewed; from then on tests/test_canon_vectors.py
locks them byte-exactly, so any behavioral change to lexcan-0.1 breaks the
conformance run instead of passing silently.

Idempotent: regenerates all files deterministically. Run this ONLY when the
owner deliberately accepts a rule-set change (then review the diff).
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from lexora import CANONICALIZER_VERSION  # noqa: E402
from lexora.canonicalize import APPLIED_RULES_V0, canonicalize  # noqa: E402

VECTOR_DIR = REPO_ROOT / "tests" / "vectors" / "canonicalization"

# name -> (declared_encoding or None, description, input bytes)
VECTORS: dict[str, tuple[str | None, str, bytes]] = {
    "v001_crlf_lf": (
        None,
        "CAN-R02: CRLF and lone CR normalize to LF; existing LF untouched",
        b"alpha\r\nbeta\rgamma\n delta\r\n",
    ),
    "v002_devanagari_marks": (
        None,
        "REQ-CAN-005: Devanagari combining marks pass through byte-exact "
        "(no decomposition/reordering); soft hyphen still removed",
        "काँस\xad".encode("utf-8"),
    ),
    "v003_zwnj_passthrough": (
        None,
        "REQ-CAN-005: ZWJ (U+200D) and ZWNJ (U+200C) pass through unchanged",
        "प्रय\xadत्न‌ज्ञ‍".encode("utf-8"),
    ),
    "v004_softhyphen_only": (
        None,
        "CAN-R05: U+00AD deleted everywhere; other chars unchanged",
        "hy\xadphen\xadated en\xaddash–ok".encode("utf-8"),
    ),
    "v005_declared_cp1251": (
        "cp1251",
        "CAN-R01: declared non-UTF-8 encoding transcoded to canonical UTF-8",
        "Привет\r\nмиру".encode("cp1251"),
    ),
    "v006_utf8_bom_stripped": (
        None,
        "CAN-R01: UTF-8 BOM stripped; output has no BOM (REQ-CAN-002)",
        "\ufeffcontent\r\nmore".encode("utf-8"),
    ),
    "v007_utf16le_bom": (
        None,
        "CAN-R01: UTF-16LE BOM detected, transcoded to UTF-8, CRLF -> LF",
        "Text line\r\nsecond".encode("utf-16-le"),
    ),
    "v008_empty_input": (
        None,
        "Edge case: empty input maps to empty output",
        b"",
    ),
    "v009_passthrough_ascii": (
        None,
        "Invariant: pure ASCII with LF-only newlines passes through unchanged",
        b"the quick brown fox\njumps over\t123 !@#\n",
    ),
}


def main() -> int:
    if VECTOR_DIR.exists():
        shutil.rmtree(VECTOR_DIR)
    VECTOR_DIR.mkdir(parents=True)
    for name, (enc, desc, raw) in VECTORS.items():
        d = VECTOR_DIR / name
        d.mkdir()
        out = canonicalize(raw, declared_encoding=enc)
        (d / "input.bin").write_bytes(raw)
        (d / "expected_output.bin").write_bytes(out)
        meta = {
            "id": name,
            "description": desc,
            "canonicalizer_version": CANONICALIZER_VERSION,
            "applied_rules": list(APPLIED_RULES_V0),
            "declared_encoding": enc,
            "input_bytes": len(raw),
            "expected_output_bytes": len(out),
        }
        (d / "meta.json").write_text(json.dumps(meta, indent=2) + "\n")
        print(f"wrote {d.relative_to(REPO_ROOT)} ({len(raw)} -> {len(out)} B)")
    print(f"{len(VECTORS)} vectors generated under {VECTOR_DIR.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
