#!/usr/bin/env python3
"""One-off: surface "how it works" as a header button.

    python scripts/_info_button.py --dry
    python scripts/_info_button.py

WHY
    The info modal had a single entry point — a link in the footer. The
    mobile layout fix moved the footer inside .scroll, so on a phone it
    now sits underneath a list that can run to fifty items. Everything
    that explains what the app is measuring lives behind that link: the
    Omnibus methodology, the verdict definitions, and the coverage
    disclaimer added after a user found watermelon missing.

WHAT IT ADDS
    A round button next to the language chip, calling the same
    showInfo() the footer already calls. The footer link stays — two
    routes to one modal costs nothing, and on desktop the footer is
    where people look.

NO NEW STRINGS
    HEADER_I18N.howItWorks already holds the translated label in all
    eleven locales for the footer link, so the aria-label reuses it. It
    is re-applied on language change alongside the other chrome labels
    rather than being left frozen in Bulgarian.

SIZE
    40x40, not the 34px of the neighbouring language chip. This is a new
    control and the review flagged touch targets; the existing
    undersized ones are a documented compromise, but adding another
    would not be.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "docs" / "index.html"
DRY = "--dry" in sys.argv

# ── 1. styling, on the dark header ───────────────────────────────────
CSS_ANCHOR = (
    ".theme-btn { border:0; background:none; cursor:pointer; "
    "color:rgba(255,255,255,.78); padding:4px; line-height:1; border-radius:8px; "
    "transition:color .15s; flex:none; }"
)
CSS_NEW = CSS_ANCHOR + """
  /* Sits on the deep-green appbar beside the language chip. Same
     translucent-white treatment as .cp-trigger so the two read as one
     group, but a full 40px target rather than the chip's ~34. */
  .info-btn {
    flex:none; width:40px; height:40px; margin-left:8px; padding:0;
    display:flex; align-items:center; justify-content:center;
    border:0; border-radius:999px; cursor:pointer;
    background:rgba(255,255,255,.14); color:#fff;
    font-family:inherit; font-size:16px; font-weight:800; line-height:1;
    transition:background .15s;
  }
  .info-btn:hover { background:rgba(255,255,255,.24); }"""

# ── 2. markup, after the country picker ──────────────────────────────
MARKUP_ANCHOR = """        <div class="cp-menu" id="flags"></div>
      </div>
    </div>
    <div class="appbar-search">"""

MARKUP_NEW = """        <div class="cp-menu" id="flags"></div>
      </div>
      <button class="info-btn" id="info-btn" onclick="showInfo()" aria-label="Как работи?">?</button>
    </div>
    <div class="appbar-search">"""

# ── 3. keep the label in step with the chosen language ───────────────
ARIA_ANCHOR = "    if (infoModal) infoModal.setAttribute('aria-label', X.infoDialog);"
ARIA_NEW = """    if (infoModal) infoModal.setAttribute('aria-label', X.infoDialog);
    // Reuses the footer link's existing translation rather than adding a
    // twelfth key to maintain across eleven locales.
    const infoBtn = document.getElementById('info-btn');
    if (infoBtn) infoBtn.setAttribute('aria-label',
      (HEADER_I18N[country.lang] || HEADER_I18N.bg).howItWorks);"""


def main() -> None:
    if not INDEX.exists():
        raise SystemExit(f"ABORT: {INDEX} not found — run from the repo root.")

    text = INDEX.read_text(encoding="utf-8")
    print("Info button" + ("  (DRY RUN)" if DRY else ""))
    print()

    if 'id="info-btn"' in text and ".info-btn {" in text:
        print("  --  already applied")
        return

    for label, old, new in (
        (".info-btn styles", CSS_ANCHOR, CSS_NEW),
        ("button markup", MARKUP_ANCHOR, MARKUP_NEW),
        ("aria-label sync on language change", ARIA_ANCHOR, ARIA_NEW),
    ):
        n = text.count(old)
        if n == 1:
            text = text.replace(old, new)
            print(f"  OK    {label}")
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
    print("Check: the button opens the modal, and switching language")
    print("updates its aria-label along with the rest of the chrome.")


if __name__ == "__main__":
    main()
