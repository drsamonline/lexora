"""The language-plugin contract (ADR-0022), and proof that it rejects bad plugins.

A contract that has only ever seen a valid implementation is not a contract — it is a
description of English. So the second half of this file is a set of deliberately broken
plugins, each of which must fail for the *specific* reason it was broken.

The English plugin is the reference implementation: if it ever fails these tests, the
seam and the shipped language have diverged.
"""

from __future__ import annotations

import pytest

from lexora import langapi
from lexora.langapi import LanguagePlugin
from lexora.languages import english


def _valid(**overrides) -> LanguagePlugin:
    base = dict(
        id="xx", version=1, name="Testish",
        canonicalize=lambda raw, **kw: raw.replace(b"\r\n", b"\n"),
    )
    base.update(overrides)
    return LanguagePlugin(**base)


# --------------------------------------------------------------------------- #
# the reference implementation
# --------------------------------------------------------------------------- #

def test_english_is_discoverable_and_valid() -> None:
    plugin = langapi.get("en")
    assert plugin.name == "English"
    assert langapi.contract_violations(plugin) == []


def test_english_keeps_the_historical_provenance_label() -> None:
    """`lexcan-0.1`, not `en-1` — renaming would rewrite every archive's header.

    ADR-0020 had already changed that field once, yesterday. A plugin seam is not a
    good enough reason to do it again for no reader benefit.
    """
    assert langapi.get("en").provenance == "lexcan-0.1"


def test_english_delegates_its_rules_rather_than_copying_them() -> None:
    """One source of truth: the plugin must call the canonicaliser, not reimplement it."""
    from lexora.canonicalize import canonicalize

    assert english.PLUGIN.canonicalize is canonicalize


def test_default_is_english_and_named_explicitly() -> None:
    assert langapi.default().id == "en"


def test_the_report_is_doctor_ready() -> None:
    rows = langapi.report()
    assert any(r["id"] == "en" and r["status"] == "ok" for r in rows)
    for row in rows:
        assert set(row) == {"id", "name", "provenance", "tokenizer", "status"}


# --------------------------------------------------------------------------- #
# the contract rejects what it should
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("overrides,expected", [
    ({"id": "English"}, "lowercase alphanumeric"),
    ({"id": "e"}, "lowercase alphanumeric"),
    ({"id": "en-gb"}, "lowercase alphanumeric"),
    ({"id": "x" * 12}, "lowercase alphanumeric"),
    ({"version": 0}, "positive integer"),
    ({"version": "1"}, "positive integer"),
    ({"name": "  "}, "non-empty human-readable"),
    ({"tokenizer": "snowball"}, "not one of"),
    ({"canonicalize": None}, "canonicalize is required"),
    ({"ocr_languages": ["eng"]}, "tuple"),
    ({"provenance_label": "way-too-long-label"}, "at most"),
    ({"provenance_label": "has spaces"}, "ASCII letters"),
])
def test_each_violation_is_caught_for_its_own_reason(overrides, expected) -> None:
    problems = langapi.contract_violations(_valid(**overrides))
    assert problems, f"{overrides} produced no violation"
    assert any(expected in p for p in problems), f"expected {expected!r} in {problems}"


def test_a_plugin_that_returns_str_is_rejected() -> None:
    problems = langapi.contract_violations(
        _valid(canonicalize=lambda raw, **kw: "text, not bytes")
    )
    assert any("not bytes" in p for p in problems)


def test_a_plugin_that_raises_on_trivial_input_is_rejected() -> None:
    def boom(raw, **kw):
        raise ValueError("cannot clean")

    problems = langapi.contract_violations(_valid(canonicalize=boom))
    assert any("raised on trivial input" in p for p in problems)


def test_a_nondeterministic_plugin_is_rejected() -> None:
    """Determinism is REQ-CAN-001; a plugin that varies makes archives incomparable."""
    calls = {"n": 0}

    def unstable(raw, **kw):
        calls["n"] += 1
        return raw + str(calls["n"]).encode()

    problems = langapi.contract_violations(_valid(canonicalize=unstable))
    assert any("not deterministic" in p for p in problems)


def test_a_non_plugin_object_is_rejected_with_a_useful_message() -> None:
    problems = langapi.contract_violations(object())
    assert problems and "not a LanguagePlugin" in problems[0]


def test_all_problems_are_reported_at_once() -> None:
    """A contract that reports one problem per run wastes the author's afternoon."""
    problems = langapi.contract_violations(
        _valid(id="BAD ID", version=0, name="", tokenizer="nope", canonicalize=None)
    )
    assert len(problems) >= 5, problems


# --------------------------------------------------------------------------- #
# registry behaviour
# --------------------------------------------------------------------------- #

def test_unknown_language_lists_what_is_available() -> None:
    # `zz` and not `hi`: Hindi is a real plugin package now (packages/lexora-lang-hi),
    # so asserting that `hi` is absent made this test fail on exactly the machines
    # that had done the thing the seam exists for. An id no plugin would claim is
    # what "unknown" means.
    with pytest.raises(langapi.LanguageError) as excinfo:
        langapi.get("zz")
    message = str(excinfo.value)
    assert "no language plugin" in message and "en" in message


def test_a_broken_installed_plugin_does_not_break_discovery(monkeypatch) -> None:
    """A third-party plugin that fails to import must not take the CLI down with it."""

    class _EP:
        name = "bad"
        value = "badpkg:plugin"

        def load(self):
            raise ImportError("badpkg is broken")

    monkeypatch.setattr(langapi, "_installed",
                        lambda: [(LanguagePlugin(id="zz", version=1, name="broken"),
                                  ["failed to load: ImportError: badpkg is broken"],
                                  "bad (badpkg:plugin)")])
    plugins = langapi.available()          # must not raise
    assert "en" in plugins                  # built-ins still usable
    rows = langapi.report()
    assert any(r["status"].startswith("invalid: failed to load") for r in rows)


def test_installed_plugin_cannot_shadow_a_builtin(monkeypatch) -> None:
    clash = _valid(id="en", name="Impostor")
    monkeypatch.setattr(langapi, "_installed", lambda: [(clash, [], "impostor (pkg:fn)")])
    plugins = langapi.available()
    assert plugins["en"].name == "English", "a third-party plugin shadowed a built-in"
