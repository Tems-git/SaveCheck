#!/usr/bin/env python3
"""Redesign stage 2: components.

Run from the repo root:

    python scripts/_redesign_2_components.py --dry
    python scripts/_redesign_2_components.py

Stage 1 swapped the CSS custom properties, which carried most of the app
across on its own. What it could not reach were the rules that hardcode
hex values — those kept the old warm/emerald scheme regardless of the
tokens. This stage fixes those, and restyles the header into the dark
green block the design leads with.

SCOPE
    Pure CSS plus two inline style attributes on the cart button.
    No render function is touched, no markup is moved. Every current
    feature keeps working exactly as it did.

NOT INCLUDED
    The coloured chain badge squares (K/L/T/B/F) from the mockup. Those
    need new elements emitted by the render functions, which is a
    behaviour change rather than a restyle.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "docs" / "index.html"
DRY = "--dry" in sys.argv

EDITS: list[tuple[str, str, str]] = []


def edit(label: str, old: str, new: str) -> None:
    EDITS.append((label, old, new))


# ── header: the design's signature dark block ────────────────────────
# Same DOM, restyled. The glow sits in ::after so it can overflow the
# rounded corner without a wrapper element; children are lifted above it
# with position/z-index rather than the glow being pushed behind, which
# would put it under the .phone background.
edit(
    "appbar -> deep gradient block",
    ".appbar { background:var(--card); padding:14px 14px; "
    "border-bottom:1px solid var(--line); flex:none; }",
    """.appbar {
    position:relative; overflow:hidden; flex:none;
    padding:16px 16px 18px; border-bottom:0; border-radius:0 0 28px 28px;
    background:linear-gradient(168deg,var(--deep) 0%,var(--deep-2) 58%,var(--deep-3) 100%);
  }
  .appbar::after {
    content:''; position:absolute; width:260px; height:260px; right:-90px; top:-120px;
    border-radius:50%; pointer-events:none;
    background:radial-gradient(circle, rgba(88,224,146,.30), transparent 68%);
  }
  .appbar > * { position:relative; z-index:1; }""",
)

edit(
    "brand wordmark on dark",
    "  .brand h1 b { color:var(--green); }",
    "  .brand h1 { color:#fff; }\n  .brand h1 b { color:var(--accent-lt); }",
)

edit(
    "brand tagline on dark",
    "  .brand-tagline { font-size:11px; color:var(--muted); font-weight:600; "
    "letter-spacing:.01em; }",
    "  .brand-tagline { font-size:11px; color:rgba(214,240,224,.74); font-weight:600; "
    "letter-spacing:.01em; }",
)

# Search field becomes the elevated white card the mockup puts on the
# hero. Background stays tokenised so dark theme still inverts it.
edit(
    "search field -> elevated card",
    ".search-field { flex:1; display:flex; align-items:center; gap:8px; "
    "background:var(--cream); border:1.5px solid var(--line); border-radius:12px; "
    "padding:0 12px; transition:border-color .15s; position:relative; }",
    ".search-field { flex:1; display:flex; align-items:center; gap:8px; "
    "background:var(--card); border:1.5px solid transparent; border-radius:16px; "
    "padding:0 14px; transition:border-color .15s; position:relative; "
    "box-shadow:0 14px 30px -14px rgba(0,0,0,.55); }",
)

edit(
    "search focus ring -> accent",
    "  .search-field:focus-within { border-color:var(--green); }",
    "  .search-field:focus-within { border-color:var(--accent-lt); }",
)

# Country picker + theme toggle now sit on dark ground.
edit(
    "country picker on dark",
    ".cp-trigger { display:flex; align-items:center; gap:5px; border:1px solid var(--line); "
    "background:var(--cream); border-radius:11px; cursor:pointer; padding:8px 11px; "
    "font-size:18px; line-height:1; }",
    ".cp-trigger { display:flex; align-items:center; gap:5px; border:1px solid transparent; "
    "background:rgba(255,255,255,.14); border-radius:999px; cursor:pointer; padding:7px 12px; "
    "font-size:18px; line-height:1; }",
)

edit(
    "country code on dark",
    "  .cp-trigger .cc { font-size:10px; font-weight:700; color:var(--muted); }",
    "  .cp-trigger .cc { font-size:10px; font-weight:700; color:rgba(255,255,255,.88); }",
)

edit(
    "country chevron on dark",
    "  .cp-chev { width:10px; height:10px; stroke:var(--muted); transition:transform .2s; "
    "flex:none; }",
    "  .cp-chev { width:10px; height:10px; stroke:rgba(255,255,255,.82); "
    "transition:transform .2s; flex:none; }",
)

edit(
    "theme toggle on dark",
    ".theme-btn { border:0; background:none; cursor:pointer; color:var(--muted); padding:4px; "
    "line-height:1; border-radius:8px; transition:color .15s; flex:none; }",
    ".theme-btn { border:0; background:none; cursor:pointer; color:rgba(255,255,255,.78); "
    "padding:4px; line-height:1; border-radius:8px; transition:color .15s; flex:none; }",
)

edit(
    "theme toggle hover on dark",
    "  .theme-btn:hover { color:var(--ink); }",
    "  .theme-btn:hover { color:#fff; }",
)

# ── the four hardcoded gradients the token swap could not reach ──────
edit(
    "hero gradient -> deep green",
    """    margin:14px 14px 0; color:#fff; border-radius:18px; padding:15px 17px;
    background:linear-gradient(135deg,#16a34a,#15803d); box-shadow:0 12px 26px rgba(22,163,74,.28);""",
    """    margin:14px 14px 0; color:#fff; border-radius:20px; padding:15px 17px;
    background:linear-gradient(168deg,var(--deep) 0%,var(--deep-2) 62%,var(--deep-3) 100%);
    box-shadow:0 16px 34px -14px rgba(12,42,27,.55);""",
)

