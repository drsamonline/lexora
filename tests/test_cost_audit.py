"""REQ-CMP-004 — the cost model's accounting must close against the file, exactly.

[COST_MODEL.md](../docs/COST_MODEL.md)'s first rule is "nothing is free": if the decoder needs a
byte, that byte counts. `benchmarks/cost_audit.py` decomposes an `.lxz` into the model's terms and
demands the sum equal the file size with **no tolerance** — a tolerance is where an unaccounted
field hides.

The two failures this guards against are both flattering, which is why they survive review:

* charging the index entry to `blockMetadata` **and** `indexContribution` makes the accounting
  56 bytes per block larger than the archive — it looks like the codec is doing better than it is;
* forgetting the 40-byte trailer makes it smaller — it looks like a saving.

So the tests assert exactness, assert which term owns the index bytes, and mutate a real archive to
prove the auditor is measuring rather than echoing a number it was handed.
"""

from __future__ import annotations

import json
import pathlib
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "benchmarks"))

import cost_audit  # noqa: E402  (path insertion must come first)
from lexora import container  # noqa: E402

PAYLOAD = b"the quick brown fox jumps over the lazy dog\n" * 200


@pytest.fixture()
def single(tmp_path) -> pathlib.Path:
    p = tmp_path / "single.lxz"
    p.write_bytes(container.pack(PAYLOAD, level=9))
    return p


@pytest.fixture()
def multi(tmp_path) -> pathlib.Path:
    p = tmp_path / "multi.lxz"
    p.write_bytes(container.pack(PAYLOAD, level=9, block_size=1024))
    return p


def test_the_accounting_closes_exactly(single) -> None:
    report = cost_audit.account(single)
    assert report["unaccounted_bytes"] == 0, (
        f"{report['unaccounted_bytes']} byte(s) in the archive belong to no cost-model term"
    )
    assert report["accounted_bytes"] == report["actual_bytes"] == single.stat().st_size
    assert report["verdict"] == "PASS"


def test_every_term_the_requirement_names_is_present(single) -> None:
    """REQ-CMP-004 names headers, side tables, dictionaries, grammar stores and block metadata.

    A term that is zero must still be *reported* as zero — an absent term is indistinguishable
    from a forgotten one.
    """
    components = cost_audit.account(single)["components"]
    for term in ("payload_bytes", "block_metadata_bytes", "archive_header_bytes",
                 "archive_trailer_bytes", "side_tables_bytes", "dictionary_bytes",
                 "residual_bytes"):
        assert term in components, f"the audit does not account for {term}"
    assert components["side_tables_bytes"] == 0 and components["dictionary_bytes"] == 0, (
        "v0 carries neither a grammar store nor a dictionary — if that changes, the audit and "
        "COST_MODEL.md change in the same commit"
    )


def test_the_index_is_charged_once_not_twice(multi) -> None:
    """The double-count trap. 56 bytes a block is the index entry's whole footprint."""
    report = cost_audit.account(multi)
    components = report["components"]
    assert report["blocks"] > 1, "this test needs a multi-block archive to be meaningful"
    assert components["block_metadata_bytes"] == report["blocks"] * container.INDEX_ENTRY_SIZE
    assert components["index_contribution_bytes"] == 0, (
        "the index bytes are already in block_metadata_bytes; charging them again inflates the "
        "accounting by 56 bytes a block and flatters the codec"
    )
    # and the arithmetic that would result from the double count is measurably wrong
    doubled = report["accounted_bytes"] + components["block_metadata_bytes"]
    assert doubled > report["actual_bytes"]


def test_the_payload_term_is_the_compressed_bytes(multi) -> None:
    data = multi.read_bytes()
    info, _, _ = container.read_index(data)
    expected = sum(b.compressed_size for b in info.blocks)
    assert cost_audit.account(multi)["components"]["payload_bytes"] == expected


def test_the_layout_has_no_hidden_padding(multi) -> None:
    layout = cost_audit.account(multi)["layout"]
    assert layout["gap_before_index"] == 0, "bytes sit between the last block and the index"
    assert layout["gap_before_trailer"] == 0, "bytes sit between the index and the trailer"


def test_a_byte_inserted_before_the_trailer_is_reported_as_unaccounted(single, tmp_path) -> None:
    """The mutation: the auditor must notice a byte nobody's formula mentions.

    Inserted *before* the trailer rather than appended, because the trailer sits at EOF — appending
    shifts the reader's 40-byte window and produces an unreadable file instead of an unaccounted
    byte (that case is the next test). A byte in the gap is the honest simulation of a layout
    change nobody wrote into the model.
    """
    raw = single.read_bytes()
    mutated = tmp_path / "mutated.lxz"
    mutated.write_bytes(raw[:-container.TRAILER_SIZE] + b"\x00" + raw[-container.TRAILER_SIZE:])
    report = cost_audit.account(mutated)
    assert report["unaccounted_bytes"] == 1
    assert report["layout"]["gap_before_trailer"] == 1
    assert report["verdict"] == "FAIL"


def test_the_cli_fails_on_an_unaccounted_byte(single, tmp_path) -> None:
    raw = single.read_bytes()
    mutated = tmp_path / "mutated.lxz"
    mutated.write_bytes(raw[:-container.TRAILER_SIZE] + b"\x00" + raw[-container.TRAILER_SIZE:])
    assert cost_audit.main(["--archive", str(mutated)]) == 2
    assert cost_audit.main(["--archive", str(single)]) == 0


def test_a_byte_appended_to_the_end_is_refused_not_scored(single, tmp_path) -> None:
    """Appending corrupts the trailer, so the honest answer is a refusal — not a residual of 1."""
    mutated = tmp_path / "appended.lxz"
    mutated.write_bytes(single.read_bytes() + b"\x00")
    with pytest.raises(cost_audit.CostError):
        cost_audit.account(mutated)
    assert cost_audit.main(["--archive", str(mutated)]) == 3


def test_a_truncated_archive_is_refused_not_scored(single, tmp_path) -> None:
    """A file whose trailer is gone cannot be decomposed — refusing beats inventing a residual."""
    truncated = tmp_path / "truncated.lxz"
    truncated.write_bytes(single.read_bytes()[:-1])
    with pytest.raises(cost_audit.CostError):
        cost_audit.account(truncated)
    assert cost_audit.main(["--archive", str(truncated)]) == 3


def test_a_file_that_is_not_an_archive_is_refused(tmp_path) -> None:
    junk = tmp_path / "junk.lxz"
    junk.write_bytes(b"not an archive at all")
    assert cost_audit.main(["--archive", str(junk)]) == 3


def test_the_json_report_is_machine_readable(single, tmp_path) -> None:
    out = tmp_path / "report.json"
    assert cost_audit.main(["--archive", str(single), "--json", "--out", str(out)]) == 0
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert doc["requirement"] == "REQ-CMP-004"
    assert doc["verdict"] == "PASS"
    assert doc["unaccounted_bytes"] == 0
