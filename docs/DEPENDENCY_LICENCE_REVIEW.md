# Dependency licence review — GUI extra (PySide6/Qt) under PolyForm Noncommercial

> **Status:** Review for owner decision (Session 44, 2026-10-29). **Not a decision record and not legal advice.** It gathers what the licences require, what this project's distribution shape means for them, and the options — the choice belongs in an ADR (to be recorded as ADR-0011) once the owner picks.
> **Raised by:** [ADR-0009](ADR/ADR-0009-license-polyform-noncommercial.md) Consequences §3, which flagged the PySide6 combination as an open review item rather than closing it silently.
> **Related:** [ADR-0006](ADR/ADR-0006-license-mit.md) (superseded) · [ADR-0008](ADR/ADR-0008-gui-toolkit-architecture.md) (toolkit decision) · [ADR-0009](ADR/ADR-0009-license-polyform-noncommercial.md) (project licence) · `LICENSE` · `pyproject.toml` · [RELEASE_PROCESS.md](RELEASE_PROCESS.md) R3

## Why this document exists

The project licence changed to PolyForm Noncommercial 1.0.0 (ADR-0009). Every dependency that was comfortable under MIT needs re-reading under a source-available, noncommercial licence — not because PolyForm is unusual, but because the questions change: MIT asked almost nothing of us, whereas distribution under any licence still has to satisfy each dependency's own terms. The GUI is the one dependency with real obligations attached.

## Inventory

| Dependency | Licence | Where it ships | Obligation weight |
|---|---|---|---|
| CPython | PSF-2.0 | runtime | notice only |
| `zstandard` | BSD-3-Clause | core, always | attribution in notices |
| `pytest` | MIT | dev only, never shipped | none at distribution |
| **PySide6 / Qt 6** | **LGPL-3.0** (Qt for Python open-source build) | `[gui]` extra only | **the subject of this review** |
| PyMuPDF (planned PDF/OCR) | **AGPL-3.0** | not a dependency | flagged, see §5 |

The core install (`pip install lexora`) stays Qt-free by design (ADR-0008 decision 1), so **the LGPL question only arises for the optional GUI extra**. That is the single most useful fact in this document: it bounds the exposure.

## 1. What LGPL-3.0 actually asks of us

As we read LGPL-3.0 §4 (Combined Works), conveying a work that links the library requires:

1. **Prominent notice** with each copy that the library is used and is covered by the LGPL.
2. **Copies of both the GPL-3.0 and LGPL-3.0 texts** accompanying the distribution.
3. If the work **displays copyright notices during execution**, the library's copyright notice included among them, with a pointer to those licence texts.
4. A mechanism preserving the user's ability to **relink or replace** the library with a modified version — satisfied in practice by **dynamic linking against shared libraries** (§4(d)(1)), which is how the PySide6 wheels ship.
5. **Installation information** ("anti-tivoization") only where GPL §6 would require it — for a normal desktop install this does not bite.

Two things LGPL-3.0 does **not** require: it does not force our own code to be LGPL, and it does not require publishing our source. Relinkability is the crux, and shared libraries satisfy it.

## 2. Does PolyForm Noncommercial conflict with those obligations?

Our reading: **no direct conflict, but two conditions worth writing down.**

- LGPL-3.0 requires that the terms of the combined work "effectively do not restrict modification of the portions of the Library ... and reverse engineering for debugging". PolyForm grants modification and new works, and restricts **commercial use**, not modification. A noncommercial field-of-use restriction is not the same as a restriction on modifying the library or debugging it.
- LGPL notices must travel with the distribution; PolyForm's *Notices* section requires passing on **its own** terms and `Required Notice:` line. These are additive, not contradictory — ship both sets.

The place this could get uncomfortable is **enforcement posture**, not doctrine: a noncommercial licence plus LGPL parts means recipients have to reason about two permission systems at once. That is a communication cost (see the checklist in §4), not a licence incompatibility.

## 3. The question nobody asks: which Qt modules do the wheels actually pull in?

PySide6's own licence is one half of the story. The wheels bundle **individual Qt modules, and they are not all LGPL**. Qt 6 ships some modules under **GPL-3.0 only** (or commercial) — charting and a few add-ons are the usual offenders. Importing one of those into a PolyForm application would put a GPL-3.0-only component into the combined work, and that is a real problem rather than a notice-and-paperwork one.

