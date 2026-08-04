#!/usr/bin/env python3
"""Redesign stage 4: point the app at the new SVG logo.

Run from the repo root:

    python scripts/_redesign_4_logo.py --dry
    python scripts/_redesign_4_logo.py

WHAT IT TOUCHES
    docs/index.html  — appbar <img src>
    docs/sw.js       — precache entry

ON THE SERVICE WORKER
    SHELL_URLS still lists './img/logos/logo-d.png', but that file was
    replaced by logo-d.webp during the WebP pass. Precaching runs under
    allSettled, so the miss has been silent — the shell has simply been
    caching without its logo. Repointing it to the SVG fixes the entry
    and the bug in one move.

NOT DONE HERE
    docs/img/logos/logo-d.webp is left in place. Nothing references it
    after this, but removing an asset is its own call and does not need
    to ride along with swapping one.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DRY = "--dry" in sys.argv

TARGETS = [
    (
        "docs/index.html",
        "appbar logo src",
        'src="./img/logos/logo-d.webp"',
        'src="./img/logos/logo.svg"',
    ),
    (
        "docs/sw.js",
        "precache entry (was a dead .png path)",
        "  './img/logos/logo-d.png',",
        "  './img/logos/logo.svg',",
    ),
]


def main() -> None:
    print("Redesign stage 4 — logo references" + ("  (DRY RUN)" if DRY else ""))
    print()

    svg = ROOT / "docs" / "img" / "logos" / "logo.svg"
    if not svg.exists():
        raise SystemExit(
            "ABORT: docs/img/logos/logo.svg is missing.\n"
            "       git pull first — the mark lands in its own commit."
        )

    pending = []
    for rel, label, old, new in TARGETS:
        path = ROOT / rel
        if not path.exists():
            raise SystemExit(f"ABORT: {rel} not found — run from the repo root.")

        text = path.read_text(encoding="utf-8")
        n = text.count(old)
        if n == 1:
            pending.append((path, text.replace(old, new)))
            print(f"  OK    {rel:<18} {label}")
        elif new in text:
            print(f"  --    {rel:<18} {label} (already applied)")
        else:
            raise SystemExit(
                f"\nABORT: anchor in {rel} for {label!r} matched {n} times "
                f"(expected 1). Nothing written."
            )

    if DRY:
        print("\nDry run — nothing written.")
        return

    for path, text in pending:
        path.write_text(text, encoding="utf-8")

    print("\nDone.  Review:  git diff docs/index.html docs/sw.js")


if __name__ == "__main__":
    main()
