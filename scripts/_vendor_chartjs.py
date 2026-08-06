#!/usr/bin/env python3
"""One-off: vendor Chart.js so the price chart works offline.

    python scripts/_vendor_chartjs.py --dry
    python scripts/_vendor_chartjs.py

WHY
    The 90-day chart is the substance of the product detail view, and it
    is the one part that cannot render offline: Chart.js is fetched from
    jsDelivr, and the service worker passes cross-origin requests
    straight through without caching them. The app is meant to be used
    standing in a shop with poor signal.

    Locally hosted, it also becomes cacheable by the shell's
    stale-while-revalidate branch, and cdn.jsdelivr.net can come out of
    the CSP — it currently appears in both script-src and connect-src.

WHAT IT DOES
    Reads the jsDelivr URL already present in docs/index.html and
    downloads exactly that, rather than a version chosen here. The
    vendored file is then the same build that has been serving
    production, with no version bump smuggled in.

    Saves to docs/js/ and repoints the reference.

WHAT IT DELIBERATELY DOES NOT DO
    Touch the CSP. That lives in Cloudflare, and tightening it before
    vendored copies have propagated would block the chart for anyone
    still running cached HTML that points at the CDN. Ship this first,
    let clients turn over, then remove cdn.jsdelivr.net by hand.

    Add the file to SHELL_URLS. Chart.js is lazy-loaded on first modal
    open and precaching 200 KB would undo that. Same-origin now, so the
    shell's stale-while-revalidate branch picks it up the first time a
    chart is opened, and it is available offline from then on.
"""

from __future__ import annotations

import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "docs" / "index.html"
JS_DIR = ROOT / "docs" / "js"
DRY = "--dry" in sys.argv

CDN_RE = re.compile(
    r"https://cdn\.jsdelivr\.net/[^\s'\"<>()]*[Cc]hart[^\s'\"<>()]*\.js"
)

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)


def main() -> None:
    if not INDEX.exists():
        raise SystemExit(f"ABORT: {INDEX} not found — run from the repo root.")

    text = INDEX.read_text(encoding="utf-8")
    print("Vendor Chart.js" + ("  (DRY RUN)" if DRY else ""))
    print()

    if "./js/chart" in text and CDN_RE.search(text) is None:
        print("  --  already vendored")
        return

    urls = sorted(set(CDN_RE.findall(text)))
    if not urls:
        raise SystemExit(
            "ABORT: no jsDelivr Chart.js URL found in docs/index.html.\n"
            "       Either it is already vendored or the reference has moved."
        )
    if len(urls) > 1:
        print("  found several references:")
        for u in urls:
            print(f"    {u}")
        raise SystemExit(
            "\nABORT: expected exactly one URL. Nothing written — resolve by hand\n"
            "       so the vendored copy is unambiguous."
        )

    url = urls[0]
    name = url.rsplit("/", 1)[-1]
    dest = JS_DIR / name
    local_ref = f"./js/{name}"

    print(f"  source   {url}")
    print(f"  target   docs/js/{name}")

    if DRY:
        print("\nDry run — nothing downloaded or written.")
        return

    JS_DIR.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        payload = r.read()

    # A truncated or error-page download would be worse than no change at
    # all, since the chart would then fail with no CDN left to fall back on.
    if len(payload) < 50_000 or b"Chart" not in payload[:200_000]:
        raise SystemExit(
            f"ABORT: downloaded {len(payload)} bytes and it does not look like\n"
            "       Chart.js. Nothing written."
        )

    dest.write_bytes(payload)
    text = text.replace(url, local_ref)
    INDEX.write_text(text, encoding="utf-8")

    print(f"  size     {len(payload) / 1024:.0f} KB")
    print("\nDone.  Review:  git status docs/js  &&  git diff docs/index.html")
    print("\nAfter this is deployed and clients have turned over, remove")
    print("https://cdn.jsdelivr.net from script-src and connect-src in the")
    print("Cloudflare CSP Transform Rule — not before.")


if __name__ == "__main__":
    main()
