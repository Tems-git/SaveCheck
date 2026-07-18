"""Generate per-chain promotional brochure summaries with Omnibus verdicts.

Extracts promo products for each chain from the KZP feed. Chains that didn't
publish today fall back to the most recent day they DID publish (up to 3 days
back). Runs the Omnibus verdict on known basket items against their OWN
90-day variant history (from the product-first index), then writes
public/brochures.js.

    python scripts/gen_brochures.py [--zip-dir /tmp/kzp_zips]
"""

from __future__ import annotations

import json
import sys
import zipfile
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from savecheck.ingest.kolkostruva import chain_name_from_filename, parse_chain_csv  # noqa: E402
from savecheck.pricing import Verdict, evaluate_series  # noqa: E402

# Reuse basket + chain config + product-first loader from gen_demo_data.
sys.path.insert(0, str(ROOT / "scripts"))
from gen_demo_data import (  # noqa: E402
    BASKET,
    CHAIN_DISPLAY,
    MAIN_CHAINS,
    PRIMARY_ORDER,
    ProductOffering,
    load_all_products,
    product_key,
)

import argparse

MAX_ITEMS_PER_CHAIN = 300         # cap; enough for chains that promo everything (e.g. Kaufland)
MAX_FALLBACK_DAYS = 3             # how far back to look for a chain that didn't publish today


def _claimed_pct(retail: Decimal | None, promo: Decimal) -> int | None:
    if retail and retail > promo and retail > 0:
        return round(float((retail - promo) / retail * 100))
    return None


def _collect_promos_from_zip(
    zip_path: Path,
    zip_date: date,
    only_chains: set[str],
    into: dict[str, dict[str, dict]],
) -> set[str]:
    """Scan one ZIP, populating ``into[chain][key]`` for chains in ``only_chains``.
    Returns the set of chains for which promos were actually found in this ZIP."""
    found: set[str] = set()

    with zipfile.ZipFile(zip_path) as zf:
        for entry in zf.namelist():
            if not entry.lower().endswith(".csv"):
                continue
            chain_raw = chain_name_from_filename(entry)
            if chain_raw not in MAIN_CHAINS:
                continue
            display = CHAIN_DISPLAY[chain_raw]
            if display not in only_chains:
                continue

            with zf.open(entry) as raw:
                csv_bytes = raw.read()

            chain_bucket = into[display]
            for row in parse_chain_csv(csv_bytes, chain_raw, zip_date):
                if not row.is_promo or row.price <= 0:
                    continue
                key = row.product_code or row.product_name
                existing = chain_bucket.get(key)
                if existing is None or row.price < existing["price"]:
                    chain_bucket[key] = {
                        "name": row.product_name,
                        "price": row.price,
                        "retail": row.retail_price,
                        "category": row.category or "",
                        "code": row.product_code or "",
                    }
                    found.add(display)

    return found


