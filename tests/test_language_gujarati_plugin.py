"""The fourth language plugin — and the first whose script-specific rule is not composition.

REQ-CAN-005 names two scripts, Devanagari and Gujarati. Devanagari shipped with
`packages/lexora-lang-hi`; Gujarati had **no plugin and no vectors**, so the requirement was half
met while its row said otherwise. This file exercises the fourth plugin, which lives outside the
core (`packages/lexora-lang-gu/`) and registers through an entry point.

Four things are asserted, in order of how much they matter:

1. **Readability without the plugin** — an archive written with `gu-1` decodes to identical bytes
   on a machine where the package cannot be imported. That is the property ADR-0022 traded for.
2. **The rule does something real, and the right something** — two byte spellings of the same
   Gujarati sequence converge, while ZWJ/ZWNJ survive and digits are untouched.
3. **The claim is measured, not copied from Hindi** — Gujarati has *zero* canonical
   decompositions in its block, so NFC here orders marks rather than composing letters. A test
   asserts that absence, so nobody later claims Devanagari's byte saving for a script that cannot
   deliver it.
4. **The core did not have to change to admit it** — built-ins are still English only.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tomllib
import unicodedata
from pathlib import Path

import pytest

from lexora import container, langapi

REPO_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = REPO_ROOT / "packages" / "lexora-lang-gu"
PLUGIN_SRC = PACKAGE_DIR / "src"

#: Gujarati fixtures, written as explicit code points so the file's own normalisation cannot
#: change what is being tested.
KA = "\u0a95"                    # ક
NUKTA = "\u0abc"                 # ઼  (combining class 7)
VIRAMA = "\u0acd"                # ્  (combining class 9)
GUJARAT = "\u0a97\u0ac1\u0a9c\u0ab0\u0abe\u0aa4"   # ગુજરાત
DIGITS = "\u0ae6\u0ae7\u0ae8\u0ae9"                # ૦૧૨૩
ZWNJ_CONJUNCT = KA + VIRAMA + "\u200c" + "\u0ab7"  # ક્‌ષ
ZWJ_CONJUNCT = KA + VIRAMA + "\u200d" + "\u0ab7"   # ક્‍ષ


def _plugin():
    """The shipped plugin object, imported by path so this runs on an uninstalled checkout."""
    if str(PLUGIN_SRC) not in sys.path:
        sys.path.insert(0, str(PLUGIN_SRC))
    import lexora_lang_gu

    return lexora_lang_gu.plugin()


# --------------------------------------------------------------------------- #
# 1. the seam, declared the way a third-party package declares it
# --------------------------------------------------------------------------- #

def test_the_package_declares_the_entry_point_adr_0022_requires() -> None:
    data = tomllib.loads((PACKAGE_DIR / "pyproject.toml").read_text())
    eps = data["project"]["entry-points"]["lexora.languages"]
    assert eps == {"gu": "lexora_lang_gu:plugin"}, eps


def test_the_entry_point_target_loads_and_satisfies_the_contract() -> None:
    plugin = _plugin()
    assert langapi.contract_violations(plugin) == []
    assert plugin.id == "gu"
    assert plugin.provenance == "gu-1"
    assert plugin.tokenizer == "unicode61", "Gujarati is space-separated; trigram is for CJK"
    assert plugin.ocr_languages == ("guj",)


def test_the_core_still_ships_english_only() -> None:
    """The fourth language arrived as a package. If this fails, it was built into core."""
    assert [p.id for p in langapi._builtins()] == ["en"]


def test_the_installed_plugin_is_discovered_through_metadata() -> None:
    from importlib.metadata import PackageNotFoundError, distribution

    try:
        distribution("lexora-lang-gu")
    except PackageNotFoundError:
        pytest.skip("lexora-lang-gu is not installed in this environment "
                    "(pip install -e packages/lexora-lang-gu --no-deps)")
    plugin = langapi.get("gu")
    assert plugin.name.startswith("Gujarati")
    assert langapi.contract_violations(plugin) == []


# --------------------------------------------------------------------------- #
# 2. the claim, measured: ordering, not composition
# --------------------------------------------------------------------------- #

def test_gujarati_has_no_canonical_decompositions_at_all() -> None:
    """The fact that makes GU-R01 different from HI-R01, asserted rather than asserted-at.

    Devanagari's rule earns its keep by merging precomposed nukta letters. Gujarati has none, so
    a plugin that copied Hindi's rationale would be describing a saving this script cannot make.
    """
    block = range(0x0A80, 0x0B00)
    decomposable = [
        (hex(cp), unicodedata.name(chr(cp), "?"))
        for cp in block
        if unicodedata.decomposition(chr(cp))
        and not unicodedata.decomposition(chr(cp)).startswith("<")
    ]
    assert decomposable == [], (
        f"Gujarati now has canonical decompositions: {decomposable}. GU-R01's rationale in the "
        "plugin docstring and README needs re-reading — composition may now be in play"
    )


def test_the_two_mark_orders_canonicalise_to_one() -> None:
    """GU-R01's actual effect: nukta (ccc 7) sorts before virama (ccc 9)."""
    plugin = _plugin()
    nukta_first = (KA + NUKTA + VIRAMA).encode()
    virama_first = (KA + VIRAMA + NUKTA).encode()
    assert nukta_first != virama_first, "the fixture must differ in bytes before the rule runs"
    assert plugin.canonicalize(nukta_first) == plugin.canonicalize(virama_first)
    assert plugin.canonicalize(virama_first) == nukta_first, "NFC settles on class order"


