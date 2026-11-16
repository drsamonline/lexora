"""`--language` on the CLI — PATH_TO_V1 P3.6.

The seam (ADR-0022) was proven by two languages but only *in the library*: a plugin
could be imported and called, and nothing a user types could reach it. P3.6 is the
one-flag difference between "the interface exists" and "the interface is usable".

Five properties, in order of what they protect:

1. **`canon --language hi` actually cleans with the plugin.** Two spellings of the
   same Devanagari word converge on one byte string, which the built-in rules do not
   do. Asserted as a *difference* from the default path, so a regression that quietly
   routes `--language` back to English fails here.
2. **`pack --language hi` records `hi-1`** in the header, and the archive still
   decodes — provenance is a label, not a dependency (ADR-0023).
3. **The default is unchanged.** `--language en`, and no flag at all, must produce
   byte-identical output to the pre-P3.6 CLI. This is the whole risk of the change:
   every existing archive was written by the built-in path.
4. **An unknown id is a usage error (exit 2) that names what is installed** — not a
   traceback, and not exit 4, because nothing was canonicalized.
5. **`--meta` keeps its one contract**: JSON on stdout, payload never on stdout.
"""

from __future__ import annotations

import json

import pytest

from lexora import cli, container, langapi

#: Devanagari fixtures written as code points, so the editor cannot normalise them.
NUQTA_PRECOMPOSED = "\u0958"          # क़ as one letter (a composition exclusion)
NUQTA_DECOMPOSED = "\u0915\u093c"     # क + COMBINING NUKTA


def _hindi_available() -> bool:
    try:
        langapi.get("hi")
    except langapi.LanguageError:
        return False
    return True


pytestmark = pytest.mark.skipif(
    not _hindi_available(),
    reason="lexora-lang-hi is not installed (pip install -e packages/lexora-lang-hi)",
)


def test_canon_language_hi_cleans_where_the_builtin_does_not(tmp_path):
    """The plugin's rule is visible from the CLI, and it is not the built-in rule."""
    pre = tmp_path / "pre.txt"
    dec = tmp_path / "dec.txt"
    pre.write_text(NUQTA_PRECOMPOSED + "\n", encoding="utf-8")
    dec.write_text(NUQTA_DECOMPOSED + "\n", encoding="utf-8")

    hi_pre, hi_dec = tmp_path / "hi-pre.txt", tmp_path / "hi-dec.txt"
    assert cli.main(["canon", "--in", str(pre), "--out", str(hi_pre), "--language", "hi"]) == 0
    assert cli.main(["canon", "--in", str(dec), "--out", str(hi_dec), "--language", "hi"]) == 0
    # One byte string for one word: that is HI-R01, and it is the reason to select it.
    assert hi_pre.read_bytes() == hi_dec.read_bytes()

    en_pre, en_dec = tmp_path / "en-pre.txt", tmp_path / "en-dec.txt"
    assert cli.main(["canon", "--in", str(pre), "--out", str(en_pre)]) == 0
    assert cli.main(["canon", "--in", str(dec), "--out", str(en_dec)]) == 0
    # The default path does NOT converge them — so the assertion above is about the
    # plugin, not about the fixture being trivially equal.
    assert en_pre.read_bytes() != en_dec.read_bytes()


def test_canon_language_hi_reports_the_plugin_provenance(tmp_path, capsys):
    raw = tmp_path / "raw.txt"
    raw.write_bytes(b"hello\r\nworld\r\n")
    out = tmp_path / "canon.txt"
    assert cli.main(["canon", "--in", str(raw), "--out", str(out), "--language", "hi"]) == 0
    err = capsys.readouterr().err
    assert "hi-1" in err
    assert "lexcan-0.1" not in err


def test_canon_language_hi_meta_is_json_on_stdout_only(tmp_path, capsys):
    raw = tmp_path / "raw.txt"
    raw.write_bytes((NUQTA_DECOMPOSED + "\r\n").encode("utf-8"))
    assert cli.main(["canon", "--in", str(raw), "--out", "-", "--language", "hi",
                     "--meta"]) == 0
    captured = capsys.readouterr()
    meta = json.loads(captured.out)          # pure JSON: no payload leaked into stdout
    assert meta["canonicalizer_version"] == "hi-1"
    assert "HI-R01" in meta["applied_rules"]


def test_pack_language_hi_writes_the_provenance_into_the_header(tmp_path):
    raw = tmp_path / "raw.txt"
    raw.write_bytes((NUQTA_DECOMPOSED + "\n").encode("utf-8"))
    canon = tmp_path / "canon.txt"
    assert cli.main(["canon", "--in", str(raw), "--out", str(canon), "--language", "hi"]) == 0

    archive = tmp_path / "doc.lxz"
    assert cli.main(["pack", "--in", str(canon), "--out", str(archive),
                     "--language", "hi"]) == 0
    info, _, _ = container.read_index(archive.read_bytes())
    assert info.canonicalizer_version == "hi-1"

    # Readable without the plugin: provenance is a label, never a dependency.
    back = tmp_path / "back.txt"
    assert cli.main(["unpack", "--in", str(archive), "--out", str(back)]) == 0
    assert back.read_bytes() == canon.read_bytes()


def test_pack_default_and_explicit_en_are_byte_identical(tmp_path):
    """The change must not move a single byte of an archive written without a flag."""
    payload = tmp_path / "canon.txt"
    payload.write_bytes(("hello\r\nworld \u00ad" * 50).encode("utf-8"))

    a, b = tmp_path / "default.lxz", tmp_path / "en.lxz"
    assert cli.main(["pack", "--in", str(payload), "--out", str(a)]) == 0
    assert cli.main(["pack", "--in", str(payload), "--out", str(b), "--language", "en"]) == 0
    assert a.read_bytes() == b.read_bytes()
    info, _, _ = container.read_index(a.read_bytes())
    assert info.canonicalizer_version == "lexcan-0.1"


def test_canon_default_output_is_byte_identical_to_explicit_en(tmp_path):
    raw = tmp_path / "raw.txt"
    raw.write_bytes(b"a\r\nb\xc2\xadc\r\n")
    d, e = tmp_path / "d.txt", tmp_path / "e.txt"
    assert cli.main(["canon", "--in", str(raw), "--out", str(d)]) == 0
    assert cli.main(["canon", "--in", str(raw), "--out", str(e), "--language", "en"]) == 0
    assert d.read_bytes() == e.read_bytes() == b"a\nbc\n"


@pytest.mark.parametrize("verb", ["canon", "pack"])
def test_unknown_language_is_a_usage_error_naming_what_is_installed(tmp_path, capsys, verb):
    src = tmp_path / "in.bin"
    src.write_bytes(b"x\r\n")
    argv = [verb, "--in", str(src), "--out", str(tmp_path / "out"), "--language", "zz"]
    assert cli.main(argv) == 2
    err = capsys.readouterr().err
    assert "usage error" in err
    assert "zz" in err
    # The message must be actionable: the installed ids are the answer to "what then?".
    assert "hi" in err and "en" in err


def test_language_option_is_documented_in_the_reference():
    """A flag a user cannot read about does not exist (the CLI_REFERENCE guard)."""
    from pathlib import Path

    text = (Path(__file__).resolve().parents[1] / "docs" / "CLI_REFERENCE.md").read_text()
    assert text.count("--language") >= 2, "canon and pack both carry --language"