So the audit has two halves, and the second is the one that can actually bite:

```bash
# what the GUI actually imports
rg -n "^\s*(from|import)\s+PySide6" src/lexora/gui/
# which Qt modules those imports resolve to, and each module's licence
# (PySide6 ships the Qt licence texts under PySide6/Qt/lib and in the wheel metadata)
```

Today the GUI imports from exactly three modules — `PySide6.QtCore`, `PySide6.QtGui`, `PySide6.QtWidgets`, all LGPL-3.0 in Qt 6 — and nothing else:

```
$ grep -rhoE "PySide6\.[A-Za-z]+" src/lexora/gui/ | sort -u
PySide6.QtCore
PySide6.QtGui
PySide6.QtWidgets
```

The imports are lazy and confined to `app.py` (lines 25, 139, 148, 344, 359, 443) — `service.py` and `crash.py` stay Qt-free by design, which is also what keeps the core install Qt-free. **This was read from the import lines in this repository, not from an installed wheel**: PySide6 is not installed in the review environment (the GUI tests skip there), so the module-to-licence mapping is asserted from Qt's own published licensing and should be re-confirmed against the wheel at packaging time. Treat it as the first item on the checklist, not as a settled fact.

## 4. What shipping would require (checklist for whichever option is chosen)

1. A `NOTICE` file naming every third-party component, its version and its licence — PySide6, Qt modules actually used, `zstandard`, CPython.
2. Copies of **LGPL-3.0** and **GPL-3.0** texts alongside `LICENSE` in the distribution (wheel data files and the GUI packaging recipe both).
3. The LGPL notice reachable **from the running application** — the About view (`format_about_text`) is the natural home, and it already lists version and paths.
4. A documented **relinking route**: state that PySide6/Qt are dynamically linked shared libraries and that a user may replace them; keep them as separate files in any packaged build (no static linking, no bundling that prevents substitution).
5. `LICENSE` (PolyForm, with its `Required Notice:` line) still travels with every artifact — RELEASE_PROCESS R3, unchanged by any of this.
6. Re-verify the Qt module licence list against the actual wheel each time PySide6's version moves.

## 5. PyMuPDF (AGPL-3.0) — unchanged, still not a dependency

ADR-0006 flagged it and ADR-0009 carried the flag forward. AGPL-3.0 requires the source of the whole combined work for anything conveyed or offered over a network; PolyForm Noncommercial cannot satisfy that, and neither could MIT. It remains **not a declared dependency**. Using it locally for private research is a different question from distributing it, but adopting it for the PDF/OCR path would need its own ADR and, realistically, a commercial licence from Artifex.

## 6. Options for the owner

- **A. Keep PySide6 as an optional extra, comply, document.** Dynamic linking (already the case), `NOTICE` + licence texts + About-view notice + relinking statement. Standard practice; keeps the GUI free to distribute for noncommercial use. **Recommended if the GUI is meant to ship to anyone.**
- **B. Process separation.** Run the GUI as a separate process talking to the core, which strengthens the relinking argument further. More engineering for a marginal licence benefit over A; worth it only if packaging gets unusual.
- **C. Drop the `[gui]` extra from distribution.** Core stays Qt-free and ships under PolyForm alone; the GUI remains a source-level tool users build themselves. Zero LGPL obligations in what we hand out, at the cost of the GUI not being a shipped artifact.
- **D. Commercial Qt licence.** Removes LGPL obligations entirely and is the only option compatible with static linking or GPL-only Qt modules. A cost decision, not an engineering one.

## 7. What is needed to close this

1. Owner picks A, B, C or D → recorded as **ADR-0011** (ADR-0010 was taken by the `.lxdb` direction in Session 52), which then either closes the ADR-0009 flag or states precisely what remains.
2. Whichever is chosen, the §4 checklist becomes part of the release gate (R3 grows a licence-notices row).
3. If the GUI is ever distributed commercially by anyone, get a lawyer's read. This document records engineering judgement about licence mechanics; it is not a legal opinion, and the owner remains accountable for data and licence decisions as CORPUS_POLICY already says for data.