def test_a_word_survives_canonicalisation_unchanged() -> None:
    plugin = _plugin()
    assert plugin.canonicalize(GUJARAT.encode()).decode() == GUJARAT


def test_zwj_and_zwnj_are_preserved() -> None:
    """REQ-CAN-005: deleting these changes the word, so they survive."""
    plugin = _plugin()
    assert plugin.canonicalize(ZWNJ_CONJUNCT.encode()) == ZWNJ_CONJUNCT.encode()
    assert plugin.canonicalize(ZWJ_CONJUNCT.encode()) == ZWJ_CONJUNCT.encode()


def test_gujarati_digits_are_not_transliterated() -> None:
    plugin = _plugin()
    assert plugin.canonicalize(DIGITS.encode()).decode() == DIGITS


def test_the_base_rules_still_apply_through_the_plugin() -> None:
    """CRLF and soft hyphens are cleaned before GU-R01 runs."""
    plugin = _plugin()
    raw = ("\u0a97\r\n\u0ac1\u00ad\u0a9c\r\n").encode()
    assert plugin.canonicalize(raw) == "\u0a97\n\u0ac1\u0a9c\n".encode()


def test_the_plugin_is_deterministic_and_returns_bytes() -> None:
    plugin = _plugin()
    a = plugin.canonicalize(GUJARAT.encode())
    b = plugin.canonicalize(GUJARAT.encode())
    assert isinstance(a, bytes) and a == b


def test_meta_records_the_plugins_own_rules_and_provenance() -> None:
    meta = _plugin().canonicalize_with_meta(GUJARAT.encode())
    assert meta["canonicalizer_version"] == "gu-1"
    assert meta["applied_rules"] == ["CAN-R01", "CAN-R02", "CAN-R05", "GU-R01"]


# --------------------------------------------------------------------------- #
# 3. provenance reaches the archive, and the default path does not move
# --------------------------------------------------------------------------- #

def test_an_archive_records_the_plugin_provenance() -> None:
    plugin = _plugin()
    payload = plugin.canonicalize((GUJARAT + "\n").encode())
    archive = container.pack(payload, canonicalizer_version=plugin.provenance)
    info = container.unpack_header(archive)
    assert info.canonicalizer_version == "gu-1"
    assert container.unpack(archive) == payload


def test_the_default_header_is_unchanged_byte_for_byte() -> None:
    """A plugin must not move what a user who never mentions Gujarati gets."""
    payload = b"plain english\n"
    assert container.pack(payload) == container.pack(payload, canonicalizer_version=None)


_BLOCKER = r'''
import sys

class Blocker:
    def find_spec(self, name, path=None, target=None):
        if name.split(".")[0] == "lexora_lang_gu":
            raise ImportError("lexora_lang_gu is deliberately unavailable here")
        return None

sys.meta_path.insert(0, Blocker())

try:
    import lexora_lang_gu  # noqa: F401
except ImportError:
    pass
else:
    raise SystemExit("the blocker did not block")

from lexora import langapi
from lexora.container import unpack, unpack_header

archive = open(sys.argv[1], "rb").read()
if "gu" in langapi.available():
    raise SystemExit("the plugin was discovered in a process that must not have it")
info = unpack_header(archive)
sys.stdout.buffer.write(info.canonicalizer_version.encode() + b"\n")
sys.stdout.buffer.write(unpack(archive))
'''


def test_a_gu_archive_is_readable_where_the_plugin_does_not_exist(tmp_path) -> None:
    """The v1.0 condition: an archive written with a plugin is readable without it."""
    plugin = _plugin()
    payload = plugin.canonicalize((GUJARAT + " " + ZWNJ_CONJUNCT + "\n").encode())
    archive = container.pack(payload, canonicalizer_version=plugin.provenance)
    path = tmp_path / "gu.lxz"
    path.write_bytes(archive)

    env = dict(os.environ)
    env["PYTHONPATH"] = str(REPO_ROOT / "src") + os.pathsep + env.get("PYTHONPATH", "")
    result = subprocess.run([sys.executable, "-c", _BLOCKER, str(path)],
                            capture_output=True, env=env, timeout=120)
    assert result.returncode == 0, result.stderr.decode()
    label, _, decoded = result.stdout.partition(b"\n")
    assert label == b"gu-1"
    assert decoded == payload
