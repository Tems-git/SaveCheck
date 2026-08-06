#!/usr/bin/env python3
"""One-off: stop .appbar clipping and re-stacking the language dropdown.

    python scripts/_fix_appbar_clipping.py --dry
    python scripts/_fix_appbar_clipping.py

THE REGRESSION
    The component restyle gave .appbar a radial accent glow as an
    ::after element. To keep that circle inside the rounded bottom
    corners it needed overflow:hidden, and to keep the brand and search
    field above it, it needed .appbar > * { position:relative; z-index:1 }.

    Both props break the country picker's dropdown.

      overflow:hidden  cuts the menu off at the appbar's bottom edge.

      .appbar > *      seals .brand into its own stacking context at
                       z-index 1. The menu inside it sets z-index:200,
                       but that only competes within .brand — and
                       .appbar-search is a later sibling at the same
                       z-index, so it paints over the menu regardless.

    Visible effect: the dropdown shows a row or two, vanishes behind the
    search field, and reappears below it. Nine locales unreachable.

    It went unnoticed through several checks because changing language
    only needs the first row, which stayed clickable.

THE FIX
    Move the glow into the background of .appbar as a second layer.
    Backgrounds are clipped by border-radius automatically, so neither
    overflow:hidden nor the z-index prop is needed and both are removed.

    Geometry is preserved: the ::after was a 260px circle positioned
    right:-90px top:-120px, so its centre sat 40px inside the right edge
    and 10px below the top, with a 130px radius fading out at 68%.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "docs" / "index.html"
DRY = "--dry" in sys.argv

OLD = """.appbar {
    position:relative; overflow:hidden; flex:none;
    padding:16px 16px 18px; border-bottom:0; border-radius:0 0 28px 28px;
    background:linear-gradient(168deg,var(--deep) 0%,var(--deep-2) 58%,var(--deep-3) 100%);
  }
  .appbar::after {
    content:''; position:absolute; width:260px; height:260px; right:-90px; top:-120px;
    border-radius:50%; pointer-events:none;
    background:radial-gradient(circle, rgba(88,224,146,.30), transparent 68%);
  }
  .appbar > * { position:relative; z-index:1; }"""

NEW = """.appbar {
    position:relative; flex:none;
    padding:16px 16px 18px; border-bottom:0; border-radius:0 0 28px 28px;
    /* The accent glow is a background layer, not an ::after element.
       As a child it needed overflow:hidden to stay inside the rounded
       corners — which clipped the language dropdown — and a z-index on
       its siblings to sit behind them, which sealed .brand into its own
       stacking context and pushed the same dropdown under the search
       field. Backgrounds are clipped by border-radius for free, so both
       props are gone.

       Geometry matches the old circle: 260px wide at right:-90px and
       top:-120px put its centre 40px inside the right edge and 10px
       below the top, radius 130, fading out at 68%. */
    background:
      radial-gradient(circle 130px at calc(100% - 40px) 10px,
                      rgba(88,224,146,.30), transparent 68%),
      linear-gradient(168deg,var(--deep) 0%,var(--deep-2) 58%,var(--deep-3) 100%);
  }"""


def main() -> None:
    if not INDEX.exists():
        raise SystemExit(f"ABORT: {INDEX} not found — run from the repo root.")

    text = INDEX.read_text(encoding="utf-8")
    print("Appbar clipping fix" + ("  (DRY RUN)" if DRY else ""))
    print()

    if ".appbar::after" not in text and "circle 130px at calc(100% - 40px)" in text:
        print("  --  already applied")
        return

    n = text.count(OLD)
    if n != 1:
        raise SystemExit(
            f"\nABORT: anchor matched {n} times (expected 1). Nothing written.\n"
            "       The .appbar block has been edited since the restyle."
        )

    text = text.replace(OLD, NEW)
    print("  OK    .appbar glow moved to a background layer")
    print("        · overflow:hidden removed  (was clipping the dropdown)")
    print("        · .appbar > * z-index removed  (was burying it under search)")
    print("        · .appbar::after removed")

    if DRY:
        print("\nDry run — nothing written.")
        return

    INDEX.write_text(text, encoding="utf-8")
    print("\nDone.  Review:  git diff docs/index.html")
    print("Check: open the language menu — all 11 locales, over the search field.")


if __name__ == "__main__":
    main()