def extract_chain_promos(
    zips: list[Path],
    ref: date,
    offerings: dict[tuple[str, str], ProductOffering],
    max_fallback_days: int = MAX_FALLBACK_DAYS,
) -> dict[str, dict]:
    """Return ``{display_chain: {"from_date": iso, "items": [...]}}``.

    Walks ZIPs newest-to-oldest starting at ``ref``. For each chain not yet
    populated, picks its promos from the current ZIP. Stops when all chains
    are populated or when we're more than ``max_fallback_days`` days behind
    ``ref`` (older than that is stale — promos change weekly).

    Each item matching a basket category is verified against its OWN 90-day
    history (looked up in the product-first offerings index by product_key),
    not a category-wide blended series — so a pricier brand's discount isn't
    judged against a cheaper brand's typical price."""
    raw: dict[str, dict[str, dict]] = defaultdict(dict)
    from_dates: dict[str, str] = {}
    oldest_allowed = ref - timedelta(days=max_fallback_days)

    # Walk ZIPs newest first
    for zip_path in sorted(zips, reverse=True):
        try:
            zip_date = date.fromisoformat(zip_path.stem)
        except ValueError:
            continue
        if zip_date > ref or zip_date < oldest_allowed:
            continue

        missing = {c for c in PRIMARY_ORDER if c not in from_dates}
        if not missing:
            break

        found_here = _collect_promos_from_zip(zip_path, zip_date, missing, raw)
        for c in found_here:
            # Only record from_date the FIRST time we see a chain
            from_dates.setdefault(c, zip_date.isoformat())

    # Build the sorted, verdict-annotated output per chain
    out: dict[str, dict] = {}
    for c in PRIMARY_ORDER:
        if c not in from_dates:
            continue
        items = []
        for d in raw[c].values():
            promo_price: Decimal = d["price"]
            retail_price: Decimal | None = d["retail"]
            claimed = _claimed_pct(retail_price, promo_price)

            item: dict = {
                "name": d["name"],
                "price": float(promo_price),
                "retail": float(retail_price) if retail_price else None,
                "claimed_pct": claimed,
                "category": d["category"],
            }

            # Omnibus verdict against this item's OWN variant history.
            # Uses ref (not from_date[c]) for evaluate_series, since offerings
            # is a REF-anchored snapshot.
            for pid, pat in BASKET.items():
                if pat.search(d["name"]):
                    item["basket_id"] = pid
                    key = product_key(d["code"], d["name"])
                    off = offerings.get((key, c))
                    pts_for_variant = off.points if off else []
                    if len(pts_for_variant) >= 3:
                        pts = sorted(pts_for_variant, key=lambda p: p.day)
                        today_pts = [p for p in pts if p.day == ref]
                        is_promo_today = any(p.is_promo for p in today_pts)
                        res = evaluate_series(pts, ref, is_promo=is_promo_today)
                        s = res.stats
                        item["verdict"] = res.verdict.value
                        item["omnibus_pct"] = (
                            round(float(res.discount_vs_median) * 100)
                            if res.discount_vs_median is not None else None
                        )
                        item["min_30_prior"] = float(s.min_30_prior) if s.min_30_prior else None
                        item["median_90"] = float(s.median_90) if s.median_90 else None
                    # else: not enough history for THIS specific product → stays unverified
                    break

            # For non-basket items we still want the Omnibus verdict — evaluate
            # against the offering's own history via product_key lookup.
            if "verdict" not in item:
                key = product_key(d["code"], d["name"])
                off = offerings.get((key, c))
                pts_for_variant = off.points if off else []
                if len(pts_for_variant) >= 3:
                    pts = sorted(pts_for_variant, key=lambda p: p.day)
                    today_pts = [p for p in pts if p.day == ref]
                    is_promo_today = any(p.is_promo for p in today_pts)
                    res = evaluate_series(pts, ref, is_promo=is_promo_today)
                    s = res.stats
                    item["verdict"] = res.verdict.value
                    item["omnibus_pct"] = (
                        round(float(res.discount_vs_median) * 100)
                        if res.discount_vs_median is not None else None
                    )
                    item["min_30_prior"] = float(s.min_30_prior) if s.min_30_prior else None
                    item["median_90"] = float(s.median_90) if s.median_90 else None

            items.append(item)

        # Sort: basket items (mainstream products) first, then by REAL discount
        # (omnibus_pct = savings vs 90-day median), not the label claim. Items
        # without omnibus_pct (insufficient history) fall to the bottom.
        # Verdict is NOT part of the sort key — fake items with high omnibus_pct
        # (rare but possible) still get their spot; low-omnibus fakes fall
        # naturally below high-omnibus greens/yellows/reds.
        def _sort(it: dict) -> tuple:
            is_basket = 0 if "basket_id" in it else 1
            omnibus = it.get("omnibus_pct")
            has_omnibus = 0 if omnibus is not None else 1
            return (is_basket, has_omnibus, -(omnibus or 0))

        items.sort(key=_sort)
        out[c] = {
            "from_date": from_dates[c],
            "items": items[:MAX_ITEMS_PER_CHAIN],
        }

    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--zip-dir", default="/tmp/kzp_zips")
    args = parser.parse_args()

    zip_dir = Path(args.zip_dir)
    zips = sorted(zip_dir.glob("*.zip"))
    if not zips:
        raise FileNotFoundError(f"No ZIPs in {zip_dir}")

    latest_zip = zips[-1]
    ref = date.fromisoformat(latest_zip.stem)
    print(f"Reference date: {ref} (from {latest_zip.name})")

    print(f"Loading product-first index for Omnibus verdicts…")
    offerings = load_all_products(zip_dir)
    print(f"  → {len(offerings)} distinct (product, chain) offerings")

    print(f"Extracting promos (with up to {MAX_FALLBACK_DAYS}-day fallback per chain)…")
    chains_data = extract_chain_promos(zips, ref, offerings)

    # Week label: ref through the Sunday of ref's week
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
        if c in chains_data:
            info = chains_data[c]
            items = info["items"]
            n = len(items)
            basket_n = sum(1 for it in items if "basket_id" in it)
            fake_n = sum(1 for it in items if it.get("verdict") == "red")
            real_n = sum(1 for it in items if it.get("verdict") == "green")
            stale = " (from " + info["from_date"] + ")" if info["from_date"] != ref.isoformat() else ""
            print(f"  {c:<12} {n:>4} promos  (basket: {basket_n} → 🟢{real_n} 🔴{fake_n}){stale}")
        else:
            print(f"  {c:<12}    - no promos found in last {MAX_FALLBACK_DAYS} days")


if __name__ == "__main__":
    main()
