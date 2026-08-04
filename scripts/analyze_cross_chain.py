#!/usr/bin/env python3
"""How matchable are products across chains, really?

    python scripts/analyze_cross_chain.py
    python scripts/analyze_cross_chain.py --sample 30 --seed 7

Read-only. Touches nothing, writes nothing.

WHY THIS EXISTS
    Cross-chain comparison lives or dies on what counts as "the same
    product" in two different chains. KZP product codes are per-chain,
    and the names are supplier strings like

        ПЛЕШКА СВИНСКА БЕЗ КОСТ ПР-Д БЪЛГАРИЯ АЛДАГОТ

    A false pair here is much worse than a missing one: quoting two
    prices for products that are not comparable undermines the only
    thing this app is for. So measure before building.

READING THE OUTPUT
    Tier 1 is free — the pipeline already keys on product_code where a
    chain supplies one. If tier 1 alone covers a decent share, the MVP
    is an afternoon. If it is near zero, the feature needs real
    normalisation work and should be scoped accordingly.

    Watch the price-spread table as closely as the totals. A group whose
    dearest member costs several times its cheapest is usually a bad
    match, not a bargain — that row is a false-positive gauge.

    Then actually read the sample. Tier counts can look great while the
    pairs underneath are nonsense, and nothing but looking catches it.
"""

from __future__ import annotations

import argparse
import json
import random
import re
import statistics
import sys
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRODUCTS_JS = ROOT / "docs" / "products.js"


# ── loading ──────────────────────────────────────────────────────────

def load_products() -> list[dict]:
    if not PRODUCTS_JS.exists():
        raise SystemExit(
            f"ABORT: {PRODUCTS_JS} not found.\n"
            "       Run from the repo root; the file ships in the repo."
        )
    raw = PRODUCTS_JS.read_text(encoding="utf-8")
    start = raw.index("{")
    end = raw.rindex("}") + 1
    return json.loads(raw[start:end])["products"]


# ── normalisation ────────────────────────────────────────────────────
# Quantity is pulled out and canonicalised separately from the words.
# Two products are only ever candidates if their quantities agree —
# "кисело мляко 400 г" and "кисело мляко 2 кг" are not the same thing,
# however similar the words look.

_QTY_PATTERNS = [
    (re.compile(r"(\d+[.,]?\d*)\s*(?:кг|kg)\b", re.I), lambda v: f"{v * 1000:.0f}g"),
    (re.compile(r"(\d+[.,]?\d*)\s*(?:гр|г|g)\b", re.I),  lambda v: f"{v:.0f}g"),
    (re.compile(r"(\d+[.,]?\d*)\s*(?:л|l)\b", re.I),     lambda v: f"{v * 1000:.0f}ml"),
    (re.compile(r"(\d+[.,]?\d*)\s*(?:мл|ml)\b", re.I),   lambda v: f"{v:.0f}ml"),
    (re.compile(r"(\d+)\s*(?:бр\.?|броя|бр)\b", re.I),   lambda v: f"{v:.0f}pc"),
]

_PUNCT = re.compile(r"[^\w\s]", re.UNICODE)
_WS = re.compile(r"\s+")


def split_qty(name: str) -> tuple[str, str]:
    """Return (canonical quantity, name with the quantity removed)."""
    qty = ""
    rest = name
    for pat, fmt in _QTY_PATTERNS:
        m = pat.search(rest)
        if m:
            try:
                qty = fmt(float(m.group(1).replace(",", ".")))
            except ValueError:
                continue
            rest = rest[: m.start()] + " " + rest[m.end():]
            break
    return qty, rest


def norm_words(text: str) -> str:
    text = _PUNCT.sub(" ", text.lower())
    return _WS.sub(" ", text).strip()


def key_tier2(name: str) -> str:
    """Normalised words, order preserved, plus canonical quantity."""
    qty, rest = split_qty(name)
    return f"{norm_words(rest)}|{qty}"


def key_tier3(name: str) -> str:
    """Same, but word order ignored. Looser, and where the false
    positives start to show up."""
    qty, rest = split_qty(name)
    words = sorted(set(norm_words(rest).split()))
    return f"{' '.join(words)}|{qty}"


# ── analysis ─────────────────────────────────────────────────────────

def groups_by(products: list[dict], keyfn) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = defaultdict(list)
    for p in products:
        out[keyfn(p)].append(p)
    return out


def cross_chain_only(groups: dict[str, list[dict]]) -> dict[str, list[dict]]:
    """Keep groups spanning 2+ chains, one entry per chain (cheapest)."""
    kept = {}
    for k, items in groups.items():
        best: dict[str, dict] = {}
        for p in items:
            c = p["chain"]
            if c not in best or p["price"] < best[c]["price"]:
                best[c] = p
        if len(best) >= 2:
            kept[k] = list(best.values())
    return kept


