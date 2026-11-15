"""The second language plugin — and the two properties that make the seam worth having.

ADR-0022 introduced the language seam with one implementation (English), which proves the
interface *compiles* but not that it is an interface: a seam with one implementation behind
it is a description of that implementation. This file exercises the second one, Hindi,
which lives OUTSIDE the core package (`packages/lexora-lang-hi/`) and registers through an
entry point.

Three things are asserted, in order of how much they matter:

1. **Readability without the plugin.** An archive written with `hi-1` decodes to the same
   bytes on a machine where the plugin cannot be imported. That is the property ADR-0022
   traded for, and the new v1.0 condition ("an archive written with a plugin must be
   readable without it").
2. **The plugin actually cleans something.** Two spellings of the same Devanagari word —
   precomposed nukta and base + combining nukta — converge on one byte string, while
   ZWJ/ZWNJ survive, because deleting those changes the word (REQ-CAN-005).
3. **The core did not have to change to admit it.** Built-ins are still English only; the
   plugin arrives through `importlib.metadata`, not through a list in `langapi`.

Nothing here re-implements the plugin's rules: the test imports the shipped package.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

from lexora import container, langapi

REPO_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = REPO_ROOT / "packages" / "lexora-lang-hi"
PLUGIN_SRC = PACKAGE_DIR / "src"

#: Devanagari fixtures. Written with explicit code points so the test does not depend on
#: the editor's normalisation of this file.
NUQTA_PRECOMPOSED = "\u0958"          # क़ as one letter (U+0958 QA WITH NUKTA)
NUQTA_DECOMPOSED = "\u0915\u093c"     # क + COMBINING NUKTA
WORD_KAAM = "\u0915\u093e\u092e"      # काम — "work"
KA_MATRA_I = "\u0915\u093f"          # कि — ka + i-matra


def _plugin():
    """The shipped plugin object, imported from the package directory.

    Imported by path rather than through the entry point so this test can run on a
    checkout where the distribution is not installed; the entry point itself is asserted
    separately, from the package's own pyproject.
    """
    if str(PLUGIN_SRC) not in sys.path:
        sys.path.insert(0, str(PLUGIN_SRC))
    import lexora_lang_hi

    return lexora_lang_hi.plugin()


# --------------------------------------------------------------------------- #
# 1. the seam, declared the way a third-party package declares it
# --------------------------------------------------------------------------- #

def test_the_package_declares_the_entry_point_adr_0022_requires() -> None:
    """Registration is one line in pyproject.toml, not a change to the core registry."""
    data = tomllib.loads((PACKAGE_DIR / "pyproject.toml").read_text())
    eps = data["project"]["entry-points"]["lexora.languages"]
    assert eps == {"hi": "lexora_lang_hi:plugin"}, eps


def test_the_entry_point_target_loads_and_satisfies_the_contract() -> None:
    plugin = _plugin()                            # what the entry point calls
    assert langapi.contract_violations(plugin) == []
    assert plugin.id == "hi"
    assert plugin.provenance == "hi-1"            # what lands in the header (ADR-0023)
    assert plugin.tokenizer == "unicode61"        # Devanagari is space-separated
    assert plugin.ocr_languages == ("hin",)


def test_the_core_still_ships_english_only() -> None:
    """The second language arrived as a package. If this fails, it was built into core."""
    assert [p.id for p in langapi._builtins()] == ["en"]


def test_the_installed_plugin_is_discovered_through_metadata() -> None:
    """When the distribution is installed, `doctor` sees it with no other wiring."""
    from importlib.metadata import PackageNotFoundError, distribution

    try:
        distribution("lexora-lang-hi")
    except PackageNotFoundError:
        pytest.skip("lexora-lang-hi is not installed in this environment "
                    "(pip install -e packages/lexora-lang-hi --no-deps)")
    plugin = langapi.get("hi")
    assert plugin.name.startswith("Hindi")
    assert langapi.contract_violations(plugin) == []


# --------------------------------------------------------------------------- #
# 2. the cleaning rules do something, and stop where they must
# --------------------------------------------------------------------------- #

def test_the_two_spellings_of_a_nukta_letter_canonicalise_to_one() -> None:
    """HI-R01. Without it one Hindi word is two archives and half the searches miss."""
    plugin = _plugin()
    pre = plugin.canonicalize(NUQTA_PRECOMPOSED.encode())
    dec = plugin.canonicalize(NUQTA_DECOMPOSED.encode())
    assert pre == dec
    # and the base rules alone do NOT do this — the rule is the plugin's, not inherited
    from lexora.canonicalize import canonicalize as base

    assert base(NUQTA_PRECOMPOSED.encode()) != base(NUQTA_DECOMPOSED.encode())


def test_a_word_survives_canonicalisation_unchanged() -> None:
    plugin = _plugin()
    assert plugin.canonicalize(WORD_KAAM.encode()) == WORD_KAAM.encode()
    assert plugin.canonicalize(KA_MATRA_I.encode()) == KA_MATRA_I.encode()


def test_zwj_and_zwnj_are_preserved() -> None:
    """REQ-CAN-005: these change conjunct shaping. Removing them changes the word."""
    plugin = _plugin()
    for mark in ("\u200c", "\u200d"):
        raw = (WORD_KAAM + mark + WORD_KAAM).encode()
        assert plugin.canonicalize(raw) == raw


def test_devanagari_digits_are_not_transliterated() -> None:
    """Cleaning is not normalisation of content: १२३ stays १२३."""
    plugin = _plugin()
    digits = "\u0967\u0968\u0969"
    assert plugin.canonicalize(digits.encode()) == digits.encode()


def test_the_base_rules_still_apply_through_the_plugin() -> None:
    plugin = _plugin()
    assert plugin.canonicalize(b"a\r\nb\r\n") == b"a\nb\n"
    assert plugin.canonicalize("a\u00adb".encode()) == b"ab"


def test_the_plugin_is_deterministic_and_returns_bytes() -> None:
    plugin = _plugin()
    raw = (WORD_KAAM + "\r\n" + NUQTA_PRECOMPOSED).encode()
    first = plugin.canonicalize(raw)
    assert isinstance(first, bytes)
    assert plugin.canonicalize(raw) == first


def test_meta_records_the_plugins_own_rules_and_provenance() -> None:
    plugin = _plugin()
    meta = plugin.canonicalize_with_meta(WORD_KAAM.encode())
    assert meta["canonicalizer_version"] == "hi-1"
    assert "HI-R01" in meta["applied_rules"]
    assert meta["canonical"] == WORD_KAAM.encode()


# --------------------------------------------------------------------------- #
# 3. the archive: provenance recorded, and readable without the plugin
# --------------------------------------------------------------------------- #

def test_an_archive_records_the_plugin_provenance() -> None:
    plugin = _plugin()
    payload = plugin.canonicalize(WORD_KAAM.encode())
    archive = container.pack(payload, canonicalizer_version=plugin.provenance)
    info = container.unpack_header(archive)
    assert info.canonicalizer_version == "hi-1"
    assert container.unpack(archive) == payload


def test_the_default_header_is_unchanged_byte_for_byte() -> None:
    """ADR-0023 must not rewrite a single existing archive: the default is the old label."""
    payload = b"unchanged\n"
    assert (container.pack(payload)
            == container.pack(payload, canonicalizer_version=None)
            == container.pack(payload, canonicalizer_version="lexcan-0.1"))
    assert container.unpack_header(container.pack(payload)).canonicalizer_version == "lexcan-0.1"


def test_a_non_ascii_provenance_is_refused_with_a_container_error() -> None:
    with pytest.raises(container.ContainerError) as excinfo:
        container.pack(b"x", canonicalizer_version="\u0939\u093f-1")
    assert "ASCII" in str(excinfo.value)


def test_a_too_long_provenance_is_refused() -> None:
    with pytest.raises(container.ContainerError) as excinfo:
        container.pack(b"x", canonicalizer_version="x" * 16)
    assert "does not fit" in str(excinfo.value)


def test_the_streamed_path_records_it_too() -> None:
    import io

    plugin = _plugin()
    payload = plugin.canonicalize((WORD_KAAM * 50).encode())
    dst = io.BytesIO()
    info = container.pack_stream(io.BytesIO(payload), dst,
                                 canonicalizer_version=plugin.provenance)
    assert info.canonicalizer_version == "hi-1"
    dst.seek(0)
    out = io.BytesIO()
    container.unpack_stream(dst, out)
    assert out.getvalue() == payload


_BLOCKER = r'''
import sys

# Make the plugin genuinely unimportable, the way an uninstalled package is.
class Blocker:
    def find_spec(self, name, path=None, target=None):
        if name.split(".")[0] == "lexora_lang_hi":
            raise ImportError("lexora_lang_hi is deliberately unavailable here")
        return None

sys.meta_path.insert(0, Blocker())

try:
    import lexora_lang_hi  # noqa: F401
except ImportError:
    pass
else:
    raise SystemExit("the blocker did not block")

from lexora import langapi
from lexora.container import unpack, unpack_header

archive = open(sys.argv[1], "rb").read()
if "hi" in langapi.available():
    raise SystemExit("the plugin was discovered in a process that must not have it")
info = unpack_header(archive)
sys.stdout.buffer.write(info.canonicalizer_version.encode() + b"\n")
sys.stdout.buffer.write(unpack(archive))
'''

def test_an_hi_archive_is_readable_where_the_plugin_does_not_exist(tmp_path) -> None:
    """The v1.0 condition: an archive written with a plugin is readable without it.

    Run in a subprocess, because blocking an import inside this process would not be
    believable — `lexora_lang_hi` is already in `sys.modules` by now.
    """
    plugin = _plugin()
    payload = plugin.canonicalize((WORD_KAAM + " " + NUQTA_DECOMPOSED + "\n").encode())
    archive = container.pack(payload, canonicalizer_version=plugin.provenance)
    path = tmp_path / "hi.lxz"
    path.write_bytes(archive)

    env = dict(os.environ)
    env["PYTHONPATH"] = str(REPO_ROOT / "src") + os.pathsep + env.get("PYTHONPATH", "")
    result = subprocess.run([sys.executable, "-c", _BLOCKER, str(path)],
                            capture_output=True, env=env, timeout=120)
    assert result.returncode == 0, result.stderr.decode()
    label, _, decoded = result.stdout.partition(b"\n")
    assert label == b"hi-1"
    assert decoded == payload
