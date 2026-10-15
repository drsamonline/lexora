"""Tests for lexora.canonicalize (REQ-CAN-001..003, 005).

These are behavioral tests written alongside lexcAN-0.1. NOTE: docs/CANONICALIZATION.md
requires *golden vectors* before any rule ships to a release; these tests lock v0
behaviour for development but do not replace the golden-vector gate (P1-T2, open).
"""

from __future__ import annotations

import pytest

from lexora import CANONICALIZER_VERSION
from lexora.canonicalize import (
    APPLIED_RULES_V0,
    CanonicalizationError,
    canonicalize,
    canonicalize_with_meta,
)


def test_determinism_same_input_same_output():
    # REQ-CAN-001: pure function of input bytes + version.
    raw = "Hello\r\nWorld​\u00adx".encode("utf-8")
    assert canonicalize(raw) == canonicalize(raw)


def test_version_exposed():
    # REQ-CAN-001: implementations MUST expose the canonicalizer version string.
    assert CANONICALIZER_VERSION == "lexcan-0.1"
    meta = canonicalize_with_meta(b"abc")
    assert meta["canonicalizer_version"] == CANONICALIZER_VERSION
    assert meta["applied_rules"] == list(APPLIED_RULES_V0)


def test_crlf_and_lone_cr_to_lf():
    # CAN-R02 / REQ-CAN-002 newline policy fixed per version.
    assert canonicalize(b"a\r\nb\rc\n") == b"a\nb\nc\n"
    # CRLF handled first: no double conversion artifacts.
    assert canonicalize(b"a\r\r\nb") == b"a\n\nb"


def test_soft_hyphen_removed():
    assert canonicalize("hy\u00adphen".encode("utf-8")) == b"hyphen"


def test_utf8_bom_stripped_no_bom_in_output():
    # REQ-CAN-002: output UTF-8 without BOM.
    out = canonicalize("\ufeffdata".encode("utf-8"))
    assert out == b"data"
    assert not out.startswith(b"\xef\xbb\xbf")


def test_declared_encoding_used():
    assert canonicalize("café".encode("latin-1"), declared_encoding="latin-1") == "café".encode("utf-8")


def test_undeclared_non_utf8_refused():
    # REQ-CAN-003 spirit: no silent lossy guessing. 0x80 is invalid UTF-8 and
    # is not a BOM prefix, so detection must refuse rather than guess latin-1.
    with pytest.raises(CanonicalizationError):
        canonicalize(b"\x80\x81 not valid utf8")


def test_bad_declared_encoding_raises():
    with pytest.raises(CanonicalizationError):
        canonicalize(b"abc", declared_encoding="not-a-codec")


def test_script_safety_indic_preserved():
    # REQ-CAN-005: combining marks, ZWJ/ZWNJ must pass through untouched.
    hindi = "किताब\u200dज़\u200c".encode("utf-8")
    assert canonicalize(hindi) == hindi
    gujarati = "પુસ્તક".encode("utf-8")
    assert canonicalize(gujarati) == gujarati


def test_unknown_codepoints_pass_through():
    # Whitelist rule (REQ-CAN-003): only R01/R02/R05 alter bytes.
    exotic = "✅ \u2028 keep me".encode("utf-8")
    assert canonicalize(exotic) == exotic


def test_empty_input():
    assert canonicalize(b"") == b""


def test_meta_hashes():
    meta = canonicalize_with_meta(b"a\r\nb")
    assert meta["input_bytes"] == 4
    assert meta["output_bytes"] == 3
    assert meta["canonical"] == b"a\nb"
    assert len(meta["input_sha256"]) == 64 and len(meta["output_sha256"]) == 64
