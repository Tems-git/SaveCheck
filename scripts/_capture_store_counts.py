#!/usr/bin/env python3
"""One-off: capture how many stores back each price, and report the spread.

    python scripts/_capture_store_counts.py --dry
    python scripts/_capture_store_counts.py

THE GAP
    KZP publishes one row per (product, store, day). parse_chain_csv
    already returns `store` and `region` on every row — and
    load_all_products discards both:

        day_all_obs[k].append((
            row.price, row.is_promo, row.retail_price,
            row.product_name, row.product_code, row.category,
        ))

    One representative observation per (product, day) then stands in for
    the whole chain. A clearance price in three outlets of two hundred
    is displayed as "Kaufland: 0.08 €" with nothing to qualify it.

    The outlier filter exists for this, but only fires at
    OUTLIER_MIN_OBS (5) observations with a 60% gap to the median.
    Under five, plain min() wins. The three items at the top of the home
    screen right now — bevola soaps, 0.08, −84% — look exactly like that
    case.

WHAT THIS CHANGES
    Nothing that affects output values. It records two integers per
    offering and prints a distribution:

        stores        outlets reporting this product on the observed day
        chain_stores  outlets that chain reported at all that day

    Price selection, the outlier thresholds and every verdict stay as
    they are. The point is to see the shape of the problem before
    deciding what to do about it.

WHAT IS OUT OF SCOPE
    Choosing a city or a nearby store. products.js is 1.8 MB holding one
    observation per product per chain; per-outlet prices multiply that by
    the number of outlets. That needs an API, not a bigger JSON file.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GEN = ROOT / "scripts" / "gen_demo_data.py"
SNAP = ROOT / "src" / "savecheck" / "pricing" / "snapshot.py"
DRY = "--dry" in sys.argv

EDITS: list[tuple[Path, str, str, str]] = []


def edit(path: Path, label: str, old: str, new: str) -> None:
    EDITS.append((path, label, old, new))


# ── 1. ProductOffering gains a per-day store count ───────────────────
edit(
    SNAP, "ProductOffering.store_counts",
    """    points: list[PricePoint] = field(default_factory=list)
    retail_prices: dict[date, Decimal] = field(default_factory=dict)""",
    """    points: list[PricePoint] = field(default_factory=list)
    retail_prices: dict[date, Decimal] = field(default_factory=dict)
    # How many distinct outlets reported this product on a given day. KZP
    # publishes one row per (product, store, day), and the pipeline reduces
    # that to one representative price — this keeps the sample size so a
    # single outlet's clearance is distinguishable from a chain-wide cut.
    store_counts: dict[date, int] = field(default_factory=dict)""",
)

# ── 2. module-level home for the per-chain denominators ──────────────
edit(
    GEN, "CHAIN_STORE_TOTALS",
    'OUTLIER_MIN_OBS = 5              # need this many stores selling the item today',
    """# Distinct outlets each chain reported on a given day — the denominator for
# "found in 3 of 214 stores". Populated as a side effect of
# load_all_products; a return-value change would break gen_brochures.py,
# which calls it with the same signature.
CHAIN_STORE_TOTALS: dict[tuple[str, "date"], int] = {}

OUTLIER_MIN_OBS = 5              # need this many stores selling the item today""",
)

# ── 3. count outlets while reading the CSV ───────────────────────────
edit(
    GEN, "collect store ids in the first pass",
    """                for row in parse_chain_csv(csv_bytes, chain_raw, d):
                    if row.price <= 0:
                        continue
                    rows_seen += 1
                    k = product_key(row.product_code, row.product_name)
                    day_all_obs[k].append((
                        row.price, row.is_promo, row.retail_price,
                        row.product_name, row.product_code, row.category,
                    ))""",
    """                # Store identity is region + outlet name; neither is unique on
                # its own (chains reuse outlet names across towns).
                day_stores: dict[str, set[str]] = defaultdict(set)
                chain_stores_today: set[str] = set()

                for row in parse_chain_csv(csv_bytes, chain_raw, d):
                    if row.price <= 0:
                        continue
                    rows_seen += 1
                    k = product_key(row.product_code, row.product_name)
                    store_id = f"{row.region or ''}|{row.store or ''}"
                    day_stores[k].add(store_id)
                    chain_stores_today.add(store_id)
                    day_all_obs[k].append((
                        row.price, row.is_promo, row.retail_price,
                        row.product_name, row.product_code, row.category,
                    ))

                if chain_stores_today:
                    CHAIN_STORE_TOTALS[(display, d)] = len(chain_stores_today)""",
)

# ── 4. carry the count onto the offering ─────────────────────────────
edit(
    GEN, "record store_counts on the offering",
    """                    off.points.append(PricePoint(day=d, price=price, is_promo=is_promo))""",
    """                    off.points.append(PricePoint(day=d, price=price, is_promo=is_promo))
                    off.store_counts[d] = len(day_stores.get(k, ()))""",
)

