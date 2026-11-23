#!/usr/bin/env python3
"""REQ-EXP-002 — prove a learned structure came from the training split, and only from it.

The requirement: *"Learned structures induced only from training split; never from validation or
held-out documents"* (verification method: lineage audit of dictionary build inputs). Until now
that was a sentence in a register with nothing behind it.

Two different questions, and a dictionary needs both answered:

1. **Where did the inputs come from?** This is a bookkeeping question and the only one that can be
   answered exactly. :func:`check_build_inputs` refuses any sample whose manifest split is not
   `train`, and :func:`audit` records the evidence — manifest hash, every input path with its
   split, and the dictionary's own hash — so a later reader can see what was trained on what.

2. **Did held-out text leak in anyway?** Bookkeeping can be right and the dictionary still carry
   held-out bytes — a caller passing the wrong file, a glob that reached too far. zstd dictionaries
   hold *literal* byte sequences sampled from their inputs, so this is checkable rather than
   merely assertable: :func:`leak_probe` slides a window over the held-out documents and reports any
   run long enough to be a copy rather than a coincidence.

The window is 24 bytes on purpose. Prose collides at 8–12 bytes constantly ("the same phrase"),
and a probe that cries wolf on ordinary English is a probe people switch off. At 24 bytes a match
is a copy.

**And the probe is a backstop, not the control — this was measured, not assumed.** Building a
dictionary from nine samples where one was a held-out document produced a dictionary with **no**
24-byte run of that document in it: zstd's trainer keeps the substrings it judges representative,
and one contaminated sample out of nine did not clear that bar. A dictionary can therefore be
trained on held-out text and still pass a verbatim probe. That is why :func:`check_build_inputs` —
the bookkeeping — is the control, and why it refuses an input the manifest cannot place rather
than assuming it was fine. The probe catches the other failure mode: a dictionary that literally
carries held-out bytes, by training, concatenation, or a glob that reached too far.

    python benchmarks/lineage_audit.py --manifest benchmarks/MANIFEST.json \\
        --dictionary dict.bin --inputs a.txt b.txt c.txt

Exit 0 when the audit is clean, 2 when it refuses. A refusal is the useful outcome: it is what
stops a contaminated dictionary from being shipped quietly.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys

#: A window this long is a copy, not a coincidence — see the module docstring.
LEAK_WINDOW = 24

#: The only split a learned structure may be induced from.
ALLOWED_SPLIT = "train"


class LineageError(ValueError):
    """The dictionary's inputs, or its contents, are not allowed."""


def load_manifest(path: pathlib.Path) -> dict:
    doc = json.loads(path.read_text(encoding="utf-8"))
    if "files" not in doc:
        raise LineageError(f"{path} has no 'files' list — not a corpus manifest")
    return doc


def _split_of(manifest: dict, sample: str) -> str | None:
    """The manifest's split for a sample path, by path or by basename."""
    target = pathlib.PurePath(sample)
    for entry in manifest["files"]:
        path = pathlib.PurePath(entry["path"])
        if path == target or path.name == target.name:
            return entry.get("split")
    return None


def check_build_inputs(manifest: dict, samples: list[str]) -> dict:
    """Refuse any build whose inputs are not entirely from the training split.

    An unknown sample is a refusal too, not a pass: a file the manifest cannot place could be
    anything, and "we could not tell" is not "it was fine".
    """
    if not samples:
        raise LineageError("no build inputs given — a dictionary with no recorded inputs cannot be audited")

    per_split: dict[str, list[str]] = {}
    unknown: list[str] = []
    for sample in samples:
        split = _split_of(manifest, sample)
        if split is None:
            unknown.append(sample)
        else:
            per_split.setdefault(split, []).append(sample)

    offending = {split: names for split, names in per_split.items() if split != ALLOWED_SPLIT}
    if offending or unknown:
        parts = []
        if offending:
            parts.append(
                "built from splits other than "
                f"{ALLOWED_SPLIT!r}: "
                + "; ".join(f"{split}: {sorted(names)}" for split, names in sorted(offending.items()))
            )
        if unknown:
            parts.append(f"inputs the manifest cannot place: {sorted(unknown)}")
        raise LineageError("dictionary lineage refused — " + " | ".join(parts))

    return {
        "inputs": len(samples),
        "splits": {split: len(names) for split, names in sorted(per_split.items())},
        "input_sha256": {
            name: hashlib.sha256(pathlib.Path(name).read_bytes()).hexdigest()
            for name in sorted(samples)
            if pathlib.Path(name).is_file()
        },
    }


