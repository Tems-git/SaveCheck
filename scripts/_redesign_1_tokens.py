#!/usr/bin/env python3
"""Redesign stage 1: self-hosted Golos Text + Design-1 colour tokens.

Run from the repo root:

    python scripts/_redesign_1_tokens.py --dry    # preview, downloads nothing
    python scripts/_redesign_1_tokens.py          # download fonts + patch

WHY SELF-HOST THE FONT
    The Cloudflare CSP is `default-src 'self'` with no font-src of its
    own, so font-src inherits 'self' and fonts.gstatic.com is blocked.
    Rather than loosen the CSP for a cosmetic dependency we vendor the
    files, exactly like docs/img/TwemojiCountryFlags.woff2 already is.

    Google serves Golos Text as a VARIABLE font, so each unicode subset
    is a single woff2 covering the whole 400..900 weight range — four
    small files instead of one per weight.

WHAT IT TOUCHES
    docs/img/fonts/*.woff2   (new)
    docs/index.html          @font-face block, body font stack,
                             :root + dark tokens, JS C map, theme-color

Each edit asserts its anchor exists. If the source has drifted the
script aborts before writing anything.
"""

from __future__ import annotations

import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "docs" / "index.html"
FONT_DIR = ROOT / "docs" / "img" / "fonts"
DRY = "--dry" in sys.argv

GOOGLE_CSS = (
    "https://fonts.googleapis.com/css2?family=Golos+Text:wght@400..900&display=swap"
)
# woff2 is only served to browsers that advertise support.
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)

# Subsets worth shipping. Greek is in here because the UI ships an EL
# locale; the rest of the Balkan languages are covered by latin-ext.
WANTED_SUBSETS = {"cyrillic", "cyrillic-ext", "latin", "latin-ext", "greek", "greek-ext"}


