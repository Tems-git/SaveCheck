#!/usr/bin/env python3
"""One-off: update the README for the service worker and Chart.js changes.

    python scripts/_readme_sw_chart.py --dry
    python scripts/_readme_sw_chart.py

WHAT WENT STALE
    * The service worker section describes the shell as cache-first and
      the data branch as untimed. Both changed.
    * Tech stack sends Chart.js to jsDelivr at 4.4; it is vendored at
      4.4.1.
    * The payload table lists a 64 KB logo raster that is gone and omits
      the 206 KB of Chart.js that is now local.
    * The structure tree has no docs/js.

WHAT IS LEFT ALONE ON PURPOSE
    The CSP row. cdn.jsdelivr.net is still in the live policy — that
    change lives in Cloudflare and has to wait until vendored copies
    have propagated, or clients on cached HTML lose their chart.
    Documenting the intended policy rather than the deployed one would
    be exactly the kind of small untruth this session has been removing.
    A note records what is pending and why the order matters.

Each edit stands alone; misses are reported rather than aborting.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
DRY = "--dry" in sys.argv

EDITS = [
    (
        "tech stack — Charts row",
        "| Charts | Chart.js 4.4 (jsDelivr CDN, lazy loaded on first modal open) |",
        "| Charts | Chart.js 4.4.1 — vendor-нат в `docs/js/`, lazy loaded при първо"
        " отваряне на модал. Беше на jsDelivr CDN, което правеше графиката единствената"
        " част от детайлния изглед, недостъпна офлайн. |",
    ),
    (
        "PWA — service worker description",
        """- **Service worker** (`docs/sw.js`) — two-tier caching strategy:
  - **Shell (index.html, icons, manifest)** — cache-first, instant load
  - **Data (products.js, brochures.js, history)** — network-first с cache fallback за offline usage""",
        """- **Service worker** (`docs/sw.js`) — two-tier caching strategy:
  - **Shell (index.html, icons, manifest, logo)** — **stale-while-revalidate**: кешираното
    копие се сервира веднага, а фонова заявка го обновява за следващото отваряне. Най-лошият
    случай е една визита назад. Преди беше cache-first, но реализацията беше `cached || fetch(...)`,
    тоест веднъж кеширан файл **никога** не се проверяваше отново до ръчен bump на `CACHE_VERSION` —
    въпреки коментар в самия файл, който твърдеше обратното.
  - **Data (products.js, brochures.js, history)** — network-first с **4-секунден таймаут** и cache
    fallback. Приложението се ползва в магазин със слаб сигнал; без граница заявката виси до
    вътрешния лимит на браузъра, докато годно кеширано копие стои неизползвано. Ако таймерът
    спечели, заявката се оставя да върви — така кешът пак се освежава за следващия път.""",
    ),
    (
        "payload table — logo row",
        "| `logo-d.webp` | ~64 KB | Was 1.4 MB PNG, converted (-95%) |",
        "| `logos/logo.svg` | ~1 KB | Векторно. Замени 64 KB WebP растер, който още изписваше"
        " старото име |",
    ),
    (
        "payload table — Chart.js row",
        "| `products-history.js` | 0 KB | **Lazy** — loads with Chart.js on first product modal open |",
        "| `products-history.js` | 0 KB | **Lazy** — loads with Chart.js on first product modal open |\n"
        "| `js/chart.umd.min.js` | 0 KB | **Lazy** — vendor-нат, ~206 KB при първо отваряне на"
        " графика; оттам нататък се сервира от SW кеша, включително офлайн |",
    ),
    (
        "security — pending CSP note",
        "**Grade A** на securityheaders.com",
        "> **Предстои:** Chart.js вече е локален, така че `https://cdn.jsdelivr.net` може да отпадне\n"
        "> от `script-src` и `connect-src`. Промяната е в Cloudflare и се прави **след** като\n"
        "> vendor-натата версия се разпространи — клиент със стар кеширан HTML още сочи към CDN-а\n"
        "> и графиката му би се блокирала. Таблицата по-горе описва политиката такава, каквато е\n"
        "> в момента, не каквато ще стане.\n\n"
        "**Grade A** на securityheaders.com",
    ),
    (
        "structure tree — sw.js note",
        "│   ├── sw.js                     # Service Worker (two-tier caching)",
        "│   ├── sw.js                     # Service Worker (SWR shell + network-first data)",
    ),
    (
        "structure tree — docs/js",
        "│   ├── og.svg                    # Open Graph image",
        "│   ├── og.svg                    # Open Graph image\n"
        "│   ├── js/\n"
        "│   │   └── chart.umd.min.js      # Vendor-нат Chart.js 4.4.1 (офлайн графики)",
    ),
]


def main() -> None:
    if not README.exists():
        raise SystemExit(f"ABORT: {README} not found — run from the repo root.")

    text = README.read_text(encoding="utf-8")
    print("README — service worker + Chart.js" + ("  (DRY RUN)" if DRY else ""))
    print()

    misses = 0
    for label, old, new in EDITS:
        n = text.count(old)
        if n == 1:
            text = text.replace(old, new)
            print(f"  OK      {label}")
        elif n == 0 and new.split("\n")[0][:50] in text:
            print(f"  --      {label} (already applied)")
        else:
            print(f"  MISS    {label}  (matched {n}, expected 1)")
            misses += 1

    if not DRY:
        README.write_text(text, encoding="utf-8")

    # The findings script may or may not have been run before the history
    # one superseded it in conversation; worth knowing either way.
    print()
    if "Cross-chain matching — измерено и отпаднало" in text:
        print("  note: roadmap findings section present")
    else:
        print("  note: roadmap findings NOT present — scripts/_readme_findings.py")
        print("        appears never to have run. Worth checking.")

    print(f"\n{len(EDITS) - misses} of {len(EDITS)} applied."
          + ("  (dry run — nothing written)" if DRY else "  Review: git diff README.md"))


if __name__ == "__main__":
    main()
