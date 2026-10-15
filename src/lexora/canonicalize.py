"""Deterministic canonicalization of raw text bytes -> canonical UTF-8 bytes C.

Implements the *v0 minimal rule set* from docs/CANONICALIZATION.md:
  CAN-R01 encoding normalization (declared/detected charset -> UTF-8)
  CAN-R02 line-ending normalization (CRLF/CR -> LF)
  CAN-R05 soft-hyphen removal (U+00AD deleted)

Deliberately NOT implemented in v0 (status per rule table):
  CAN-R03 trailing-whitespace trim  (Medium risk for tables; needs golden vectors)
  CAN-R04 control-char removal      (needs context rules)
  CAN-R06 ligature expansion        (Deferred pending ADR)
  CAN-R07 Unicode NFKC              (Rejected for v1)
  CAN-R08/R09 dedup & OCR correction (P3 scope)

Script safety (REQ-CAN-005): no rule here decomposes or reorders Devanagari /
Gujarati combining marks, ZWJ (U+200D) or ZWNJ (U+200C). The only codepoints
removed are U+00AD, which cannot affect Indic shaping.

Determinism (REQ-CAN-001): pure function of (input bytes, version, declared
encoding). No locale, no randomness, no current-time dependence.
"""

from __future__ import annotations

import codecs
import hashlib

from lexora import CANONICALIZER_VERSION

# Ordered list of applied rules; recorded in meta output so audits can replay.
APPLIED_RULES_V0: tuple[str, ...] = ("CAN-R01", "CAN-R02", "CAN-R05")


class CanonicalizationError(ValueError):
    """Raised when input cannot be canonicalized under the declared contract."""


def _detect_and_decode(raw: bytes, declared_encoding: str | None) -> str:
    """CAN-R01: decode to str using declared encoding, else BOM/UTF-8 sniff.

    Detection order (deterministic):
      1. declared_encoding argument, if given.
      2. UTF-16 BOMs (FF FE / FE FF).
      3. UTF-8 BOM.
      4. Strict UTF-8 decode.
      5. No automatic lossy fallback: silent guesses violate REQ-CAN-003.
         Callers wanting latin-1 must declare it explicitly.
    """
    if declared_encoding is not None:
        try:
            text = codecs.decode(raw, declared_encoding)
        except (LookupError, UnicodeDecodeError) as exc:
            raise CanonicalizationError(
                f"declared encoding {declared_encoding!r} failed: {exc}"
            ) from exc
        return _strip_bom(text)

    if raw.startswith(b"\xff\xfe") or raw.startswith(b"\xfe\xff"):
        return _strip_bom(codecs.decode(raw, "utf-16"))
    if raw.startswith(b"\xef\xbb\xbf"):
        body = raw[3:]
    else:
        body = raw
    try:
        return body.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise CanonicalizationError(
            "input is not valid UTF-8 and no encoding was declared "
            "(declare one explicitly; lossy auto-guessing is prohibited)"
        ) from exc


def _strip_bom(text: str) -> str:
    return text[1:] if text.startswith("\ufeff") else text


def canonicalize(raw: bytes, *, declared_encoding: str | None = None) -> bytes:
    """Return canonical UTF-8 bytes C for raw extracted bytes.

    Guarantees: deterministic (REQ-CAN-001), UTF-8 without BOM, LF newlines
    (REQ-CAN-002; newline policy fixed for lexcAN-0.1), only whitelisted
    rules applied (REQ-CAN-003).
    """
    text = _detect_and_decode(raw, declared_encoding)

    # CAN-R02: CRLF -> LF first, then lone CR -> LF. Deterministic two-pass.
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # CAN-R05: remove soft hyphens. Safe for all scripts (no combining effect).
    text = text.replace("\u00ad", "")

    return text.encode("utf-8")  # canonical form: UTF-8, no BOM (REQ-CAN-002)


def canonicalize_with_meta(raw: bytes, *, declared_encoding: str | None = None) -> dict:
    """canonicalize() plus audit metadata (sizes, hashes, rules, version)."""
    c = canonicalize(raw, declared_encoding=declared_encoding)
    return {
        "canonicalizer_version": CANONICALIZER_VERSION,
        "applied_rules": list(APPLIED_RULES_V0),
        "input_bytes": len(raw),
        "output_bytes": len(c),
        "input_sha256": hashlib.sha256(raw).hexdigest(),
        "output_sha256": hashlib.sha256(c).hexdigest(),
        "canonical": c,
    }
