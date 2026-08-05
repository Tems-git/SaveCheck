#!/usr/bin/env python3
"""How much of each chain's catalogue is the same item counted twice?

    python scripts/analyze_duplicates.py
    python scripts/analyze_duplicates.py --worst 25

Read-only. Touches nothing, writes nothing.

WHY THIS EXISTS
    Fantastico reports 2360 offerings, Kaufland 327. Fantastico runs
    about forty stores; Kaufland about three hundred. KZP's basket is
    regulated, so the chains report against much the same list and these
    numbers should not differ by a factor of seven in that direction.

    The data suggests why. Four Fantastico rows read

        ПЛЕШКА СВИНСКА БЕЗ КОСТ МК ЛОВЕЧ АД              2.99  −55%
        ПЛЕШКА СВИНСКА БЕЗ КОСТ ПР-Д БЪЛГАРИЯ АЛДАГОТ    2.99  −55%
        ПЛЕШКА СВИНСКА БЕЗ КОСТ ПР-Д БЪЛГАРИЯ БИЛЯНА-МЕС 2.99  −55%
        ПЛЕШКА СВИНСКА БЕЗ КОСТ ПР-Д БЪЛГАРИЯ САРАЙ РАЗЛОГ 2.99 −55%

    Same shelf item, four suppliers, four product codes, identical price
    and identical discount. The pipeline treats them as four products.

WHAT IT MEASURES
    Strip the supplier tail, regroup, and see how far each chain's count
    falls. Then check what share of the collapsed groups carry a single
    price across all their members — same price is the strong signal
    that a group is one item rather than several real variants.

WHY IT MATTERS BEYOND TIDINESS
    Every user-facing count derived from offerings inherits the
    inflation: the real-promotions figure on Home, the misleading-
    promotions counter, and the Battle of the Titans denominators. That
    leaderboard ranks chains on "tracked products" — 2391 for Fantastico
    against 165 for Billa. If one side counts the same item repeatedly
    the ranking is comparing unlike quantities.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRODUCTS_JS = ROOT / "docs" / "products.js"

# Supplier markers seen in the KZP feed. "ПР-Д" is производител; the
# company-form tail catches "МК ЛОВЕЧ АД" and friends, allowing up to
# three words of company name before the legal form.
_PRODUCER_CUT = re.compile(r"\s+(?:ПР-?Д|ПР-?ВО|ПРОИЗВ\w*)\b.*$", re.IGNORECASE)
_COMPANY_TAIL = re.compile(
    r"\s+(?:[\w\-]+\s+){0,3}(?:ЕООД|ООД|АД|ЕТ|СД)\.?\s*$", re.IGNORECASE
)

_QTY = [
    (re.compile(r"(\d+[.,]?\d*)\s*(?:кг|kg)\b", re.I), lambda v: f"{v * 1000:.0f}g"),
    (re.compile(r"(\d+[.,]?\d*)\s*(?:гр|г|g)\b", re.I), lambda v: f"{v:.0f}g"),
    (re.compile(r"(\d+[.,]?\d*)\s*(?:л|l)\b", re.I), lambda v: f"{v * 1000:.0f}ml"),
    (re.compile(r"(\d+[.,]?\d*)\s*(?:мл|ml)\b", re.I), lambda v: f"{v:.0f}ml"),
]
_PUNCT = re.compile(r"[^\w\s]", re.UNICODE)
_WS = re.compile(r"\s+")


def base_name(name: str) -> str:
    """Product identity with the supplier stripped off."""
    s = _PRODUCER_CUT.sub("", name)
    prev = None
    while prev != s:                      # e.g. "... БИЛЯНА-МЕС ООД АД"
        prev = s
        s = _COMPANY_TAIL.sub("", s)
    qty = ""
    for pat, fmt in _QTY:
        m = pat.search(s)
        if m:
            try:
                qty = fmt(float(m.group(1).replace(",", ".")))
            except ValueError:
                break
            s = s[: m.start()] + " " + s[m.end():]
            break
    return f"{_WS.sub(' ', _PUNCT.sub(' ', s.lower())).strip()}|{qty}"


def load() -> list[dict]:
    if not PRODUCTS_JS.exists():
        raise SystemExit(f"ABORT: {PRODUCTS_JS} not found — run from the repo root.")
    raw = PRODUCTS_JS.read_text(encoding="utf-8")
    return json.loads(raw[raw.index("{"): raw.rindex("}") + 1])["products"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--worst", type=int, default=15,
                    help="how many worst-duplicated names to print (default 15)")
    args = ap.parse_args()

    products = load()

    by_chain: dict[str, list[dict]] = defaultdict(list)
    for p in products:
        by_chain[p["chain"]].append(p)

    print("=" * 74)
    print("PER-CHAIN DUPLICATION  (supplier suffix stripped)")
    print("=" * 74)
    print(f"\n  {'chain':<13}{'offerings':>10}{'distinct':>10}{'factor':>9}"
          f"{'in dup grp':>12}{'same price':>12}")
    print("  " + "-" * 64)

    summary = {}
    for chain, items in sorted(by_chain.items(), key=lambda kv: -len(kv[1])):
        groups: dict[str, list[dict]] = defaultdict(list)
        for p in items:
            groups[base_name(p["name"])].append(p)

        dup_groups = {k: v for k, v in groups.items() if len(v) > 1}
        in_dup = sum(len(v) for v in dup_groups.values())
        same_price = sum(
            1 for v in dup_groups.values()
            if len({round(x.get("price") or 0, 2) for x in v}) == 1
        )

        factor = len(items) / len(groups) if groups else 0
        pct_dup = 100 * in_dup / len(items) if items else 0
        pct_same = 100 * same_price / len(dup_groups) if dup_groups else 0

        print(f"  {chain:<13}{len(items):>10}{len(groups):>10}{factor:>8.2f}x"
              f"{pct_dup:>11.1f}%{pct_same:>11.1f}%")
        summary[chain] = (len(items), len(groups), groups)

    print("\n  factor      offerings per distinct product; 1.00x means no duplication")
    print("  in dup grp  share of offerings sharing a name with another")
    print("  same price  share of those groups where every member costs the same,")
    print("              which is the strong signal for one shelf item, not variants")

    # What the leaderboard denominators would look like deduplicated.
    print("\n" + "=" * 74)
    print("EFFECT ON USER-FACING COUNTS")
    print("=" * 74)
    print(f"\n  {'chain':<13}{'real now':>10}{'real dedup':>12}{'change':>10}")
    print("  " + "-" * 45)
    for chain, (_, _, groups) in sorted(summary.items(), key=lambda kv: -kv[1][0]):
        real_now = sum(1 for p in by_chain[chain] if p.get("state") == "real")
        real_dedup = sum(
            1 for v in groups.values() if any(p.get("state") == "real" for p in v)
        )
        delta = f"-{real_now - real_dedup}" if real_now else "0"
        print(f"  {chain:<13}{real_now:>10}{real_dedup:>12}{delta:>10}")

    print("\n  'real now' is what Home counts today; 'real dedup' counts each")
    print("  shelf item once. The gap is how much the promotion figures and")
    print("  the Titans denominators are inflated.")

    # Evidence to read.
    print("\n" + "=" * 74)
    print(f"WORST {args.worst} DUPLICATED NAMES — check these are truly one item")
    print("=" * 74 + "\n")

    allg = []
    for chain, (_, _, groups) in summary.items():
        for k, v in groups.items():
            if len(v) > 1:
                allg.append((len(v), chain, k, v))
    allg.sort(key=lambda t: -t[0])

    for n, chain, _, items in allg[: args.worst]:
        prices = {round(p.get("price") or 0, 2) for p in items}
        tag = "identical price" if len(prices) == 1 else f"{len(prices)} distinct prices"
        print(f"  {chain} — {n} codes, {tag}")
        for p in sorted(items, key=lambda x: x.get("price") or 0)[:5]:
            print(f"      {p.get('price'):>7.2f}  {p['name'][:62]}")
        if n > 5:
            print(f"      … and {n - 5} more")
        print()


if __name__ == "__main__":
    main()
