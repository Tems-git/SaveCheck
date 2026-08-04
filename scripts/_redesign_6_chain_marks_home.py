#!/usr/bin/env python3
"""Redesign stage 6: chain marks on the Home filter row.

Run from the repo root:

    python scripts/_redesign_6_chain_marks_home.py --dry
    python scripts/_redesign_6_chain_marks_home.py

BACKGROUND
    Stage 5 added chainMark() and its CSS, then wired it into the chain
    filter that renders into #chain-wrap. That turned out to be the
    dormant Products view — hidden in the UI, code intact, per the
    README's known-limitations list. So the helper landed correctly but
    was called from somewhere nothing reaches.

    The Home tab builds its own chips inline inside renderHome(), with
    no class and styles written directly onto each button. That is the
    row on screen, and this patches it.

    Stage 5's call site is deliberately left alone. It is inert, and it
    becomes correct the day the Products view comes back.

ALSO FIXED HERE
    color:var(--fg) -> color:var(--ink). There is no --fg token in this
    file, so inactive chips have been falling back to an inherited
    colour. It is inside the string being rewritten anyway.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "docs" / "index.html"
DRY = "--dry" in sys.argv

# The whole button template, from the style attribute through the label.
# Long on purpose: it makes the anchor unambiguous and lets one edit do
# the flex layout, the --fg fix and the mark insertion together.
OLD = (
    "style=\"flex-shrink:0;padding:6px 12px;"
    "border:1px solid ${homeChain===c?'var(--green)':'var(--line)'};"
    "background:${homeChain===c?'var(--green)':'var(--card)'};"
    "color:${homeChain===c?'#fff':'var(--fg)'};"
    "border-radius:999px;font-size:12px;font-weight:700;cursor:pointer\">"
    "${c || FILTER_ALL[country.lang]}</button>"
)

NEW = (
    "style=\"flex-shrink:0;display:inline-flex;align-items:center;gap:5px;padding:6px 12px;"
    "border:1px solid ${homeChain===c?'var(--green)':'var(--line)'};"
    "background:${homeChain===c?'var(--green)':'var(--card)'};"
    "color:${homeChain===c?'#fff':'var(--ink)'};"
    "border-radius:999px;font-size:12px;font-weight:700;cursor:pointer\">"
    "${chainMark(c)}${c || FILTER_ALL[country.lang]}</button>"
)


def main() -> None:
    if not INDEX.exists():
        raise SystemExit(f"ABORT: {INDEX} not found — run from the repo root.")

    text = INDEX.read_text(encoding="utf-8")
    print("Redesign stage 6 — chain marks on the Home row"
          + ("  (DRY RUN)" if DRY else ""))
    print()

    # chainMark() ships in stage 5; without it this patch renders nothing.
    if "function chainMark(" not in text:
        raise SystemExit(
            "ABORT: chainMark() is missing.\n"
            "       Run scripts/_redesign_5_chain_marks.py first."
        )
    print("  guard: chainMark() present")

    if NEW in text:
        print("  --    Home chip template (already applied)")
        print("\nNothing to do.")
        return

    n = text.count(OLD)
    if n != 1:
        raise SystemExit(
            f"\nABORT: chip template anchor matched {n} times (expected 1).\n"
            "       Nothing written."
        )

    text = text.replace(OLD, NEW)
    print("  OK    Home chip template")
    print("        · inline-flex + gap so the mark sits beside the label")
    print("        · var(--fg) -> var(--ink)  (--fg is not a token here)")
    print("        · ${chainMark(c)} before the label")

    if DRY:
        print("\nDry run — nothing written.")
        return

    INDEX.write_text(text, encoding="utf-8")
    print("\nDone.  Review:  git diff docs/index.html")


if __name__ == "__main__":
    main()