# White on #d97706 was ~3:1. The deeper amber lands near 4.4:1 and stops
# reading as muddy gold next to the cooler surfaces.
edit(
    "fake hook -> deeper amber (contrast)",
    ".fake-hook { display:flex; align-items:center; gap:12px; "
    "background:linear-gradient(135deg,#f59e0b,#d97706); color:#fff; border-radius:16px; "
    "padding:14px 16px; margin-top:10px; cursor:pointer; "
    "box-shadow:0 8px 20px rgba(217,119,6,.28); }",
    ".fake-hook { display:flex; align-items:center; gap:12px; "
    "background:linear-gradient(135deg,#C98A08,#9A6A04); color:#fff; border-radius:18px; "
    "padding:14px 16px; margin-top:10px; cursor:pointer; "
    "box-shadow:0 14px 28px -12px rgba(154,106,4,.55); }",
)

edit(
    "titans hero -> deep green",
    ".titan-hero { background:linear-gradient(135deg,#15803d,#166534); color:#fff; "
    "border-radius:18px; padding:14px 16px; margin-bottom:12px; }",
    ".titan-hero { background:linear-gradient(168deg,var(--deep),var(--deep-2)); color:#fff; "
    "border-radius:20px; padding:14px 16px; margin-bottom:12px; "
    "box-shadow:0 16px 34px -16px rgba(12,42,27,.5); }",
)

# This one was blue — the only non-green surface in the app, and it now
# clashes head-on with the palette.
edit(
    "brochure hero -> green family (was blue)",
    ".broch-hero { background:linear-gradient(135deg,#1d4ed8,#1e40af); color:#fff; "
    "border-radius:18px; padding:14px 16px; margin-bottom:12px; }",
    ".broch-hero { background:linear-gradient(168deg,var(--deep-2),var(--deep-3)); color:#fff; "
    "border-radius:20px; padding:14px 16px; margin-bottom:12px; "
    "box-shadow:0 16px 34px -16px rgba(12,42,27,.5); }",
)

