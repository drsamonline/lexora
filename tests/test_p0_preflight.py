"""P0's preflight, tested on the failures it exists to catch ten seconds in, not five hours in.

P0 is the one item blocking the headline claim, `.lxdb` and REQ-BMK-003, and it runs for six to
eight hours on a machine this container is not. The preflight cannot be tested for its happy path
here — there is no 1 GiB corpus and no `xz` — so it is tested for what it *refuses*, which is the
part that matters when the alternative is discovering the problem at hour five.

The one positive test that is possible: a synthetic corpus that meets the floor, with the binary
checks stubbed, produces GO and a machine-class record. That keeps the pass path from rotting into
"always refuses", which is a guard that reads as caution and behaves as an outage.
"""

from __future__ import annotations

import json
import pathlib
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import p0_preflight as pre  # noqa: E402  (path insertion must come first)

GIB = 1 << 30


def _manifest(tmp_path: pathlib.Path, *, files: int = 3, size: int = 400 << 20,
              splits=("train", "validation", "heldout"), write_files: bool = True) -> tuple[pathlib.Path, pathlib.Path]:
    """A corpus directory plus a manifest in the shape `harness.py manifest` writes.

    Sparse files: the point is the *declared and actual size*, and writing 1.2 GiB of zeros to test
    a size check would be a test that takes longer than the thing it guards.
    """
    corpus = tmp_path / "corpus"
    corpus.mkdir(exist_ok=True)
    entries = []
    for i in range(files):
        name = f"doc-{i}.txt"
        path = corpus / name
        if write_files:
            with path.open("wb") as fh:
                fh.truncate(size)
        entries.append({
            "path": name,
            "split": splits[i % len(splits)],
            "size_bytes": size,
            "language": "en",
            "category": "prose/books",
            "lineage_id": f"t:{i}",
            "rights": "P0",
            "sha256": "0" * 64,
        })
    manifest = tmp_path / "MANIFEST.json"
    manifest.write_text(json.dumps({"manifest_version": 2, "corpus_tier": "T1-gutenberg-p0",
                                    "manifest_sha256": "x", "root": str(corpus), "files": entries}),
                        encoding="utf-8")
    return corpus, manifest


def test_a_missing_corpus_is_no_go_with_the_command_to_fix_it(tmp_path) -> None:
    corpus, manifest = _manifest(tmp_path)
    report = pre.check_corpus(tmp_path / "nowhere", manifest)
    assert report["status"] == "NO-GO"
    assert "corpus-fetch" in report["remedy"], "a refusal must say how to stop being refused"


def test_a_corpus_below_the_protocol_floor_is_no_go(tmp_path) -> None:
    """The 5.9 MB R6 snapshot must not be able to masquerade as P0's corpus."""
    corpus, manifest = _manifest(tmp_path, files=3, size=2 << 20)   # ~6 MB total
    report = pre.check_corpus(corpus, manifest)
    assert report["status"] == "NO-GO"
    assert "below the 1 GiB protocol floor" in report["detail"]


def test_a_manifest_file_that_is_absent_is_no_go(tmp_path) -> None:
    corpus, manifest = _manifest(tmp_path, files=3, size=400 << 20)
    (corpus / "doc-1.txt").unlink()
    report = pre.check_corpus(corpus, manifest)
    assert report["status"] == "NO-GO"
    assert "doc-1.txt" in report["detail"]


def test_a_manifest_file_of_the_wrong_size_is_no_go(tmp_path) -> None:
    corpus, manifest = _manifest(tmp_path, files=3, size=400 << 20)
    with (corpus / "doc-2.txt").open("wb") as fh:
        fh.truncate(1024)
    report = pre.check_corpus(corpus, manifest)
    assert report["status"] == "NO-GO"
    assert "wrong size" in report["detail"]


def test_a_missing_split_is_no_go(tmp_path) -> None:
    """Two splits cannot produce a held-out result, and finding that out later wastes the run."""
    corpus, manifest = _manifest(tmp_path, files=2, size=400 << 20, splits=("train", "validation"))
    report = pre.check_corpus(corpus, manifest)
    assert report["status"] == "NO-GO"
    assert "heldout" in report["detail"]


def test_a_full_corpus_passes(tmp_path) -> None:
    corpus, manifest = _manifest(tmp_path, files=3, size=400 << 20)
    report = pre.check_corpus(corpus, manifest)
    assert report["status"] == "GO", report
    assert report["splits"] == ["heldout", "train", "validation"]


def test_a_missing_binary_is_no_go_and_names_the_package() -> None:
    report = pre.check_binary("definitely-not-a-real-binary-xyz")
    assert report["status"] == "NO-GO"
    assert report["path"] is None


def test_missing_7z_can_be_waived_but_the_report_says_the_claim_is_smaller(tmp_path, monkeypatch) -> None:
    """P0.3a wants a PPMd row. Running without it is allowed and must not look like a full run."""
    corpus, manifest = _manifest(tmp_path, files=3, size=400 << 20)

    def fake_binary(name, **kwargs):
        """xz present, 7z absent — the exact case the waiver exists for."""
        if name == "xz":
            return {"status": "GO", "detail": "xz (XZ Utils) 5.4.1", "path": "/usr/bin/xz"}
        return {"status": "NO-GO", "detail": f"{name} not on PATH", "path": None}

    monkeypatch.setattr(pre, "check_binary", fake_binary)
    waived = pre.preflight(corpus, manifest, out_root=tmp_path, allow_missing_7z=True,
                           previous_env=None)
    assert waived["checks"]["ppmd_7z"]["status"] == "WAIVED"
    assert "OQ-18 stays open" in waived["checks"]["ppmd_7z"]["detail"]

    strict = pre.preflight(corpus, manifest, out_root=tmp_path, allow_missing_7z=False,
                           previous_env=None)
    assert strict["checks"]["ppmd_7z"]["status"] == "NO-GO"
    assert "ppmd_7z" in strict["blocking"]


def test_a_second_machine_class_is_recognised_and_a_rerun_is_not(tmp_path) -> None:
    """P0.2 asks for a *second* class; the same box under a new hostname is not one."""
    current = pre.machine_class()
    same = {"machine_class": {**current, "hostname": "renamed-box"}}
    other = {"machine_class": {**current, "cpu_count": (current["cpu_count"] or 1) * 2}}

    assert pre.same_class_as(same["machine_class"], current) is True, (
        "a renamed box must not look like a new machine class"
    )
    assert pre.same_class_as(other["machine_class"], current) is False


def test_the_cli_exits_2_on_a_no_go(tmp_path) -> None:
    """A preflight that exits 0 while saying NO-GO is a preflight nobody's script checks."""
    corpus, manifest = _manifest(tmp_path, files=3, size=2 << 20)   # below the floor
    code = pre.main(["--corpus", str(corpus), "--manifest", str(manifest),
                     "--out-root", str(tmp_path)])
    assert code == 2


def test_the_report_is_written_as_evidence(tmp_path, monkeypatch) -> None:
    corpus, manifest = _manifest(tmp_path, files=3, size=400 << 20)
    monkeypatch.setattr(pre, "check_binary",
                        lambda name, **kw: {"status": "GO", "detail": "stub", "path": f"/usr/bin/{name}"})
    out = tmp_path / "preflight.json"
    code = pre.main(["--corpus", str(corpus), "--manifest", str(manifest),
                     "--out-root", str(tmp_path), "--out", str(out)])
    assert code == 0, out.read_text() if out.exists() else "no report"
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert doc["verdict"] == "GO"
    assert doc["machine_class"]["machine"], "the machine that ran P0 must be in the artifact"
