"""Property/invariant tests for canonicalization (P1-T2 acceptance, second half).

Complements the 9 byte-exact golden vectors in tests/test_canon_vectors.py:
the whitelist contract (REQ-CAN-003) says ONLY rules CAN-R01/R02/R05 may alter
bytes — every other byte class must pass through unchanged. These tests assert
that invariant broadly and deterministically (fixed seeds; no randomness in CI
results):

  INV-1 idempotence:            canon(canon(x)) == canon(x)          (REQ-CAN-001)
  INV-2 untouched alphabet:     bytes outside {\\r, \\n, U+00AD, BOM} survive verbatim
  INV-3 random ASCII passthrough: printable ASCII + LF is a fixed point
  INV-4 script-safety fuzz:     combining marks / ZWJ / ZWNJ never reordered
  INV-5 output shape:           valid UTF-8, no BOM, no CR            (REQ-CAN-002)
"""

from __future__ import annotations

import random
import unicodedata

import pytest

from lexora.canonicalize import canonicalize

# Codepoints that v0 rules MAY touch: CR/LF (CAN-R02), soft hyphen (CAN-R05),
# BOM U+FEFF (encoding normalization artifact removal). Everything else is
# whitelisted-pass-through territory.
TOUCHED = {"\r", "\n", "\u00ad", "\ufeff"}


def _untouched_alphabet() -> str:
    """Deterministic sample of BMP codepoints no v0 rule may alter."""
    chars = []
    for cp in range(0x20, 0x1000):
        ch = chr(cp)
        if ch in TOUCHED:
            continue
        if unicodedata.category(ch) in ("Cs",):  # surrogates not encodable
            continue
        chars.append(ch)
    return "".join(chars)


def test_untouched_bmp_sample_passes_through_verbatim():
    # INV-2: strict UTF-8 input containing none of the touched codepoints
    # must be returned byte-identical (whitelist contract REQ-CAN-003).
    text = _untouched_alphabet()
    raw = text.encode("utf-8")
    assert canonicalize(raw) == raw


def test_printable_ascii_with_lf_is_fixed_point():
    # INV-3: seeded random ASCII text (no CR, no soft hyphen) is unchanged.
    rng = random.Random(20261016)
    alphabet = [chr(c) for c in range(0x20, 0x7F)] + ["\n"]
    for _ in range(200):
        s = "".join(rng.choice(alphabet) for _ in range(rng.randint(0, 64)))
        raw = s.encode("utf-8")
        assert canonicalize(raw) == raw


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_idempotence_on_random_unicode(seed):
    # INV-1: canonicalization is a fixed point after one application.
    rng = random.Random(seed)
    pool = list("abc\r\n\u00ad\u200d\u200c\u094d\u0a4d\u0ac9 \t✅\u0e01\u0e31")
    for _ in range(300):
        s = "".join(rng.choice(pool) for _ in range(rng.randint(0, 40)))
        raw = s.encode("utf-8")
        once = canonicalize(raw)
        assert canonicalize(once) == once


def test_indic_marks_zwj_zwnj_never_reordered_or_dropped():
    # INV-4 / REQ-CAN-005: seeded fuzz over Indic combining marks + ZWJ/ZWNJ
    # mixed with soft hyphens/CRLF. After removing only the whitelisted
    # deletions from the input, the remaining sequence must appear intact
    # (order preserved) in the output.
    rng = random.Random(42)
    marks = ["\u093e", "\u094d", "\u0915\u094d\u0937", "\u0a81", "\u0ac9",
             "\u200d", "\u200c", "क", "ખ", "a", "ब"]
    for _ in range(200):
        s = "".join(rng.choice(marks + ["\u00ad", "\r\n", "\r"])
                    for _ in range(rng.randint(1, 30)))
        raw = s.encode("utf-8")
        out = canonicalize(raw)
        expected = (
            s.replace("\r\n", "\n").replace("\r", "\n").replace("\u00ad", "")
        ).encode("utf-8")
        assert out == expected


@pytest.mark.parametrize("seed", [7, 8])
def test_output_shape_invariants(seed):
    # INV-5: output is always valid UTF-8 without BOM and without CR bytes.
    rng = random.Random(seed)
    for _ in range(100):
        raw = bytes(rng.randrange(256) for _ in range(rng.randint(0, 32)))
        try:
            out = canonicalize(raw)
        except Exception:
            continue  # refused inputs are covered by unit tests elsewhere
        out.decode("utf-8")  # raises if not valid UTF-8
        assert not out.startswith(b"\xef\xbb\xbf")
        assert b"\r" not in out
