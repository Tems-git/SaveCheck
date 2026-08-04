#!/usr/bin/env python3
"""Redesign stage 3: cap font weights, fix amber contrast.

Run from the repo root:

    python scripts/_redesign_3_weights.py --dry
    python scripts/_redesign_3_weights.py

WHY
    Golos Text is a much inkier face than the Segoe UI it replaced. At
    900 on a saturated background the counters close up and headings
    read as smeared — confirmed by overriding only font-weight on the
    affected headings, which sharpened them while the family stayed put.
    800 keeps the emphasis without the fill-in.

    The .fake-hook amber is a separate but compounding problem: white on
    its light end sat near 3:1, under the 4.5:1 its 11.5px sub-line
    needs. Low contrast reads as blur, so this is part of the same
    complaint.

SAFETY
    The replacement targets "font-weight:900" with no space after the
    colon. The @font-face variable range is written "font-weight: 400
    900" with a space, so it is not matched — which matters, because
    rewriting it would collapse the variable axis and bring back the
    synthetic bolding this whole exercise was about.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "docs" / "index.html"
DRY = "--dry" in sys.argv

# Literal, space-free forms. See the safety note above.
WEIGHT_MAP = {
    "font-weight:900": "font-weight:800",
    "font-weight:750": "font-weight:700",
}

# White on #C98A08 is ~3.0:1; on #9C6B06 it is ~4.6:1, and the dark end
# reaches ~7.6:1. Shadow tint follows the new base colour.
AMBER_OLD = (
    ".fake-hook { display:flex; align-items:center; gap:12px; "
    "background:linear-gradient(135deg,#C98A08,#9A6A04); color:#fff; border-radius:18px; "
    "padding:14px 16px; margin-top:10px; cursor:pointer; "
    "box-shadow:0 14px 28px -12px rgba(154,106,4,.55); }"
)
AMBER_NEW = (
    ".fake-hook { display:flex; align-items:center; gap:12px; "
    "background:linear-gradient(135deg,#9C6B06,#6F4B03); color:#fff; border-radius:18px; "
    "padding:14px 16px; margin-top:10px; cursor:pointer; "
    "box-shadow:0 14px 28px -12px rgba(111,75,3,.55); }"
)

# The sub-line rides at .92 opacity, which drags an already tight ratio
# back under the line. Full opacity, slightly muted via the colour only.
SUB_OLD = "  .fake-hook .fh-sub { font-size:11.5px; opacity:.92; margin-top:1px; }"
SUB_NEW = "  .fake-hook .fh-sub { font-size:11.5px; opacity:1; color:rgba(255,255,255,.94); margin-top:1px; }"


def main() -> None:
    if not INDEX.exists():
        raise SystemExit(f"ABORT: {INDEX} not found — run from the repo root.")

    text = INDEX.read_text(encoding="utf-8")
    print("Redesign stage 3 — weights + amber contrast" + ("  (DRY RUN)" if DRY else ""))
    print()

    # Guard: the variable-range declarations must be present and stay that way.
    ranges_before = text.count("font-weight: 400 900")
    if ranges_before == 0:
        raise SystemExit(
            "ABORT: no 'font-weight: 400 900' found in @font-face.\n"
            "       Stage 1 either did not run or the font block was edited."
        )

    for old, new in WEIGHT_MAP.items():
        n = text.count(old)
        text = text.replace(old, new)
        print(f"  {old}  ->  {new}   ({n} occurrence(s))")

    for label, old, new in (
        ("fake-hook gradient (contrast)", AMBER_OLD, AMBER_NEW),
        ("fake-hook sub-line opacity", SUB_OLD, SUB_NEW),
    ):
        n = text.count(old)
        if n == 1:
            text = text.replace(old, new)
            print(f"  OK    {label}")
        elif new[:40] in text:
            print(f"  --    {label} (already applied)")
        else:
            raise SystemExit(
                f"\nABORT: anchor for {label!r} matched {n} times (expected 1).\n"
                "       Nothing written."
            )

    ranges_after = text.count("font-weight: 400 900")
    print(f"\n  guard: @font-face variable ranges  {ranges_before} -> {ranges_after}", end="")
    if ranges_after != ranges_before:
        raise SystemExit("\nABORT: variable range declarations were altered. Nothing written.")
    print("  intact")

    if DRY:
        print("\nDry run — nothing written.")
        return

    INDEX.write_text(text, encoding="utf-8")
    print("\nDone.  Review:  git diff docs/index.html")


if __name__ == "__main__":
    main()