def leak_probe(dictionary: bytes, heldout_texts: dict[str, str], *, window: int = LEAK_WINDOW) -> list[dict]:
    """Held-out runs that appear verbatim in the dictionary.

    Returned rather than raised, so the caller can report *how much* leaked and from which
    document — a refusal that says "contaminated" without saying where is not actionable.
    """
    hits: list[dict] = []
    for name, text in heldout_texts.items():
        data = text.encode("utf-8")
        seen: set[bytes] = set()
        for start in range(0, max(0, len(data) - window + 1)):
            chunk = data[start:start + window]
            if chunk in seen:
                continue
            seen.add(chunk)
            if chunk in dictionary:
                hits.append({
                    "document": name,
                    "offset": start,
                    "sample": chunk.decode("utf-8", errors="replace"),
                })
    return hits


def heldout_texts(manifest: dict, corpus_root: pathlib.Path | None = None) -> dict[str, str]:
    """The held-out documents' text, read from the corpus root the manifest names."""
    root = pathlib.Path(corpus_root) if corpus_root else pathlib.Path(manifest.get("root", "."))
    out: dict[str, str] = {}
    for entry in manifest["files"]:
        if entry.get("split") != "heldout":
            continue
        path = root / entry["path"]
        if path.is_file():
            out[str(path)] = path.read_text(encoding="utf-8", errors="replace")
    return out


def audit(manifest: dict, dictionary: bytes, samples: list[str],
          heldout: dict[str, str] | None = None) -> dict:
    """Both halves: the inputs were train-only, and no held-out run survives in the bytes."""
    record = check_build_inputs(manifest, samples)
    hits = leak_probe(dictionary, heldout) if heldout else []
    report = {
        "requirement": "REQ-EXP-002",
        "manifest_sha256": manifest.get("manifest_sha256"),
        "allowed_split": ALLOWED_SPLIT,
        **record,
        "dictionary_bytes": len(dictionary),
        "dictionary_sha256": hashlib.sha256(dictionary).hexdigest(),
        "heldout_documents_probed": len(heldout or {}),
        "leak_window_bytes": LEAK_WINDOW,
        "leaks": hits[:20],
        "leak_count": len(hits),
        "verdict": "PASS" if not hits else "FAIL",
    }
    if hits:
        raise LineageError(
            f"{len(hits)} held-out run(s) of {LEAK_WINDOW}+ bytes appear in the dictionary "
            f"(first: {hits[0]['document']} at offset {hits[0]['offset']}, "
            f"{hits[0]['sample']!r}) — the dictionary carries held-out text"
        )
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--manifest", required=True, type=pathlib.Path)
    ap.add_argument("--dictionary", required=True, type=pathlib.Path)
    ap.add_argument("--inputs", nargs="+", required=True, help="the samples the dictionary was built from")
    ap.add_argument("--corpus-root", type=pathlib.Path, default=None)
    ap.add_argument("--out", type=pathlib.Path, default=None)
    args = ap.parse_args(argv)

    manifest = load_manifest(args.manifest)
    try:
        report = audit(manifest, args.dictionary.read_bytes(), args.inputs,
                       heldout_texts(manifest, args.corpus_root))
    except LineageError as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2
    text = json.dumps(report, indent=2)
    if args.out:
        args.out.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
