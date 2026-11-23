"""Guards for the documents that claim what this project can do.

Three drifts were found on 2026-11-23, and each was the same failure in a different costume:

* ``README.md`` said TXT/PDF ingestion "is not implemented yet" — it had shipped, with tests.
* ``ROADMAP.md`` said M3 was "Not started" and had last been verified **2026-10-15**.
* ``PROGRESS.md`` still had P2 "Not started" and a 502-test gate from **2026-10-17**.

Nothing failed when they went stale, because "this capability is built" was prose, and prose is
not recomputed. ``tests/test_readme_claims.py`` already pins the verb list, the version a user
reads and the absence of a static test count; it cannot tell whether a sentence is true.

These two guards are cheap, and both would have failed on the morning of 2026-11-23:

1. **A cited code path must exist.** A document that points at ``src/…``, ``tests/…``,
   ``packages/…``, ``benchmarks/…`` or ``scripts/…`` is making a checkable claim. A renamed or
   deleted file leaves a citation that reads fine and leads nowhere.
2. **The state documents must agree on when they were last verified.** Four documents carry a
   ``Last verified`` date, and they are supposed to describe one repository. When one of them is
   three weeks behind the others, at least one is lying about the present — which is exactly the
   ROADMAP/STATUS gap above.

Neither guard asserts a *number*, so no normal edit turns them red. They assert agreement.
"""

from __future__ import annotations

import datetime as dt
import pathlib
import re

import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]

# Documents that describe the present state of the repository. SESSION_LOG is deliberately
# absent: it is append-only history, and a path that existed in a past session is still a true
# record of that session after the file is renamed.
STATE_DOCS = [
    "README.md",
    "CONTRIBUTING.md",
    "docs/ROADMAP.md",
    "docs/PATH_TO_V1.md",
    "docs/STATUS.md",
    "docs/PROGRESS.md",
    "docs/NEXT_SESSION.md",
]

# Only paths in the trees the repository owns — a bare filename in prose (`pyproject.toml`) is
# often illustrative, a tree-qualified one is a citation.
CITED_PATH = re.compile(r"`((?:src|tests|packages|benchmarks|scripts)/[A-Za-z0-9_./-]+)`")

LAST_VERIFIED = re.compile(r"Last verified(?: state)?:\*{0,2}\s*\**\s*(\d{4}-\d{2}-\d{2})")

# A fortnight is generous on purpose: the guard is here to catch a document that was forgotten
# for weeks, not to force a rewrite on the day after a session.
MAX_DRIFT_DAYS = 14


def _state_docs() -> list[pathlib.Path]:
    return [REPO / name for name in STATE_DOCS]


def test_every_cited_code_path_exists() -> None:
    """A citation of a file that does not exist is a broken instruction, not a typo."""
    missing: list[str] = []
    for doc in _state_docs():
        text = doc.read_text(encoding="utf-8")
        for cited in sorted(set(CITED_PATH.findall(text))):
            path = cited.rstrip(".,;:)")
            if not (REPO / path).exists():
                missing.append(f"{doc.relative_to(REPO)} cites `{path}`, which does not exist")
    assert not missing, "documents cite files that are not in the repository:\n" + "\n".join(missing)


def test_the_state_documents_agree_on_when_they_were_last_verified() -> None:
    """One repository, one present tense — four documents must not describe four different days."""
    dates: dict[str, dt.date] = {}
    for doc in _state_docs():
        match = LAST_VERIFIED.search(doc.read_text(encoding="utf-8"))
        if match:
            dates[str(doc.relative_to(REPO))] = dt.date.fromisoformat(match.group(1))

    assert len(dates) >= 3, (
        "fewer than three state documents carry a `Last verified` date — either the header "
        f"shape changed or the field was dropped: {sorted(dates)}"
    )

    oldest = min(dates.values())
    newest = max(dates.values())
    spread = (newest - oldest).days
    if spread > MAX_DRIFT_DAYS:
        detail = "\n".join(f"  {name}: {day}" for name, day in sorted(dates.items()))
        pytest.fail(
            f"the state documents disagree about when they were last verified by {spread} days "
            f"(oldest {oldest}, newest {newest}). At least one of them is describing a repository "
            f"that no longer exists:\n{detail}"
        )