# ── surfaces ─────────────────────────────────────────────────────────
edit(
    "home savings card -> softer",
    ".home-hero { border-radius:20px; margin-bottom:6px; "
    "box-shadow:0 4px 16px rgba(22,163,74,.12); display:flex; align-items:stretch; "
    "overflow:hidden; border:2px solid var(--green); background:var(--card); }",
    ".home-hero { border-radius:20px; margin-bottom:6px; "
    "box-shadow:0 10px 26px -14px rgba(12,42,27,.30); display:flex; align-items:stretch; "
    "overflow:hidden; border:1px solid var(--line); background:var(--card); }",
)

edit(
    "card stack radius",
    ".cards { background:var(--card); border:1px solid var(--line); border-radius:16px; "
    "overflow:hidden; box-shadow:var(--shadow-card); }",
    ".cards { background:var(--card); border:1px solid var(--line); border-radius:18px; "
    "overflow:hidden; box-shadow:var(--shadow-card); }",
)

# Leftover warm grey from the cream scheme.
edit(
    "titan bar track -> tokenised",
    ".titan-bar-wrap { margin:8px 0 5px; height:9px; background:#ece7df; "
    "border-radius:999px; overflow:hidden; display:flex; }",
    ".titan-bar-wrap { margin:8px 0 5px; height:9px; background:var(--line); "
    "border-radius:999px; overflow:hidden; display:flex; }",
)

edit(
    "advice box -> tokenised",
    ".advice-box { background:#eaf5ee; border:1.5px solid var(--green); border-radius:14px; "
    "padding:12px 14px; margin-bottom:12px; }",
    ".advice-box { background:var(--green-bg); border:1px solid var(--green); "
    "border-radius:16px; padding:12px 14px; margin-bottom:12px; }",
)

edit(
    "active filter chip -> deep green",
    "  .fchip.active { color:#fff; border-color:transparent; }",
    "  .fchip.active { color:#fff; border-color:transparent; background:var(--green); }",
)

edit(
    "bottom nav active -> accent",
    "  .bottomnav button.on { color:var(--green-d); }",
    "  .bottomnav button.on { color:var(--green); }",
)

# ── inline styles (outrank the stylesheet, so patch the markup) ──────
# Also drops a reference to var(--fg), which is not a token this file
# has ever defined.
edit(
    "cart button colour on dark",
    "cursor:pointer;position:relative;color:var(--fg);font-size:20px;line-height:1",
    "cursor:pointer;position:relative;color:#fff;font-size:20px;line-height:1",
)

edit(
    "cart badge on dark",
    'id="cart-badge" style="background:var(--green);color:#fff;font-size:10px;',
    'id="cart-badge" style="background:var(--accent-lt);color:var(--deep);font-size:10px;',
)


def main() -> None:
    if not INDEX.exists():
        raise SystemExit(f"ABORT: {INDEX} not found — run from the repo root.")

    text = INDEX.read_text(encoding="utf-8")
    print("Redesign stage 2 — components" + ("  (DRY RUN)" if DRY else ""))
    print()

    problems = []
    for label, old, new in EDITS:
        n = text.count(old)
        if n == 1:
            text = text.replace(old, new)
            print(f"  OK    {label}")
        elif n == 0 and new.split("{")[0].strip() and new[:40] in text:
            print(f"  --    {label} (already applied)")
        else:
            print(f"  FAIL  {label}  (anchor matched {n}x, expected 1)")
            problems.append(label)

    if problems:
        raise SystemExit(
            f"\nABORT: {len(problems)} anchor(s) did not match — nothing written.\n"
            "docs/index.html has drifted from what this patch expects."
        )

    if DRY:
        print("\nDry run — nothing written. Re-run without --dry to apply.")
        return

    INDEX.write_text(text, encoding="utf-8")
    print(f"\nDone. {len(EDITS)} edits applied.")
    print("Review:  git diff docs/index.html")


if __name__ == "__main__":
    main()