def spread(items: list[dict]) -> float:
    prices = [p["price"] for p in items if p.get("price")]
    lo = min(prices)
    return max(prices) / lo if lo else 0.0


def report_tier(label: str, groups: dict, total_offerings: int) -> dict:
    covered = sum(len(v) for v in groups.values())
    pct = 100 * covered / total_offerings if total_offerings else 0
    print(f"  {label:<34} {len(groups):>5} groups   "
          f"{covered:>5} offerings ({pct:.1f}%)")
    return groups


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sample", type=int, default=20,
                    help="how many groups to print for eyeballing (default 20)")
    ap.add_argument("--seed", type=int, default=1, help="sample seed")
    args = ap.parse_args()

    products = load_products()
    total = len(products)

    print("=" * 72)
    print("CROSS-CHAIN MATCHABILITY")
    print("=" * 72)

    chains = Counter(p["chain"] for p in products)
    print(f"\n{total} offerings across {len(chains)} chains")
    for c, n in chains.most_common():
        print(f"    {c:<14} {n:>5}")

    key_kinds = Counter(p["id"].split(":", 1)[0] for p in products)
    print("\nProduct key source:")
    for kind, n in key_kinds.most_common():
        print(f"    {kind + '-based':<14} {n:>5}  ({100 * n / total:.1f}%)")
    if key_kinds.get("code", 0) == 0:
        print("    NOTE: no code-based keys at all — tier 1 cannot work.")

    print("\n" + "-" * 72)
    print("MATCH TIERS  (groups spanning 2+ chains)")
    print("-" * 72)

    t1 = report_tier("1. exact product key",
                     cross_chain_only(groups_by(products, lambda p: p["id"])), total)
    t2 = report_tier("2. normalised name + quantity",
                     cross_chain_only(groups_by(products, lambda p: key_tier2(p["name"]))), total)
    t3 = report_tier("3. token set + quantity (loose)",
                     cross_chain_only(groups_by(products, lambda p: key_tier3(p["name"]))), total)

    print("\n  Tier 1 is free — the pipeline already keys on product_code")
    print("  wherever a chain supplies one. Tiers 2 and 3 are the ones that")
    print("  cost work and carry false-positive risk.")

    # Which chain pairs actually become comparable.
    print("\n" + "-" * 72)
    print("CHAIN PAIRS COMPARABLE  (tier 2)")
    print("-" * 72)
    pairs = Counter()
    for items in t2.values():
        for a, b in combinations(sorted(p["chain"] for p in items), 2):
            pairs[(a, b)] += 1
    if pairs:
        for (a, b), n in pairs.most_common():
            print(f"    {a:<12} <-> {b:<12} {n:>5}")
    else:
        print("    none")

    # Spread doubles as a false-positive gauge.
    print("\n" + "-" * 72)
    print("PRICE SPREAD WITHIN MATCHED GROUPS  (tier 2)")
    print("-" * 72)
    ratios = [spread(v) for v in t2.values() if spread(v) > 0]
    if ratios:
        print(f"    median max/min      {statistics.median(ratios):.2f}x")
        for hi in (1.5, 2.0, 3.0):
            n = sum(1 for r in ratios if r > hi)
            print(f"    groups above {hi:>4.1f}x  {n:>5}  ({100 * n / len(ratios):.1f}%)")
        print("\n    A group whose dearest member costs several times its")
        print("    cheapest is more often a bad match than a real bargain.")
        print("    Treat the tail as a false-positive estimate, not savings.")
    else:
        print("    no matched groups to measure")

    # The part that actually decides it.
    print("\n" + "=" * 72)
    print(f"SAMPLE — {args.sample} random tier-2 groups. Read these.")
    print("=" * 72)
    print("Counts can look excellent while the pairs are junk. This is the")
    print("only check that catches it.\n")

    keys = sorted(t2.keys())
    if not keys:
        print("  nothing matched — tier 2 produced no cross-chain groups")
        return
    random.seed(args.seed)
    for k in random.sample(keys, min(args.sample, len(keys))):
        items = sorted(t2[k], key=lambda p: p["price"])
        r = spread(items)
        flag = "   <-- wide spread, check this one" if r > 2 else ""
        print(f"  [{r:.2f}x]{flag}")
        for p in items:
            print(f"      {p['chain']:<12} {p['price']:>7.2f}  {p['name'][:58]}")
        print()


if __name__ == "__main__":
    main()
