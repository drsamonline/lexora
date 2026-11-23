#!/usr/bin/env python3
"""Draw this repository's badges as local SVGs — the offline fallback set.

The fleet's presentation standard asks for six committed badge files under `docs/assets/`, so a page
that claims to work offline does not load its own self-description from an image service. The
shields.io and GitHub-Actions badges in the README stay: they are **live**, and a committed SVG
cannot carry a CI result. These are the fallback, not a replacement.

**One claim here is deliberately a state rather than a number.** The `tests` badge says `green`,
not `867 passing`, because a static count is exactly what `tests/test_readme_claims.py` forbids in
this repository: a number nothing recomputes decays the moment a test is added, and it decays
silently. The count is the CI badge's job. Every other claim below is a fact that changes only when
someone changes the repository — the licence, the runtime dependency count, the absence of network
calls — and each is asserted by a test in this repo.

    python3 scripts/badges.py            # write docs/assets/badge-*.svg
    python3 scripts/badges.py --check    # exit 1 if any file is missing or stale
"""

from __future__ import annotations

import argparse
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
OUT = REPO / "docs" / "assets"

#: The page's own palette (docs/index.html `:root`), so a badge never introduces a colour the
#: page does not already use.
INK = "#101113"
EDGE = "#2a2d33"
PAPER = "#e9e9ea"
MUTED = "#8b8c93"
GREEN = "#a3e635"
WARN = "#d8a13a"

#: (file stem, left label, right text, right colour)
BADGES = [
    ("live", "live", "online", GREEN),
    ("tests", "tests", "green — see CI", GREEN),
    ("build", "build", "green", GREEN),
    ("licence", "licence", "PolyForm NC 1.0.0", WARN),
    ("offline", "offline", "no network", MUTED),
    ("deps", "deps", "1 runtime", MUTED),
]

CHAR_W = 6.6          # monospace advance at 11 px, rounded up
PAD = 9


def _width(text: str) -> int:
    return int(len(text) * CHAR_W + PAD * 2)


def svg(left: str, right: str, colour: str) -> str:
    lw, rw = _width(left), _width(right)
    total = lw + rw
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{total}" height="20" role="img" \
aria-label="{left}: {right}">
  <title>{left}: {right}</title>
  <rect width="{total}" height="20" rx="3" fill="{INK}" stroke="{EDGE}"/>
  <rect x="{lw}" width="{rw}" height="20" rx="3" fill="{colour}" fill-opacity="0.16"/>
  <g font-family="ui-monospace, 'SF Mono', Menlo, Consolas, monospace" font-size="11" \
text-anchor="middle">
    <text x="{lw / 2:.0f}" y="14" fill="{MUTED}">{left}</text>
    <text x="{lw + rw / 2:.0f}" y="14" fill="{PAPER}">{right}</text>
  </g>
</svg>
"""


def render() -> dict[pathlib.Path, str]:
    return {OUT / f"badge-{stem}.svg": svg(left, right, colour)
            for stem, left, right, colour in BADGES}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="exit 1 if a badge is missing or stale")
    args = ap.parse_args(argv)

    OUT.mkdir(parents=True, exist_ok=True)
    stale = []
    for path, content in render().items():
        current = path.read_text(encoding="utf-8") if path.exists() else None
        if current != content:
            stale.append(path.name)
            if not args.check:
                path.write_text(content, encoding="utf-8")

    if args.check:
        if stale:
            print(f"stale or missing badges: {', '.join(sorted(stale))}")
            print("regenerate: python3 scripts/badges.py")
            return 1
        print(f"ok: {len(render())} badge(s) present and current")
        return 0

    print(f"wrote {len(render())} badge(s) to {OUT.relative_to(REPO)}/"
          + (f" (changed: {', '.join(sorted(stale))})" if stale else " (all current)"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
