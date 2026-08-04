#!/usr/bin/env python3
"""Redesign stage 5: coloured chain marks in the filter row.

Run from the repo root:

    python scripts/_redesign_5_chain_marks.py --dry
    python scripts/_redesign_5_chain_marks.py

WHY ONLY THE FILTER ROW
    The design puts a coloured square beside every mention of a chain.
    Transplanting that wholesale would collide with this app's verdict
    palette — Kaufland and Billa are red brands, Fantastico is amber,
    and here red already means "fake promotion".

    Of the three places a mark could go:
      * product rows      — the verdict dot already occupies that slot
      * brochure headers  — green/red count pills sit beside the name
      * chain filter row  — no semantic colour anywhere on it

    Only the third is safe, and it is also where the marks earn the most:
    picking your chain is a scanning task.

WHAT IT TOUCHES
    docs/index.html — one CSS rule, one colour map + helper, one call
                      site inside the chip renderer.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "docs" / "index.html"
DRY = "--dry" in sys.argv

# ── 1. the mark itself ───────────────────────────────────────────────
CSS_ANCHOR = "  .fchip .fc-n { font-weight:800; opacity:.65; }"
CSS_NEW = """  .fchip .fc-n { font-weight:800; opacity:.65; }
  /* Chain identity square. Only ever rendered in the filter row, where
     no colour carries verdict meaning — see chainMark() below. */
  .chain-mark {
    width:16px; height:16px; border-radius:5px; flex:none;
    display:inline-flex; align-items:center; justify-content:center;
    font-size:9.5px; font-weight:800; color:#fff; line-height:1;
  }"""

# ── 2. colour map + helper, parked next to the verdict map ───────────
C_ANCHOR = "const C = { red:'#D4342B', green:'#0E7A43', yellow:'#C98A08', gray:'#6B7F72' };"
C_NEW = """const C = { red:'#D4342B', green:'#0E7A43', yellow:'#C98A08', gray:'#6B7F72' };

// Chain brand colours. Deliberately NOT reused anywhere a verdict colour
// is on screen: Kaufland and Billa are red brands and Fantastico is
// amber, which would read as "fake" and "weak" respectively. Confined to
// the filter row, which carries no semantic colour of its own.
const CHAIN_MARK = {
  'Lidl':       '#0050AA',
  'Kaufland':   '#E10915',
  'Billa':      '#D6122A',
  'Fantastico': '#E8A400',
  'T Market':   '#00843D',
};

// Unknown chains render nothing rather than a grey box — the locale
// chain lists are not guaranteed to match this map as markets are added.
function chainMark(c) {
  const bg = CHAIN_MARK[c];
  if (!bg) return '';
  // aria-hidden: the chain name follows as text, so announcing the
  // initial as well just doubles it up for screen reader users.
  return `<span class="chain-mark" style="background:${bg}" aria-hidden="true">${c[0]}</span>`;
}"""

# ── 3. call site ─────────────────────────────────────────────────────
CHIP_ANCHOR = (
    "      return `<button class=\"fchip ${on ? 'active' : ''}\" "
    "style=\"${on ? 'background:var(--green);border-color:transparent;color:#fff' : ''}\" "
    "onclick=\"setChainFilter('${c}')\">${c}</button>`;"
)
CHIP_NEW = (
    "      return `<button class=\"fchip ${on ? 'active' : ''}\" "
    "style=\"${on ? 'background:var(--green);border-color:transparent;color:#fff' : ''}\" "
    "onclick=\"setChainFilter('${c}')\">${chainMark(c)}${c}</button>`;"
)


def main() -> None:
    if not INDEX.exists():
        raise SystemExit(f"ABORT: {INDEX} not found — run from the repo root.")

    text = INDEX.read_text(encoding="utf-8")
    print("Redesign stage 5 — chain marks" + ("  (DRY RUN)" if DRY else ""))
    print()

    for label, old, new in (
        (".chain-mark CSS", CSS_ANCHOR, CSS_NEW),
        ("CHAIN_MARK map + chainMark()", C_ANCHOR, C_NEW),
        ("chip render call site", CHIP_ANCHOR, CHIP_NEW),
    ):
        n = text.count(old)
        if n == 1:
            text = text.replace(old, new)
            print(f"  OK    {label}")
        elif n == 0 and ("chain-mark" in text or "chainMark" in text):
            print(f"  --    {label} (already applied)")
        else:
            raise SystemExit(
                f"\nABORT: anchor for {label!r} matched {n} times (expected 1).\n"
                "       Nothing written. docs/index.html has drifted."
            )

    if DRY:
        print("\nDry run — nothing written.")
        return

    INDEX.write_text(text, encoding="utf-8")
    print("\nDone.  Review:  git diff docs/index.html")


if __name__ == "__main__":
    main()
