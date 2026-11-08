"""The language-plugin seam (ADR-0022).

What a language plugin is
-------------------------
A package that declares four optional capabilities for one language:

  * **cleaning rules** — how that language's text is canonicalised on ingest;
  * a **search tokenizer** — which FTS5 tokenizer the index should use (this is the
    one that matters most for Chinese/Japanese, which have no spaces to split on);
  * an optional **dictionary** for the trained-model compression phase (not yet used);
  * optional **OCR language hints** — Tesseract codes to suggest.

The property that makes this safe, and the reason the seam is worth having at all:
**plugins affect ingestion only.** An archive stores canonical bytes; decompression is
exact regardless of which rules produced them. A file cleaned by the Hindi plugin is
readable on a machine that has never installed it. The tool degrades to "you cannot
re-clean this, but you can read it".

Discovery
---------
Built-ins first, then installed packages that declare the `lexora.languages` entry
point. **Plugins are installed, never fetched**: nothing in an archive, a metadata
field or a path may cause code to load, because an archive is data.

Provenance
----------
`LanguagePlugin.provenance` is the short string that lands in the 16-byte
`canonicalizer_version` header field. It must be `id`-`version`, ≤ 12 bytes, ASCII.
English keeps the historical label `lexcan-0.1` deliberately: renaming it would rewrite
every archive's header a second time in one week, for no reader benefit. New languages
start at `hi-1`, `zh-1`, and so on.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable

#: Entry-point group third-party packages register under.
ENTRY_POINT_GROUP = "lexora.languages"

#: The header field this lands in is 16 bytes; leave room for the NUL terminator.
MAX_PROVENANCE_BYTES = 12
_ID_RE = re.compile(r"^[a-z][a-z0-9]{1,7}$")


class LanguageError(Exception):
    """A language plugin is missing, malformed, or does not satisfy the contract."""


@dataclass(frozen=True)
class LanguagePlugin:
    """One language's declared capabilities.

    `canonicalize` and `canonicalize_with_meta` must be **pure**: same input and
    declared encoding ⇒ same output, no I/O, no clock, no environment.
    """

    id: str
    version: int
    name: str
    tokenizer: str = "unicode61"
    canonicalize: Callable[..., bytes] | None = None
    canonicalize_with_meta: Callable[..., dict] | None = None
    ocr_languages: tuple[str, ...] = ()
    dictionary: str | None = None
    #: Overrides the derived `<id>-<version>` label. Exists for one reason: English
    #: already wrote `lexcan-0.1` into every archive, and a plugin system is not a
    #: good enough reason to rewrite every archive's header for no reader benefit.
    provenance_label: str | None = None

    @property
    def provenance(self) -> str:
        return self.provenance_label or f"{self.id}-{self.version}"


# --------------------------------------------------------------------------- #
# the contract
# --------------------------------------------------------------------------- #

def contract_violations(plugin: object) -> list[str]:
    """Everything wrong with `plugin` as a language plugin. Empty list means valid.

    Deliberately returns *all* problems rather than the first: a plugin author fixing
    one issue at a time through repeated CLI runs is a bad experience, and the whole
    point of a contract is that it can be checked in one pass.
    """
    problems: list[str] = []
    if not isinstance(plugin, LanguagePlugin):
        return [f"not a LanguagePlugin (got {type(plugin).__name__})"]

    if not _ID_RE.match(plugin.id or ""):
        problems.append(
            f"id {plugin.id!r} must be lowercase alphanumeric, start with a letter, "
            "2-8 characters (it has to fit a 16-byte header field with its version)"
        )
    if not isinstance(plugin.version, int) or plugin.version < 1:
        problems.append(f"version must be a positive integer, got {plugin.version!r}")
    label = plugin.provenance
    if not label.isascii() or not re.fullmatch(r"[A-Za-z0-9._-]+", label):
        problems.append(
            f"provenance {label!r} must be ASCII letters, digits, dot, dash or underscore "
            "(it lands in a NUL-padded header field)"
        )
    prov = label.encode("utf-8", "replace")
    if len(prov) > MAX_PROVENANCE_BYTES:
        problems.append(
            f"provenance {plugin.provenance!r} is {len(prov)} bytes; the header field "
            f"allows at most {MAX_PROVENANCE_BYTES}"
        )
    if not plugin.name or not plugin.name.strip():
        problems.append("name must be a non-empty human-readable label")
    if plugin.tokenizer not in KNOWN_TOKENIZERS:
        problems.append(
            f"tokenizer {plugin.tokenizer!r} is not one of {sorted(KNOWN_TOKENIZERS)}"
        )
    if plugin.canonicalize is None:
        problems.append("canonicalize is required — a plugin with no cleaning rules "
                        "would silently store raw bytes")
    if not isinstance(plugin.ocr_languages, tuple):
        problems.append("ocr_languages must be a tuple of Tesseract codes")

    # Behavioural checks. Cheap, and they catch the two failures that matter: a
    # plugin that is not deterministic, and one that does not return bytes.
    if plugin.canonicalize is not None:
        try:
            out = plugin.canonicalize(b"hello\r\nworld\r\n")
        except Exception as exc:  # noqa: BLE001 - any failure is a contract failure
            problems.append(f"canonicalize raised on trivial input: {type(exc).__name__}: {exc}")
        else:
            if not isinstance(out, bytes):
                problems.append(f"canonicalize returned {type(out).__name__}, not bytes")
            elif plugin.canonicalize(b"hello\r\nworld\r\n") != out:
                problems.append("canonicalize is not deterministic on identical input")
    return problems


#: Tokenizers the catalog can actually configure. `unicode61` for space-separated
#: scripts; `trigram` is what makes CJK searchable at all; `porter` stems English.
KNOWN_TOKENIZERS = frozenset({"unicode61", "trigram", "porter", "ascii"})


# --------------------------------------------------------------------------- #
# registry
# --------------------------------------------------------------------------- #

def _builtins() -> list[LanguagePlugin]:
    from lexora.languages import english

    return [english.PLUGIN]


def available(*, strict: bool = False) -> dict[str, LanguagePlugin]:
    """Every usable plugin, keyed by id. Invalid plugins are excluded, not raised.

    `strict=True` raises instead — used by `doctor`, which exists to report problems
    rather than hide them.
    """
    found: dict[str, LanguagePlugin] = {}
    problems: list[str] = []

    for plugin in _builtins():
        issues = contract_violations(plugin)
        if issues:
            problems.append(f"{plugin.id}: " + "; ".join(issues))
            continue
        found[plugin.id] = plugin

    for plugin, issues, origin in _installed():
        if issues:
            problems.append(f"{origin}: " + "; ".join(issues))
            continue
        if plugin.id in found:
            problems.append(f"{origin}: id {plugin.id!r} collides with a built-in")
            continue
        found[plugin.id] = plugin

    if strict and problems:
        raise LanguageError("; ".join(problems))
    return found


def _installed() -> list[tuple[LanguagePlugin, list[str], str]]:
    """Third-party plugins from installed packages. Never from data."""
    try:
        from importlib.metadata import entry_points
    except ImportError:  # pragma: no cover - Python < 3.8
        return []
    out: list[tuple[LanguagePlugin, list[str], str]] = []
    try:
        eps = entry_points(group=ENTRY_POINT_GROUP)
    except TypeError:  # pragma: no cover - old importlib API
        eps = entry_points().get(ENTRY_POINT_GROUP, [])
    for ep in eps:
        origin = f"{ep.name} ({ep.value})"
        try:
            plugin = ep.load()()
        except Exception as exc:  # noqa: BLE001 - a broken plugin must not kill the CLI
            out.append((LanguagePlugin(id="zz", version=1, name="broken"), 
                        [f"failed to load: {type(exc).__name__}: {exc}"], origin))
            continue
        out.append((plugin, contract_violations(plugin), origin))
    return out


def get(language_id: str) -> LanguagePlugin:
    plugins = available()
    if language_id in plugins:
        return plugins[language_id]
    raise LanguageError(
        f"no language plugin {language_id!r}; available: {', '.join(sorted(plugins)) or 'none'}"
    )


def default() -> LanguagePlugin:
    """English, until a user chooses otherwise. Named explicitly, not 'first'."""
    return get("en")


def report() -> list[dict[str, str]]:
    """Rows for `doctor`: id, name, provenance, tokenizer, and validity."""
    rows: list[dict[str, str]] = []
    for plugin in available().values():
        rows.append({
            "id": plugin.id,
            "name": plugin.name,
            "provenance": plugin.provenance,
            "tokenizer": plugin.tokenizer,
            "status": "ok",
        })
    for _plugin, issues, origin in _installed():
        if issues:
            rows.append({"id": origin, "name": "", "provenance": "", "tokenizer": "",
                         "status": "invalid: " + "; ".join(issues)})
    return rows
