# LEXORA Installation Guide

> **Status:** Draft (nothing is installable yet — no package exists, verified 2026-10-15)
> **Owner:** Documentation architect (delegated)
> **Related:** [BUILD_GUIDE.md](BUILD_GUIDE.md) · [DEVELOPMENT_SETUP.md](DEVELOPMENT_SETUP.md) · DECISIONS OQ-5/OQ-7/OQ-10

## Purpose & scope

End-user installation paths once P1 ships. This document deliberately contains **no working install command today** because none exists; fabricating one would violate master-prompt §1.2.

## Prerequisites (planned)

| Item | Requirement | Status |
|---|---|---|
| OS | Linux or Windows x86-64 | Proposed (REF-4G profile) |
| RAM | ~4 GiB target machine | Design constraint |
| Python | Version range = **OQ-7, undecided** | Blocked decision |
| Core dependency | `zstandard` (pinned) | Planned |
| Optional OCR | Tesseract + hi/gu traineddata | OQ-10 |

## Planned methods (PROPOSED — do not run as if real)

```text
# Method 1 (once published): pip install lexora            # NOT AVAILABLE — no package published
# Method 2: from source checkout                          # see BUILD_GUIDE "Planned build"
# Method 3: offline wheelhouse                            # wheels/ directory prepared per BUILD_GUIDE
```

## Verification after install (planned)

```text
lxz --version        # PROPOSED CLI name; actual entry point fixed at P1-T5
lxz selftest         # PROPOSED: runs round-trip invariant on bundled tiny fixtures
```

If these commands ever ship, this section gets replaced with observed output + date + commit.

## Known limitations today

- No license selected (OQ-5) ⇒ redistribution terms undefined.
- No repository remote (OQ-6) ⇒ no official clone URL to publish.
- Nothing to install; the repo is a documentation system in progress.

## Uninstall / cleanup

Not applicable until an installer exists. When packaging lands, uninstall guidance must state exactly what global state (if any) is touched — design intent: none beyond the venv/site-packages and user config dir.
