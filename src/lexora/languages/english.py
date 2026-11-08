"""English — the reference language plugin (ADR-0022).

This is a thin declaration over `lexora.canonicalize`, which already holds the rules
(CAN-R01 decode, CAN-R02 newlines, CAN-R05 NFC). The point is not to move the code but
to make English *one implementation behind an interface* instead of the only possible
behaviour, so a second language can arrive without editing the canonicaliser.

Two deliberate choices:

* **The cleaning rules are delegated, not copied.** Duplicating them here would create
  two sources of truth and the plugin would drift from the tests that pin them.
* **Provenance stays `lexcan-0.1`.** The seam's natural label would be `en-1`, but
  renaming the header field would rewrite every archive's bytes a second time in one
  week (ADR-0020 did it yesterday) for no reader benefit. New languages start at
  `hi-1`, `zh-1`; English keeps its historical label until v1, when the label can
  change once, with the format.
"""

from __future__ import annotations

from lexora import CANONICALIZER_VERSION
from lexora.canonicalize import canonicalize, canonicalize_with_meta
from lexora.langapi import LanguagePlugin

PLUGIN = LanguagePlugin(
    id="en",
    version=1,
    name="English",
    # Space-separated script: unicode61 is right, and it is what the existing catalogs
    # were built with, so this choice keeps them readable.
    tokenizer="unicode61",
    canonicalize=canonicalize,
    canonicalize_with_meta=canonicalize_with_meta,
    ocr_languages=("eng",),
    # The label every existing archive already carries. See the module docstring.
    provenance_label=CANONICALIZER_VERSION,
)