def fetch_google_css() -> str:
    req = urllib.request.Request(GOOGLE_CSS, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8")


def parse_faces(css: str) -> list[dict]:
    """Pull (subset, unicode-range, url, weight) out of Google's CSS."""
    faces = []
    # Google emits `/* subset */` immediately before each @font-face.
    chunks = re.split(r"/\*\s*([a-z-]+)\s*\*/", css)
    for i in range(1, len(chunks) - 1, 2):
        subset, block = chunks[i], chunks[i + 1]
        if subset not in WANTED_SUBSETS:
            continue
        url = re.search(r"src:\s*url\(([^)]+)\)", block)
        rng = re.search(r"unicode-range:\s*([^;]+);", block)
        wght = re.search(r"font-weight:\s*([^;]+);", block)
        if not (url and rng):
            continue
        faces.append({
            "subset": subset,
            "url": url.group(1).strip("'\""),
            "range": rng.group(1).strip(),
            "weight": wght.group(1).strip() if wght else "400 900",
        })
    return faces


def download_fonts(faces: list[dict]) -> list[dict]:
    FONT_DIR.mkdir(parents=True, exist_ok=True)
    out = []
    for f in faces:
        name = f"GolosText-{f['subset']}.woff2"
        dest = FONT_DIR / name
        if not dest.exists():
            req = urllib.request.Request(f["url"], headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=30) as r:
                dest.write_bytes(r.read())
        kb = dest.stat().st_size / 1024
        print(f"    {name:<34} {kb:6.1f} KB")
        out.append({**f, "file": name})
    return out


def build_font_face_css(faces: list[dict]) -> str:
    lines = ["  /* Golos Text — self-hosted (CSP default-src 'self' blocks Google Fonts).",
             "     Variable woff2: one file per unicode subset, all weights 400..900. */"]
    for f in faces:
        lines += [
            "  @font-face {",
            "    font-family: 'Golos Text';",
            "    font-style: normal;",
            f"    font-weight: {f['weight']};",
            "    font-display: swap;",
            f"    src: url('./img/fonts/{f['file']}') format('woff2');",
            f"    unicode-range: {f['range']};",
            "  }",
        ]
    return "\n".join(lines) + "\n"


# ── exact-anchor replacements ────────────────────────────────────────

ROOT_OLD = """  :root {
    --green:#16a34a; --green-d:#15803d; --green-bg:#eaf5ee;
    --yellow:#d97706; --red:#dc2626; --gray:#6b7280;
    --ink:#111827; --muted:#6b7280; --line:#f0ece4; --card:#ffffff; --cream:#f5f1ea;"""

ROOT_NEW = """  :root {
    /* Design 1 palette. --deep* drive the hero gradient and any dark
       surface; --accent-lt is the on-dark brand accent. */
    --deep:#0C2A1B; --deep-2:#12492C; --deep-3:#16653B; --accent-lt:#7BEBAC;
    --green:#0E7A43; --green-d:#0B5F35; --green-bg:#E7F2EA;
    --yellow:#C98A08; --red:#D4342B; --gray:#6B7F72;
    --ink:#0F1A14; --muted:#6B7F72; --line:#E4EAE4; --card:#ffffff; --cream:#F5F7F4;"""

DARK_OLD = """  [data-theme="dark"] {
    --green:#22c55e; --green-d:#16a34a; --green-bg:#14532d;
    --yellow:#fbbf24; --red:#f87171; --gray:#9ca3af;
    --ink:#e8eaf0; --muted:#8b9ab0; --line:#2c2c2e; --card:#1c1c1e; --cream:#111113;"""

DARK_NEW = """  [data-theme="dark"] {
    /* Same hues lifted for contrast on dark; greys carry a green cast so
       the two themes read as one family. */
    --deep:#0A2016; --deep-2:#0E3722; --deep-3:#124D2D; --accent-lt:#7BEBAC;
    --green:#34D399; --green-d:#10B981; --green-bg:#0F3A24;
    --yellow:#E0A82E; --red:#F2685C; --gray:#8FA396;
    --ink:#E6EFE9; --muted:#8FA396; --line:#243029; --card:#131A15; --cream:#0B120D;"""

BODY_OLD = """    margin:0; font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;
    color:var(--ink); -webkit-font-smoothing:antialiased; min-height:100vh; padding:24px 12px 36px;
    background:radial-gradient(1100px 560px at 50% -8%, #e9f5ed, #e6e0d5);"""

BODY_NEW = """    margin:0; font-family:'Golos Text',-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;
    color:var(--ink); -webkit-font-smoothing:antialiased; min-height:100vh; padding:24px 12px 36px;
    font-variant-numeric:tabular-nums;
    background:radial-gradient(120% 90% at 50% 0%, #DCE7DE 0%, #EDF1EC 55%, #E4EAE4 100%);"""

DARKBODY_OLD = (
    '  [data-theme="dark"] body { background:radial-gradient'
    "(1100px 560px at 50% -8%,#0a2418,#0f0f11); }"
)
DARKBODY_NEW = (
    '  [data-theme="dark"] body { background:radial-gradient'
    "(120% 90% at 50% 0%,#0A2016,#070B08); }"
)

C_OLD = "const C = { red:'#dc2626', green:'#16a34a', yellow:'#f59e0b', gray:'#6b7280' };"
C_NEW = (
    "// Verdict colours. Kept in sync with the --red/--green/--yellow/--gray\n"
    "// tokens above; these are baked into inline styles the CSS can't reach.\n"
    "const C = { red:'#D4342B', green:'#0E7A43', yellow:'#C98A08', gray:'#6B7F72' };"
)

THEME_OLD = '<meta name="theme-color" content="#16a34a" />'
THEME_NEW = '<meta name="theme-color" content="#0C2A1B" />'

# Anchor the new @font-face block just above the existing Twemoji one so
# all font declarations live together.
TWEMOJI_ANCHOR = "  @font-face {\n    font-family: 'Twemoji Country Flags';"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    n = text.count(old)
    if n != 1:
        raise SystemExit(
            f"ABORT: anchor {label!r} matched {n} times (expected 1).\n"
            f"       docs/index.html has drifted — nothing was written."
        )
    print(f"    patched: {label}")
    return text.replace(old, new)


def main() -> None:
    if not INDEX.exists():
        raise SystemExit(f"ABORT: {INDEX} not found — run from the repo root.")

    print("Redesign stage 1 — typography + palette" + ("  (DRY RUN)" if DRY else ""))

    print("\n  fonts:")
    if DRY:
        print("    (dry run — skipping download)")
        faces = []
    else:
        faces = download_fonts(parse_faces(fetch_google_css()))
        if not faces:
            raise SystemExit("ABORT: no usable @font-face rules came back from Google.")

    print("\n  index.html:")
    text = INDEX.read_text(encoding="utf-8")

    if "Golos Text" in text:
        print("    -- @font-face already present, skipping insert")
    elif faces:
        text = replace_once(
            text, TWEMOJI_ANCHOR,
            build_font_face_css(faces) + TWEMOJI_ANCHOR,
            "@font-face block inserted",
        )

    text = replace_once(text, ROOT_OLD, ROOT_NEW, ":root tokens")
    text = replace_once(text, DARK_OLD, DARK_NEW, "dark theme tokens")
    text = replace_once(text, BODY_OLD, BODY_NEW, "body font stack + backdrop")
    text = replace_once(text, DARKBODY_OLD, DARKBODY_NEW, "dark backdrop")
    text = replace_once(text, C_OLD, C_NEW, "JS verdict colour map")
    text = replace_once(text, THEME_OLD, THEME_NEW, "theme-color meta")

    if DRY:
        print("\nDry run — nothing written.")
        return

    INDEX.write_text(text, encoding="utf-8")
    total = sum((FONT_DIR / f["file"]).stat().st_size for f in faces) / 1024
    print(f"\nDone. {len(faces)} font file(s), {total:.0f} KB total.")
    print("Review:  git diff docs/index.html  |  git status docs/img/fonts")


if __name__ == "__main__":
    main()
