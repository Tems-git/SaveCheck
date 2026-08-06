#!/usr/bin/env python3
"""Can we build "which chain is cheapest for my basket" on the 22 categories?

    python scripts/analyze_category_basket.py
    python scripts/analyze_category_basket.py --show milk cheese coffee

Read-only. Touches nothing, writes nothing.

WHY THIS EXISTS
    Product-level cross-chain matching is not viable here — 15
    comparable groups out of 4310 offerings. But the question users
    actually ask is not "is this the same barcode", it is "where do I
    pay less for milk". Consumer price indices work the same way: they
    compare a litre of milk, not an SKU.

    The 22 BASKET categories already compute exactly that, per chain,
    and products.js carries category_tags so a cart item can reach a
    category without any new matching.

WHAT DECIDES IT
    1. Completeness. A basket total is only meaningful if every chain
       has a price for every category in it. Categories missing from
       some chains cannot be silently dropped — that flatters whichever
       chain has the most gaps.

    2. Tag coverage. If few offerings carry a category_tag, the bridge
       from a real shopping list into the comparison is too narrow.

    3. Whether the regexes catch the right thing. Printed per chain, to
       be read rather than trusted.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_JS = ROOT / "docs" / "data.js"
PRODUCTS_JS = ROOT / "docs" / "products.js"

CHAINS = ["Lidl", "Kaufland", "Billa", "Fantastico", "T Market"]


def load(path: Path, key: str):
    if not path.exists():
        raise SystemExit(f"ABORT: {path} not found — run from the repo root.")
    raw = path.read_text(encoding="utf-8")
    return json.loads(raw[raw.index("{"): raw.rindex("}") + 1])[key]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--show", nargs="*", default=None,
                    help="category ids to print matches for (default: all)")
    args = ap.parse_args()

    cats = load(DATA_JS, "products")          # legacy 22-category entries
    products = load(PRODUCTS_JS, "products")  # product-first snapshot

    # ── 1. completeness ──────────────────────────────────────────────
    print("=" * 74)
    print("CATEGORY COVERAGE PER CHAIN")
    print("=" * 74)
    print("\n  A basket total only means something if every chain in the")
    print("  comparison has a price for every category in the basket.\n")

    header = f"  {'category':<12}" + "".join(f"{c[:9]:>11}" for c in CHAINS)
    print(header)
    print("  " + "-" * (12 + 11 * len(CHAINS)))

    full, partial = [], []
    for entry in cats:
        pid = entry["id"]
        by_chain = entry.get("by_chain", {})
        cells = ""
        for c in CHAINS:
            st = by_chain.get(c)
            cells += f"{st['current_price']:>11.2f}" if st else f"{'—':>11}"
        print(f"  {pid:<12}{cells}")
        (full if len(by_chain) == len(CHAINS) else partial).append(pid)

    print(f"\n  complete in all {len(CHAINS)} chains : {len(full):>2} of {len(cats)}")
    print(f"  partial                  : {len(partial):>2}")
    if partial:
        print(f"    {', '.join(partial)}")

    print("\n  A basket built only from the complete set is honest without")
    print("  caveats. Including partial categories means either excluding")
    print("  chains per category or saying plainly what the total covers.")

    # ── 2. tag coverage ──────────────────────────────────────────────
    print("\n" + "=" * 74)
    print("CATEGORY TAG COVERAGE  (the cart -> category bridge)")
    print("=" * 74)

    tagged = [p for p in products if p.get("category_tags")]
    pct = 100 * len(tagged) / len(products) if products else 0
    print(f"\n  {len(tagged)} of {len(products)} offerings carry a tag  ({pct:.1f}%)")

    per_chain = Counter(p["chain"] for p in tagged)
    tot_chain = Counter(p["chain"] for p in products)
    print(f"\n  {'chain':<13}{'tagged':>9}{'total':>9}{'share':>9}")
    print("  " + "-" * 40)
    for c in CHAINS:
        t, n = per_chain.get(c, 0), tot_chain.get(c, 0)
        share = f"{100 * t / n:.1f}%" if n else "—"
        print(f"  {c:<13}{t:>9}{n:>9}{share:>9}")

    print("\n  This is the ceiling on how much of a real shopping list can")
    print("  enter the comparison at all. Everything untagged is invisible")
    print("  to a category-based basket.")

    per_cat = Counter(t for p in tagged for t in p["category_tags"])
    thin = [c["id"] for c in cats if per_cat.get(c["id"], 0) < 5]
    if thin:
        print(f"\n  categories matching under 5 offerings anywhere: {', '.join(thin)}")

    # ── 3. read the matches ──────────────────────────────────────────
    print("\n" + "=" * 74)
    print("WHAT EACH CATEGORY ACTUALLY CAUGHT — read these")
    print("=" * 74)
    print("The counts above can look healthy while the patterns are picking")
    print("the wrong products. This is the only check that catches it.\n")

    wanted = set(args.show) if args.show else None
    by_cat_chain: dict[str, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))
    for p in tagged:
        for t in p["category_tags"]:
            by_cat_chain[t][p["chain"]].append(p)

    for entry in cats:
        pid = entry["id"]
        if wanted and pid not in wanted:
            continue
        print(f"  --- {pid} ---")
        hits = by_cat_chain.get(pid, {})
        if not hits:
            print("      nothing tagged in any chain\n")
            continue
        for c in CHAINS:
            items = sorted(hits.get(c, []), key=lambda x: x.get("price") or 0)
            if not items:
                print(f"      {c:<12} —")
                continue
            cheapest = items[0]
            extra = f"   (+{len(items) - 1} more)" if len(items) > 1 else ""
            print(f"      {c:<12} {cheapest['price']:>7.2f}  "
                  f"{cheapest['name'][:46]}{extra}")
        print()


if __name__ == "__main__":
    main()
