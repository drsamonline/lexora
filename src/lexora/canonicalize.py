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
        try:
            text = codecs.decode(raw, "utf-16")
        except UnicodeDecodeError as exc:
            # Same wrapping as every other branch: an unwrapped UnicodeDecodeError
            # escapes the CLI's CanonicalizationError handler and surfaces as a
            # traceback instead of exit code 4 (found while testing the streaming
            # reader against a truncated UTF-16 file).
            raise CanonicalizationError(
                f"input starts with a UTF-16 BOM but is not valid UTF-16: {exc}"
            ) from exc
        return _strip_bom(text)
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


def _decode_failure(exc: UnicodeDecodeError, mode: str, declared: str | None) -> CanonicalizationError:
    """One message per detection mode, so the buffered and streaming paths cannot
    drift apart (they are compared byte-for-byte in the test suite)."""
    if mode == "declared":
        return CanonicalizationError(f"declared encoding {declared!r} failed: {exc}")
    if mode == "utf16":
        return CanonicalizationError(
            f"input starts with a UTF-16 BOM but is not valid UTF-16: {exc}"
        )
    return CanonicalizationError(
        "input is not valid UTF-8 and no encoding was declared "
        "(declare one explicitly; lossy auto-guessing is prohibited)"
    )


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

def canonicalize_stream(src, dst, *, declared_encoding: str | None = None,
                        chunk_size: int = 1 << 20) -> dict:
    """Streaming CAN-R01/R02/R05: read `src`, write canonical UTF-8 to `dst`.

    Why this exists: `canonicalize()` needs the whole document in memory, so the
    canonicalizer working set grew with input size and the ≤256 MiB
    "Canonicalize one document (streaming)" row in docs/PERFORMANCE_BUDGET.md
    could not be met on a large document. Here the resident set is one decoded
    chunk plus a one-character carry, so it is flat in document size.

    Byte-identity with canonicalize() is the contract, and it is the hard part:

      * **Decoding is incremental.** A multi-byte UTF-8 sequence (or a UTF-16
        code unit) can straddle a chunk boundary, so `codecs.getincrementaldecoder`
        is used and its final flush is taken at EOF. Decoding chunk-by-chunk with
        `bytes.decode` would corrupt exactly those characters.
      * **Encoding detection needs the first bytes.** BOM sniffing reads until it
        has three bytes (however small chunk_size is), then fixes the codec for
        the whole stream. A leading U+FEFF is stripped from the decoded text
        wherever it lands — the first decoded slice can be empty while the BOM
        is still split across reads.
      * **A trailing CR is held back.** "\r\n" split across chunks must still
        collapse to one "\n" (CAN-R02), so a chunk ending in CR carries that CR
        into the next round; at EOF the carry becomes a lone "\n", which is what
        canonicalize() does with a trailing CR.
      * **Rule order is preserved.** CRLF → LF, then lone CR → LF, then U+00AD
        removal, applied to `carry + decoded_chunk` in that order, so a soft
        hyphen sitting between CR and LF behaves identically to the buffered path.

    Returns the audit fields of canonicalize_with_meta() minus the payload, with
    SHA-256 digests accumulated while streaming. Raises CanonicalizationError
    with the same message text as the buffered path, so exit codes stay identical
    (REQ-CAN-003: no lossy guessing) — with one deliberate exception: when the
    decoder fails, the byte *position* quoted inside the codec's own message is
    relative to the current chunk rather than the whole document, because an
    incremental decoder does not know where it is in the stream. The error type
    and the leading message are identical; only that number can differ.
    """
    if chunk_size < 1:
        raise CanonicalizationError("chunk_size must be >= 1")

    in_hash = hashlib.sha256()
    out_hash = hashlib.sha256()
    input_bytes = 0
    output_bytes = 0

    decoder = None
    mode = "utf8"
    strip_bom = True
    carry = ""
    first = True

    def emit(text: str) -> None:
        nonlocal output_bytes
        if not text:
            return
        blob = text.encode("utf-8")
        out_hash.update(blob)
        output_bytes += len(blob)
        dst.write(blob)

    def process(text: str) -> str:
        """Strip one leading BOM if still pending, then apply CAN-R02 and CAN-R05,
        holding back a trailing CR so a CRLF split across chunks still collapses."""
        nonlocal carry, strip_bom
        text = carry + text
        carry = ""
        if strip_bom and text:
            if text.startswith("\ufeff"):
                text = text[1:]
            strip_bom = False
        if text.endswith("\r"):
            text, carry = text[:-1], "\r"
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        return text.replace("\u00ad", "")

    while True:
        raw = src.read(chunk_size)
        if not raw:
            break
        in_hash.update(raw)
        input_bytes += len(raw)

        if first:
            first = False
            if declared_encoding is None and len(raw) < 3:
                # A UTF-8 BOM needs three bytes; with a 1-byte chunk_size it
                # arrives in three reads, so gather before deciding the codec.
                buffered = raw
                while len(buffered) < 3:
                    more = src.read(chunk_size)
                    if not more:
                        break
                    in_hash.update(more)
                    input_bytes += len(more)
                    buffered += more
                raw = buffered
            if declared_encoding is not None:
                mode = "declared"
                try:
                    decoder = codecs.getincrementaldecoder(declared_encoding)("strict")
                except LookupError as exc:
                    raise CanonicalizationError(
                        f"declared encoding {declared_encoding!r} failed: {exc}"
                    ) from exc
            elif raw.startswith(b"\xff\xfe") or raw.startswith(b"\xfe\xff"):
                mode = "utf16"
                decoder = codecs.getincrementaldecoder("utf-16")("strict")
            else:
                mode = "utf8"
                decoder = codecs.getincrementaldecoder("utf-8")("strict")

        try:
            text = decoder.decode(raw, False)
        except UnicodeDecodeError as exc:
            raise _decode_failure(exc, mode, declared_encoding) from exc
        emit(process(text))

    if decoder is None:  # empty input: no bytes at all
        emit(process(""))
    else:
        try:
            tail = decoder.decode(b"", True)
        except UnicodeDecodeError as exc:
            raise _decode_failure(exc, mode, declared_encoding) from exc
        emit(process(tail))
    if carry:
        emit("\n")  # trailing CR at EOF is a lone CR -> LF
        carry = ""

    return {
        "canonicalizer_version": CANONICALIZER_VERSION,
        "applied_rules": list(APPLIED_RULES_V0),
        "input_bytes": input_bytes,
        "output_bytes": output_bytes,
        "input_sha256": in_hash.hexdigest(),
        "output_sha256": out_hash.hexdigest(),
    }
