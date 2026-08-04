#!/usr/bin/env python3
"""One-off: rename user-facing "SaveCheck" -> "Real365".

Run from the repo root:

    python scripts/_rename_to_real365.py          # apply
    python scripts/_rename_to_real365.py --dry    # preview only

WHAT IS RENAMED (user-visible only):
  * docs/index.html      — <title>, og:*, apple title, logo alt, brand
                           markup, and every "SaveCheck" inside the 12
                           i18n dictionaries across 11 languages.
  * docs/manifest.webmanifest — name, short_name.
  * docs/sw.js           — header comment; CACHE_VERSION bumped so the
                           renamed shell actually reaches installed PWAs
                           (shell is cache-first, so without a bump users
                           keep the old branding for an extra visit or two).
  * docs/og.svg          — social card text, if present.
  * README.md            — prose, with repo URLs / clone paths protected.

WHAT IS DELIBERATELY LEFT ALONE:
  * window.SAVECHECK_PRODUCTS / _HISTORY / _BROCHURES / _DEMO  (all caps)
  * src/savecheck/  Python package and its 57 tests   (all lower)
  * savecheck-<ver> service worker cache prefix       (all lower)
  * savecheck_lang localStorage key                   (all lower)
  * docs/products.js, data.js, brochures.js filenames

  Matching is case-sensitive on the exact token "SaveCheck", so the
  all-caps and all-lower forms above are never touched by accident.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DRY = "--dry" in sys.argv

OLD = "SaveCheck"
NEW = "Real365"

# Brand lockup is split by markup, so a plain token replace misses it.
# Design reference: "Real" in the base ink, "365" in the accent colour —
# same structure the old "Save"+"Check" lockup used.
BRAND_OLD = "Save<b>Check</b>"
BRAND_NEW = "Real<b>365</b>"

# README references that must keep saying SaveCheck: the GitHub repo is
# not being renamed, so clone URLs, `cd` targets and the directory tree
# would all break. Swap them out for sentinels, run the rename, swap back.
README_PROTECTED = [
    "github.com/Tems-git/SaveCheck.git",
    "github.com/Tems-git/SaveCheck",
    "cd SaveCheck",
    "SaveCheck/",
]

report: list[str] = []


def patch(rel: str, fn) -> None:
    """Apply `fn` to a file's text, reporting the delta."""
    path = ROOT / rel
    if not path.exists():
        report.append(f"  SKIP  {rel:<32} (not found)")
        return

    before = path.read_text(encoding="utf-8")
    after = fn(before)

    if before == after:
        report.append(f"  --    {rel:<32} (no change)")
        return

    hits = before.count(OLD) - after.count(OLD)
    if not DRY:
        path.write_text(after, encoding="utf-8")
    report.append(f"  OK    {rel:<32} ({hits} brand mention(s) rewritten)")


def rename_index(text: str) -> str:
    text = text.replace(BRAND_OLD, BRAND_NEW)
    return text.replace(OLD, NEW)


def rename_plain(text: str) -> str:
    return text.replace(OLD, NEW)


def rename_sw(text: str) -> str:
    text = text.replace(OLD, NEW)
    # Bump so the rebranded shell reaches installed clients now rather
    # than whenever their cache-first copy happens to expire.
    return text.replace(
        "const CACHE_VERSION = 'v1';",
        "const CACHE_VERSION = 'v2';",
    )


def rename_readme(text: str) -> str:
    for i, frag in enumerate(README_PROTECTED):
        text = text.replace(frag, f"\x00KEEP{i}\x00")
    text = text.replace(OLD, NEW)
    for i, frag in enumerate(README_PROTECTED):
        text = text.replace(f"\x00KEEP{i}\x00", frag)
    return text


def main() -> None:
    print(f"Rename {OLD!r} -> {NEW!r}{'  (DRY RUN)' if DRY else ''}\n")

    patch("docs/index.html", rename_index)
    patch("docs/manifest.webmanifest", rename_plain)
    patch("docs/sw.js", rename_sw)
    patch("docs/og.svg", rename_plain)
    patch("README.md", rename_readme)

    print("\n".join(report))

    # Guard: the internal identifiers must survive untouched. If any of
    # these went missing the replace was broader than intended and the
    # Python generators would stop lining up with the frontend.
    idx = (ROOT / "docs" / "index.html").read_text(encoding="utf-8")
    guards = {
        "window.SAVECHECK_PRODUCTS": "SAVECHECK_PRODUCTS",
        "savecheck_lang localStorage key": "savecheck_lang",
    }
    print()
    for label, needle in guards.items():
        status = "intact" if needle in idx else "MISSING — investigate"
        print(f"  guard: {label:<38} {status}")

    leftover = idx.count(OLD)
    print(f"\n  remaining {OLD!r} in index.html: {leftover}")

    if DRY:
        print("\nDry run — nothing written. Re-run without --dry to apply.")
    else:
        print("\nDone. Review with:  git diff --stat  then  git diff docs/manifest.webmanifest")


if __name__ == "__main__":
    main()
