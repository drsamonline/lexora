"""The third language plugin — and the capability the seam was written for.

ADR-0022 lists four things a plugin may declare and says which one matters most: *the
search tokenizer*. `hi` proved the seam is an interface rather than a description of
English, but it declared the same `unicode61` tokenizer English does, because both
scripts are written with spaces. A third language that declares a *different* tokenizer
is what turns that sentence into a claim, and that is what this file tests.

The order of the assertions follows what would go wrong without each one:

1. **The package registers the way ADR-0022 says** — one entry point, no core change,
   the core still ships English only.
2. **It cleans something real, and stops where it must** — ZH-R01 folds full-width ASCII
   letters and digits, which NFC does not; it does not fold full-width punctuation, and
   it does not convert traditional to simplified.
3. **It does NOT carry a rule it does not need** — every CJK Compatibility Ideograph is
   already folded by NFC, which is asserted here so nobody adds the rule back.
4. **The tokenizer is real** — it is declared as `trigram`, and the reason is measured
   in `tests/test_catalog_tokenizer.py` rather than asserted as a preference.
5. **The archive stays readable without the plugin** — the v1.0 condition.

Nothing here re-implements the plugin's rules: the test imports the shipped package.
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
PACKAGE_DIR = REPO_ROOT / "packages" / "lexora-lang-zh"
PLUGIN_SRC = PACKAGE_DIR / "src"

#: Written with explicit code points so the test does not depend on the editor.
FULLWIDTH_ABC = "\uff21\uff22\uff23"     # ＡＢＣ
FULLWIDTH_2024 = "\uff12\uff10\uff12\uff14"  # ２０２４
IDEOGRAPHIC_SPACE = "\u3000"
FULLWIDTH_COMMA = "\uff0c"                # ， — punctuation, must survive
HAN_SENTENCE = "\u4eca\u5929\u5929\u6c14\u5f88\u597d"   # 今天天气很好
COMPAT_IDEOGRAPH = "\uf900"               # 豈, compatibility form of U+8C48
UNIFIED_IDEOGRAPH = "\u8c48"


def _plugin():
    """The shipped plugin object, imported from the package directory."""
    if str(PLUGIN_SRC) not in sys.path:
        sys.path.insert(0, str(PLUGIN_SRC))
    import lexora_lang_zh

    return lexora_lang_zh.plugin()


# --------------------------------------------------------------------------- #
# 1. the seam, declared the way a third-party package declares it
# --------------------------------------------------------------------------- #

def test_the_package_declares_the_entry_point_adr_0022_requires() -> None:
    data = tomllib.loads((PACKAGE_DIR / "pyproject.toml").read_text())
    eps = data["project"]["entry-points"]["lexora.languages"]
    assert eps == {"zh": "lexora_lang_zh:plugin"}, eps


def test_the_entry_point_target_loads_and_satisfies_the_contract() -> None:
    plugin = _plugin()
    assert langapi.contract_violations(plugin) == []
    assert plugin.id == "zh"
    assert plugin.provenance == "zh-1"
    assert plugin.tokenizer == "trigram"          # the whole point of this language
    assert plugin.ocr_languages == ("chi_sim",)


def test_the_core_still_ships_english_only() -> None:
    """The third language arrived as a package, exactly as the second one did."""
    assert [p.id for p in langapi._builtins()] == ["en"]


def test_the_installed_plugin_is_discovered_through_metadata() -> None:
    from importlib.metadata import PackageNotFoundError, distribution

    try:
        distribution("lexora-lang-zh")
    except PackageNotFoundError:
        pytest.skip("lexora-lang-zh is not installed in this environment "
                    "(pip install -e packages/lexora-lang-zh --no-deps)")
    plugin = langapi.get("zh")
    assert plugin.name.startswith("Chinese")
    assert langapi.contract_violations(plugin) == []


# --------------------------------------------------------------------------- #
# 2. the cleaning rules do something, and stop where they must
# --------------------------------------------------------------------------- #

def test_fullwidth_letters_and_digits_fold_to_ascii() -> None:
    """ZH-R01. Without it one sentence typed on two IMEs is two archives."""
    plugin = _plugin()
    assert plugin.canonicalize(FULLWIDTH_ABC.encode()) == b"ABC"
    assert plugin.canonicalize(FULLWIDTH_2024.encode()) == b"2024"
    # and the base rules alone do NOT do this — the rule is the plugin's
    from lexora.canonicalize import canonicalize as base

    assert base(FULLWIDTH_ABC.encode()) == FULLWIDTH_ABC.encode()


def test_the_ideographic_space_becomes_a_space() -> None:
    plugin = _plugin()
    assert plugin.canonicalize(("a" + IDEOGRAPHIC_SPACE + "b").encode()) == b"a b"


def test_fullwidth_punctuation_is_left_alone() -> None:
    """It is Chinese typography, not a wide spelling of `,`. Folding it changes text."""
    plugin = _plugin()
    raw = (HAN_SENTENCE + FULLWIDTH_COMMA).encode()
    assert plugin.canonicalize(raw) == raw


def test_traditional_and_simplified_are_not_converted() -> None:
    """A content decision with a dictionary behind it, not a cleaning rule."""
    plugin = _plugin()
    traditional = "\u9ad4"       # 體
    assert plugin.canonicalize(traditional.encode()) == traditional.encode()


def test_a_chinese_sentence_survives_unchanged() -> None:
    plugin = _plugin()
    assert plugin.canonicalize(HAN_SENTENCE.encode()) == HAN_SENTENCE.encode()


def test_the_base_rules_still_apply_through_the_plugin() -> None:
    plugin = _plugin()
    assert plugin.canonicalize(b"a\r\nb\r\n") == b"a\nb\n"
    assert plugin.canonicalize("a\u00adb".encode()) == b"ab"


def test_the_plugin_is_deterministic_and_returns_bytes() -> None:
    plugin = _plugin()
    raw = (FULLWIDTH_ABC + "\r\n" + HAN_SENTENCE).encode()
    first = plugin.canonicalize(raw)
    assert isinstance(first, bytes)
    assert plugin.canonicalize(raw) == first


def test_meta_records_the_plugins_own_rules_and_provenance() -> None:
    plugin = _plugin()
    meta = plugin.canonicalize_with_meta(HAN_SENTENCE.encode())
    assert meta["canonicalizer_version"] == "zh-1"
    assert "ZH-R01" in meta["applied_rules"]
    assert meta["canonical"] == HAN_SENTENCE.encode()


# --------------------------------------------------------------------------- #
# 3. the rule this plugin deliberately does NOT carry
# --------------------------------------------------------------------------- #

def test_nfc_already_folds_every_cjk_compatibility_ideograph() -> None:
    """Measured, not assumed: 1002 of them, all canonical singleton mappings.

    So a `ZH-R02` that folded compatibility ideographs would be dead code. This test
    exists to stop the next reader from adding it back.
    """
    blocks = list(range(0xF900, 0xFB00)) + list(range(0x2F800, 0x2FA20))
    folded = [cp for cp in blocks
              if unicodedata.normalize("NFC", chr(cp)) != chr(cp)]
    assert len(folded) == 1002
    # the plugin therefore adds nothing here beyond the base rules
    assert unicodedata.normalize("NFC", COMPAT_IDEOGRAPH) == UNIFIED_IDEOGRAPH


def test_the_compatibility_form_reaches_one_archive_through_the_base_rules() -> None:
    plugin = _plugin()
    assert plugin.canonicalize(COMPAT_IDEOGRAPH.encode()) == \
        plugin.canonicalize(UNIFIED_IDEOGRAPH.encode())


# --------------------------------------------------------------------------- #
# 4. the archive: provenance recorded, and readable without the plugin
# --------------------------------------------------------------------------- #

def test_an_archive_records_the_plugin_provenance() -> None:
    plugin = _plugin()
    payload = plugin.canonicalize(FULLWIDTH_ABC.encode())
    archive = container.pack(payload, canonicalizer_version=plugin.provenance)
    info = container.unpack_header(archive)
    assert info.canonicalizer_version == "zh-1"
    assert container.unpack(archive) == payload


def test_the_default_header_is_unchanged_byte_for_byte() -> None:
    payload = b"unchanged\n"
    assert (container.pack(payload)
            == container.pack(payload, canonicalizer_version=None)
            == container.pack(payload, canonicalizer_version="lexcan-0.1"))


_BLOCKER = r'''
import sys

class Blocker:
    def find_spec(self, name, path=None, target=None):
        if name.split(".")[0] == "lexora_lang_zh":
            raise ImportError("lexora_lang_zh is deliberately unavailable here")
        return None

sys.meta_path.insert(0, Blocker())

try:
    import lexora_lang_zh  # noqa: F401
except ImportError:
    pass
else:
    raise SystemExit("the blocker did not block")

from lexora import langapi
from lexora.container import unpack, unpack_header

archive = open(sys.argv[1], "rb").read()
if "zh" in langapi.available():
    raise SystemExit("the plugin was discovered in a process that must not have it")
info = unpack_header(archive)
sys.stdout.buffer.write(info.canonicalizer_version.encode() + b"\n")
sys.stdout.buffer.write(unpack(archive))
'''


def test_a_zh_archive_is_readable_where_the_plugin_does_not_exist(tmp_path) -> None:
    """The v1.0 condition, for the third language as for the second."""
    plugin = _plugin()
    payload = plugin.canonicalize((FULLWIDTH_ABC + HAN_SENTENCE + "\n").encode())
    archive = container.pack(payload, canonicalizer_version=plugin.provenance)
    path = tmp_path / "zh.lxz"
    path.write_bytes(archive)

    env = dict(os.environ)
    env["PYTHONPATH"] = str(REPO_ROOT / "src") + os.pathsep + env.get("PYTHONPATH", "")
    result = subprocess.run([sys.executable, "-c", _BLOCKER, str(path)],
                            capture_output=True, env=env, timeout=120)
    assert result.returncode == 0, result.stderr.decode()
    label, _, decoded = result.stdout.partition(b"\n")
    assert label == b"zh-1"
    assert decoded == payload
