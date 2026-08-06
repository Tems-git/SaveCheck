#!/usr/bin/env python3
"""One-off: remove the double scroll on mobile.

    python scripts/_mobile_layout.py --dry
    python scripts/_mobile_layout.py

THE DEFECT
    The document is taller than the viewport by construction:

        body padding-top          24px
        .phone                    calc(100dvh - 60px)
        footer margin-top         14px
        footer                    ~50px
        body padding-bottom       36px
        ------------------------------------------
        total                     ~100dvh + 64px

    So a document-level scroll sits underneath the inner .scroll on
    every screen size. On desktop that is invisible — the phone frame is
    meant to be a mockup floating on a backdrop. On an actual phone it
    produces two competing scroll surfaces, and the file contains no
    @media rule to tell the two situations apart.

WHAT THIS DOES
    1. Moves <footer> inside .scroll, so it is part of the inner scroll
       instead of adding height below the frame.
    2. Adds a single @media (max-width: 480px) block that drops the body
       padding and lets .phone fill the screen: no border, no radius, no
       shadow, full height.

    Purely additive. Every base rule is inherited, so the redesign
    carries over unchanged and desktop is untouched.

WHY NOT body { overflow: hidden }
    It removes the outer scroll but strands the footer, which holds the
    only link into the info modal — there is no info control in the
    header. Both the methodology text and the coverage disclaimer would
    become unreachable on phones.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "docs" / "index.html"
DRY = "--dry" in sys.argv

# ── 1. footer joins the inner scroll ─────────────────────────────────
FOOTER_OLD = """    <div id="basket"></div>
  </div>
  <nav class="bottomnav" id="tabs"></nav>
</div>
<footer id="footer"></footer>"""

FOOTER_NEW = """    <div id="basket"></div>
    <footer id="footer"></footer>
  </div>
  <nav class="bottomnav" id="tabs"></nav>
</div>"""

# ── 2. the only @media rule in the file ──────────────────────────────
CSS_ANCHOR = """  select:focus-visible,
  textarea:focus-visible {
    outline: 2px solid var(--green);
    outline-offset: 2px;
    border-radius: 4px;
  }
</style>"""

CSS_NEW = """  select:focus-visible,
  textarea:focus-visible {
    outline: 2px solid var(--green);
    outline-offset: 2px;
    border-radius: 4px;
  }

  /* ── Phones ──────────────────────────────────────────────────────
     Everything above is shared. This block only stops the app from
     drawing a phone inside a phone, and with it removes the document
     scroll that used to sit underneath .scroll: body padding plus a
     frame shorter than the viewport plus a footer below it always
     summed to more than one screen.

     Additive on purpose — no component is restyled here, the base
     rules simply apply to a full-bleed surface instead of a 430px
     mockup. */
  @media (max-width: 480px) {
    body { padding: 0; }
    .phone {
      max-width: none;
      border: 0;
      border-radius: 0;
      box-shadow: none;
      height: 100vh;   /* fallback for browsers without dvh */
      height: 100dvh;  /* excludes the mobile URL bar */
      max-height: none;
    }
    /* The dark theme sets these with a higher specificity, so they need
       restating rather than relying on the rule above. */
    [data-theme="dark"] .phone { border: 0; box-shadow: none; }
    /* Now inside .scroll, so it wants breathing room rather than the
       margin it used when it floated below the frame. */
    footer { max-width: none; margin: 18px 0 4px; }
  }
</style>"""


def main() -> None:
    if not INDEX.exists():
        raise SystemExit(f"ABORT: {INDEX} not found — run from the repo root.")

    text = INDEX.read_text(encoding="utf-8")
    print("Mobile layout fix" + ("  (DRY RUN)" if DRY else ""))
    print()

    if "@media (max-width: 480px)" in text and "<footer id=\"footer\"></footer>\n  </div>" in text:
        print("  --  already applied")
        return

    for label, old, new in (
        ("footer moved into .scroll", FOOTER_OLD, FOOTER_NEW),
        ("@media (max-width: 480px)", CSS_ANCHOR, CSS_NEW),
    ):
        n = text.count(old)
        if n == 1:
            text = text.replace(old, new)
            print(f"  OK    {label}")
        elif n == 0 and new.strip()[:40] in text:
            print(f"  --    {label} (already applied)")
        else:
            raise SystemExit(
                f"\nABORT: anchor for {label!r} matched {n} times (expected 1).\n"
                "       Nothing written."
            )

    if DRY:
        print("\nDry run — nothing written.")
        return

    INDEX.write_text(text, encoding="utf-8")
    print("\nDone.  Review:  git diff docs/index.html")
    print("Check at 375px wide in DevTools device mode: one scroll, not two.")


if __name__ == "__main__":
    main()