# ── 5. surface both numbers in the snapshot ──────────────────────────
edit(
    GEN, "expose stores / chain_stores in products.js",
    """    tags = [pid for pid, pat in BASKET.items() if pat.search(off.name)]
    if tags:
        snap["category_tags"] = tags

    return snap""",
    """    tags = [pid for pid, pat in BASKET.items() if pat.search(off.name)]
    if tags:
        snap["category_tags"] = tags

    # Sample size behind the displayed price. Keyed off observed_on rather
    # than REF, because compute_snapshot falls back up to three days when a
    # chain did not publish.
    obs_day = date.fromisoformat(snap["observed_on"])
    n_stores = off.store_counts.get(obs_day)
    if n_stores:
        snap["stores"] = n_stores
        total = CHAIN_STORE_TOTALS.get((off.chain, obs_day))
        if total:
            snap["chain_stores"] = total

    return snap""",
)

# ── 6. the report this whole patch exists for ────────────────────────
edit(
    GEN, "store coverage report",
    """# ---------------------------------------------------------------------------
# Product-first history (new — drives docs/products-history.js)
# ---------------------------------------------------------------------------""",
    '''def report_store_coverage(products: list[dict]) -> None:
    """How thin is the evidence behind the prices we advertise?

    A price backed by three outlets out of two hundred is a local
    clearance, not a chain price, and it currently reaches the home
    screen looking identical to one backed by all of them. This prints
    the distribution so that can be judged rather than assumed.
    """
    real = [p for p in products if p.get("state") == "real" and p.get("stores")]
    if not real:
        print("  (no real promotions carry a store count)")
        return

    buckets = [(1, 1), (2, 2), (3, 4), (5, 9), (10, 24), (25, 10 ** 9)]
    labels = ["1", "2", "3-4", "5-9", "10-24", "25+"]
    counts = [0] * len(buckets)
    for p in real:
        for i, (lo, hi) in enumerate(buckets):
            if lo <= p["stores"] <= hi:
                counts[i] += 1
                break

    print(f"  {len(real)} real promotions with a store count\\n")
    print(f"    {'outlets':<10}{'promos':>8}{'share':>9}")
    print("    " + "-" * 27)
    for label, n in zip(labels, counts):
        print(f"    {label:<10}{n:>8}{100 * n / len(real):>8.1f}%")

    # Share of the chain's own footprint is the more honest denominator: 5
    # outlets is broad for a chain with 12 and negligible for one with 300.
    with_total = [p for p in real if p.get("chain_stores")]
    if with_total:
        thin = [p for p in with_total if p["stores"] / p["chain_stores"] < 0.10]
        print(f"\\n    under 10% of the chain's outlets: {len(thin)} of {len(with_total)}"
              f"  ({100 * len(thin) / len(with_total):.1f}%)")
        worst = sorted(with_total, key=lambda p: p["stores"] / p["chain_stores"])[:8]
        print("\\n    thinnest evidence among advertised real promotions:")
        for p in worst:
            print(f"      {p['chain']:<12} {p['price']:>7.2f}  "
                  f"{p['stores']:>4}/{p['chain_stores']:<5} {p['name'][:44]}")


# ---------------------------------------------------------------------------
# Product-first history (new — drives docs/products-history.js)
# ---------------------------------------------------------------------------''',
)

edit(
    GEN, "call the report from main",
    '''    print("\\nBattle of the Titans — chain scorecard (last 30 days):")''',
    '''    print("\\nStore coverage behind advertised real promotions:")
    report_store_coverage(products_dataset)

    print("\\nBattle of the Titans — chain scorecard (last 30 days):")''',
)


def main() -> None:
    for p in (GEN, SNAP):
        if not p.exists():
            raise SystemExit(f"ABORT: {p} not found — run from the repo root.")

    print("Capture store counts" + ("  (DRY RUN)" if DRY else ""))
    print()

    texts = {p: p.read_text(encoding="utf-8") for p in (GEN, SNAP)}
    misses = 0

    for path, label, old, new in EDITS:
        t = texts[path]
        n = t.count(old)
        if n == 1:
            texts[path] = t.replace(old, new)
            print(f"  OK      {label}")
        elif n == 0 and new.strip().splitlines()[0][:40] in t:
            print(f"  --      {label} (already applied)")
        else:
            print(f"  MISS    {label}  (matched {n}, expected 1)")
            misses += 1

    if misses:
        raise SystemExit(
            f"\nABORT: {misses} anchor(s) did not match — nothing written.\n"
            "       These edits interlock, so a partial apply would be worse\n"
            "       than none."
        )

    if DRY:
        print("\nDry run — nothing written.")
        return

    for path, t in texts.items():
        path.write_text(t, encoding="utf-8")

    print("\nDone. Nothing about price selection or verdicts changed.")
    print("Review:  git diff")
    print("\nThe numbers arrive with the next cron run, or run the generator")
    print("by hand if you have ZIPs cached locally.")


if __name__ == "__main__":
    main()
