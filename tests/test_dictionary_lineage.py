"""REQ-EXP-002 — a learned structure may be induced from the training split and nothing else.

Two questions, and the tests cover both because either alone is a half-truth:

* **bookkeeping** — were the build inputs train-only? Answerable exactly, and refused when the
  manifest places any input in `validation` or `heldout`, or cannot place it at all;
* **leakage** — did held-out text end up in the bytes anyway? zstd dictionaries hold literal
  sampled sequences, so this is checkable: a 24-byte run of held-out prose inside the dictionary
  is a copy, not a coincidence.

The second test is the one that matters, and it is written as a *detection* test: build a
dictionary that includes a held-out document on purpose and require the audit to catch it. A leak
probe that never fires proves nothing — the same reasoning as the cleaning audit's mutation test.
"""

from __future__ import annotations

import json
import pathlib
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "benchmarks"))

import lineage_audit as audit  # noqa: E402  (path insertion must come first)
from lexora import zstd_core  # noqa: E402

MARKER = "the quick brown fox jumps over the lazy dog and keeps running east"


def _manifest(tmp_path: pathlib.Path, *, heldout_marker: bool = True) -> tuple[dict, pathlib.Path]:
    """A tiny corpus laid out like the real one: train samples plus one held-out document."""
    root = tmp_path / "corpus"
    root.mkdir()
    files = []
    for i in range(8):
        p = root / f"train-{i}.txt"
        p.write_text(
            f"training sample {i}: lorem ipsum dolor sit amet consectetur adipiscing elit sed do "
            f"eiusmod tempor incididunt ut labore et dolore magna aliqua number {i}\n",
            encoding="utf-8",
        )
        files.append({"path": p.name, "split": "train", "lineage_id": f"t:{i}"})
    heldout = root / "heldout-0.txt"
    heldout.write_text(
        ("held out document: " + (MARKER if heldout_marker else "different words entirely") + "\n") * 4,
        encoding="utf-8",
    )
    files.append({"path": heldout.name, "split": "heldout", "lineage_id": "h:0"})
    manifest = {"root": str(root), "manifest_sha256": "test", "files": files}
    return manifest, root


def test_build_inputs_must_all_be_train(tmp_path) -> None:
    manifest, _ = _manifest(tmp_path)
    with pytest.raises(audit.LineageError) as excinfo:
        audit.check_build_inputs(manifest, ["train-0.txt", "heldout-0.txt"])
    message = str(excinfo.value)
    assert "heldout" in message and "heldout-0.txt" in message


def test_an_input_the_manifest_cannot_place_is_refused(tmp_path) -> None:
    """"We could not tell which split this came from" is not "it was fine"."""
    manifest, _ = _manifest(tmp_path)
    with pytest.raises(audit.LineageError) as excinfo:
        audit.check_build_inputs(manifest, ["train-0.txt", "mystery-file.txt"])
    assert "cannot place" in str(excinfo.value)


def test_an_empty_input_list_is_refused(tmp_path) -> None:
    manifest, _ = _manifest(tmp_path)
    with pytest.raises(audit.LineageError):
        audit.check_build_inputs(manifest, [])


def test_a_train_only_build_is_accepted_and_recorded(tmp_path) -> None:
    manifest, root = _manifest(tmp_path)
    samples = [str(root / f"train-{i}.txt") for i in range(8)]
    record = audit.check_build_inputs(manifest, samples)
    assert record["inputs"] == 8
    assert record["splits"] == {"train": 8}
    assert len(record["input_sha256"]) == 8, "the audit must record what it trained on, by hash"


def test_a_clean_dictionary_passes(tmp_path) -> None:
    """Built from train only, probed against the held-out document: nothing leaks."""
    manifest, root = _manifest(tmp_path)
    samples = [(root / f"train-{i}.txt").read_bytes() for i in range(8)]
    dictionary = zstd_core.train_dictionary(samples, size=4096)
    report = audit.audit(manifest, dictionary, [str(root / f"train-{i}.txt") for i in range(8)],
                         audit.heldout_texts(manifest))
    assert report["verdict"] == "PASS"
    assert report["leak_count"] == 0
    assert report["heldout_documents_probed"] == 1


def test_the_audit_refuses_a_contaminated_build(tmp_path) -> None:
    """The control that actually catches contamination: the recorded inputs.

    This is the deterministic one. A dictionary trained on nine samples where one was held out can
    come back with **no** verbatim 24-byte run of that document in it — measured here, not assumed
    — so a verbatim probe cannot be the thing standing between a contaminated dictionary and a
    release. The input record can, and does: it refuses by name and by split.
    """
    manifest, root = _manifest(tmp_path)
    samples = [(root / f"train-{i}.txt").read_bytes() for i in range(8)]
    samples.append((root / "heldout-0.txt").read_bytes() * 3)
    dictionary = zstd_core.train_dictionary(samples, size=8192)

    inputs = [str(root / f"train-{i}.txt") for i in range(8)] + [str(root / "heldout-0.txt")]
    with pytest.raises(audit.LineageError) as excinfo:
        audit.audit(manifest, dictionary, inputs, audit.heldout_texts(manifest))
    message = str(excinfo.value)
    assert "heldout" in message and "heldout-0.txt" in message


def test_a_trained_dictionary_is_not_guaranteed_to_show_a_verbatim_leak(tmp_path) -> None:
    """The limitation, pinned so nobody mistakes the probe for the control.

    If this ever starts finding a hit, the trainer changed — worth knowing, but it would not make
    the probe a substitute for auditing the inputs.
    """
    manifest, root = _manifest(tmp_path)
    samples = [(root / f"train-{i}.txt").read_bytes() for i in range(8)]
    samples.append((root / "heldout-0.txt").read_bytes() * 3)
    dictionary = zstd_core.train_dictionary(samples, size=8192)
    assert audit.leak_probe(dictionary, audit.heldout_texts(manifest)) == [], (
        "zstd's trainer now carries verbatim held-out runs — good news for the probe, but the "
        "input audit in check_build_inputs remains the control"
    )


def test_the_probe_reports_where_the_leak_is(tmp_path) -> None:
    """A refusal that says "contaminated" without saying where is not actionable."""
    hits = audit.leak_probe(MARKER.encode("utf-8"), {"doc.txt": "prefix " + MARKER + " suffix"})
    assert hits, "the probe did not find a 52-byte run it was handed verbatim"
    assert hits[0]["document"] == "doc.txt"
    assert hits[0]["sample"] in MARKER or MARKER in hits[0]["sample"]


def test_short_shared_phrases_are_not_reported_as_leaks() -> None:
    """The window exists so ordinary prose overlap does not cry wolf.

    A 12-byte phrase cannot match a 24-byte window, so shared phrasing below the window is
    invisible — which is the point. A 30-byte run is reported.
    """
    assert audit.leak_probe(b"lorem ipsum ", {"doc.txt": "lorem ipsum dolor sit amet"}) == []
    assert audit.leak_probe(b"lorem ipsum dolor sit amet con",
                            {"doc.txt": "lorem ipsum dolor sit amet consectetur"})


def test_the_cli_refuses_with_exit_2(tmp_path) -> None:
    manifest, root = _manifest(tmp_path)
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    dictionary_path = tmp_path / "dict.bin"
    dictionary_path.write_text("not a real dictionary", encoding="utf-8")
    code = audit.main([
        "--manifest", str(manifest_path), "--dictionary", str(dictionary_path),
        "--inputs", str(root / "train-0.txt"), str(root / "heldout-0.txt"),
    ])
    assert code == 2
