"""Generate per-chain promotional brochure summaries with Omnibus verdicts.

Uses the shared product-first index (from savecheck.pricing.compute_snapshot),
so the snapshot for each product is IDENTICAL to what gen_demo_data.py writes
into docs/products.js. This means:

  * Home's "Виж всички N реални промоции" count for a chain
  * The number of green items in that chain's brochure

come from the same underlying data with the same verdict logic — no more
"Home says 32 real Kaufland deals but brochure says 56 green".

Runs the Omnibus verdict on every offering, filters to items marked as
is_promo at REF (with the same 3-day fallback used everywhere), sorts by
real discount (omnibus_pct desc, with basket items first), caps to 500
per chain, and writes docs/brochures.js.

    python scripts/gen_brochures.py [--zip-dir /tmp/kzp_zips]
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from savecheck.pricing import compute_snapshot  # noqa: E402

# Reuse basket + chain config + product-first loader from gen_demo_data.
sys.path.insert(0, str(ROOT / "scripts"))
from gen_demo_data import (  # noqa: E402
    BASKET,
    PRIMARY_ORDER,
    load_all_products,
)


MAX_ITEMS_PER_CHAIN = 500         # cap; comfortably covers even Fantastico's ~450 items
MAX_FALLBACK_DAYS = 3


def build_brochures(
    offerings: dict,
    ref: date,
    fallback_days: int = MAX_FALLBACK_DAYS,
    min_obs_30d: int = 3,
) -> dict[str, dict]:
    """Return ``{display_chain: {"from_date": iso, "items": [...]}}``.

    Every offering runs through the shared `compute_snapshot`. We keep only
    the ones that are (a) currently on promo at REF (within fallback_days)
    and (b) present the data in the brochure schema — same fields as before,
    for UI backward compat, but derived from the shared snapshot.

    An offering must appear at least `min_obs_30d` times in the last 30 days
    to be included. This is the SAME filter products.js uses (see
    `build_products_dataset` in gen_demo_data.py) — it drops one-off items
    that appeared in a single brochure but aren't part of the regular
    assortment. Keeping the same filter here guarantees Home's real-count
    and the brochure's green-count match for every chain.

    `from_date` per chain = the OLDEST observed_on among that chain's kept
    items. When a chain didn't publish on REF the shared snapshot's fallback
    kicks in and observed_on will be REF - 1 or REF - 2. Picking the oldest
    gives an honest "as of" date for the brochure header.
    """
    per_chain: dict[str, list[dict]] = defaultdict(list)
    min_recent_day = ref - timedelta(days=30)

    for (_, chain), off in offerings.items():
        # Same "regular assortment" filter as products.js.
        recent = sum(1 for p in off.points if min_recent_day <= p.day <= ref)
        if recent < min_obs_30d:
            continue

        snap = compute_snapshot(off, ref, fallback_days=fallback_days)
        if snap is None:
            continue
        # Only items being marketed as a promo belong in a brochure.
        if not snap.get("is_promo"):
            continue

        item = _brochure_item(snap, off)
        per_chain[chain].append(item)

    out: dict[str, dict] = {}
    for chain in PRIMARY_ORDER:
        items = per_chain.get(chain)
        if not items:
            continue

        # Sort: basket items (mainstream products) first, then by REAL
        # discount (omnibus_pct = savings vs 90-day median), not the label
        # claim. Items without omnibus_pct (insufficient history) fall to
        # the bottom of their basket group. Verdict is NOT part of the
        # sort key — the ranking is by savings, so fakes with high
        # omnibus_pct (rare) still surface, and low-quality greens don't
        # get an unfair boost.
        def _sort_key(it: dict) -> tuple:
            is_basket = 0 if "basket_id" in it else 1
            omni = it.get("omnibus_pct")
            has_omni = 0 if omni is not None else 1
            return (is_basket, has_omni, -(omni or 0))

        items.sort(key=_sort_key)

        # `from_date`: oldest observed_on among kept items. If everything is
        # today it's just REF; if the chain didn't publish, it's the day it
        # last did.
        from_date = min(it["observed_on"] for it in items)

        out[chain] = {
            "from_date": from_date,
            "items": items[:MAX_ITEMS_PER_CHAIN],
            "total_before_cap": len(items),
        }

    return out


def _brochure_item(snap: dict, off) -> dict:
    """Convert a shared snapshot into the brochure item schema (same keys
    the UI already reads from docs/brochures.js)."""
    item: dict = {
        "name": snap["name"],
        "price": snap["price"],
        "retail": snap["retail"],
        "claimed_pct": snap["claimed_pct"],
        "category": off.kzp_category or "",
        "verdict": _state_to_verdict(snap.get("state")),
        "observed_on": snap["observed_on"],
    }
    if "omnibus_pct" in snap:
        item["omnibus_pct"] = snap["omnibus_pct"]
    if "min_30_prior" in snap:
        item["min_30_prior"] = snap["min_30_prior"]
    if "median_90" in snap:
        item["median_90"] = snap["median_90"]

    # BASKET tagging so mainstream basket items rank first in the brochure.
    for pid, pat in BASKET.items():
        if pat.search(snap["name"]):
            item["basket_id"] = pid
            break

    return item


def _state_to_verdict(state: str | None) -> str:
    """Map the shared snapshot `state` back to the brochure `verdict` field
    the UI expects. Same colour mapping as before."""
    return {
        "real": "green",
        "cosmetic": "yellow",
        "fake": "red",
        "unverified": "gray",
        "regular": "gray",  # shouldn't happen — regular items are filtered out
    }.get(state or "", "gray")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--zip-dir", default="/tmp/kzp_zips")
    args = parser.parse_args()

    zip_dir = Path(args.zip_dir)
    zips = sorted(zip_dir.glob("*.zip"))
    if not zips:
        raise FileNotFoundError(f"No ZIPs in {zip_dir}")

    latest_zip = zips[-1]
    ref = date.fromisoformat(latest_zip.stem)
    print(f"Reference date: {ref} (from {latest_zip.name})")

    print(f"Loading product-first index (shared with products.js)…")
    offerings = load_all_products(zip_dir)
    print(f"  → {len(offerings)} distinct (product, chain) offerings")

    print(f"Building brochures (via shared compute_snapshot)…")
    chains_data = build_brochures(offerings, ref)

    week_end = ref + timedelta(days=6 - ref.weekday())
    week_label = f"{ref.strftime('%-d.%-m')} – {week_end.strftime('%-d.%-m.%Y')}"

    payload = {
        "for_date": ref.isoformat(),
        "week_label": week_label,
        "chains": [
            {
                "chain": c,
                "from_date": chains_data[c]["from_date"],
                "is_stale": chains_data[c]["from_date"] != ref.isoformat(),
                "total_promos": len(chains_data[c]["items"]),
                "total_before_cap": chains_data[c]["total_before_cap"],
                "items": chains_data[c]["items"],
            }
            for c in PRIMARY_ORDER if c in chains_data
        ],
    }

    out = ROOT / "public" / "brochures.js"
    out.write_text(
        "window.SAVECHECK_BROCHURES = " + json.dumps(payload, ensure_ascii=False, indent=2) + ";\n",
        encoding="utf-8",
    )
    print(f"\nWrote {out}")
    for c in PRIMARY_ORDER:
        if c not in chains_data:
            print(f"  {c:<12}    - no promos found in last {MAX_FALLBACK_DAYS} days")
            continue
        info = chains_data[c]
        items = info["items"]
        n = len(items)
        total = info["total_before_cap"]
        basket_n = sum(1 for it in items if "basket_id" in it)
        red_n = sum(1 for it in items if it.get("verdict") == "red")
        green_n = sum(1 for it in items if it.get("verdict") == "green")
        stale = " (from " + info["from_date"] + ")" if info["from_date"] != ref.isoformat() else ""
        capped = f" (top {n} of {total})" if total > n else ""
        print(f"  {c:<12} {n:>4} promos{capped}  (basket: {basket_n} → 🟢{green_n} 🔴{red_n}){stale}")


if __name__ == "__main__":
    main()
