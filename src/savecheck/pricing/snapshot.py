"""Product snapshot computation — single source of truth.

Given a `ProductOffering` (one product as sold at one chain, with 90-day
observation history), compute the current-day snapshot used by BOTH:

  * public/products.js  — the product-first index that drives Home + search
  * public/brochures.js — the per-chain promotional summaries

Previously both scripts had their own slightly-different snapshot logic,
which caused the "state='real' in products.js" count to disagree with the
"verdict='green' in brochures.js" count for the same chain. This module
guarantees they match.

The verdict math itself lives in `verdict.py` (`evaluate_series`); this
module handles the input preparation: current-day fallback, is_promo
detection, retail lookup, and result formatting.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from .aggregates import PricePoint
from .verdict import Verdict, evaluate_series


STATE_FROM_VERDICT = {
    Verdict.REAL: "real",
    Verdict.COSMETIC: "cosmetic",
    Verdict.FAKE: "fake",
    Verdict.UNKNOWN: "unverified",
}


# Reason codes are stable machine-readable tags for the verdict.
# Kept identical to the original gen_demo_data.py values so existing
# products.js consumers don't observe a schema change.
def _reason_code(res: Any) -> str:
    v = res.verdict
    if v == Verdict.REAL:
        return "real"
    if v == Verdict.COSMETIC:
        return "cosmetic"
    if v == Verdict.UNKNOWN:
        return "unknown"
    # FAKE — distinguish "priced at or above recent low" from "priced below it"
    s = res.stats
    cheaper = s.min_30_prior is None or (
        s.current_price is not None and s.current_price < s.min_30_prior
    )
    return "fake_equal" if cheaper else "fake_not_below"


@dataclass
class ProductOffering:
    """One product as sold at one specific chain, over the observed window."""
    key: str
    name: str
    code: str | None
    kzp_category: str | None
    chain: str
    points: list[PricePoint] = field(default_factory=list)
    retail_prices: dict[date, Decimal] = field(default_factory=dict)


def compute_snapshot(
    off: ProductOffering,
    ref: date,
    fallback_days: int = 3,
) -> dict | None:
    """Current-day snapshot for one offering.

    Returns None if the offering has no observation within `fallback_days`
    of `ref` (offering is considered stale / not currently available).

    The snapshot dict has keys:
        id, name, code, chain, price, retail, claimed_pct, is_promo,
        kzp_category, observed_on, state, reason_code,
        omnibus_pct?, min_30_prior?, median_90?

    The `state` field maps to the four traffic-light states used everywhere
    in the UI: real / cosmetic / fake / unverified / regular.

    Regular means "not marketed as a promo today" — the item is being sold
    at whatever the chain considers its normal price. No verdict is run
    because the anti-fake-promo logic only applies to items advertised as
    a discount.
    """
    if not off.points:
        return None

    pts = sorted(off.points, key=lambda p: p.day)

    # Prefer observations from the reference day itself; if the chain didn't
    # publish for `ref`, fall back to the most recent observation within
    # `fallback_days`. Beyond that the data is stale.
    current_pts = [p for p in pts if p.day == ref]
    if not current_pts:
        cutoff = ref - timedelta(days=fallback_days)
        recent = [p for p in pts if p.day >= cutoff]
        if not recent:
            return None
        current_pts = [max(recent, key=lambda p: p.day)]

    current = min(current_pts, key=lambda p: p.price)
    is_promo_today = any(p.is_promo for p in current_pts)

    # Retail on the current day if available, else the latest known retail.
    retail_today: float | None = None
    for cp in sorted(current_pts, key=lambda p: p.day, reverse=True):
        r = off.retail_prices.get(cp.day)
        if r is not None:
            retail_today = float(r)
            break
    if retail_today is None and off.retail_prices:
        latest = max(off.retail_prices.keys())
        retail_today = float(off.retail_prices[latest])

    claimed_pct: int | None = None
    if retail_today is not None and retail_today > 0 and retail_today > float(current.price):
        claimed_pct = round((retail_today - float(current.price)) / retail_today * 100)

    snap: dict = {
        "id": off.key,
        "name": off.name,
        "code": off.code,
        "chain": off.chain,
        "price": float(current.price),
        "retail": retail_today,
        "claimed_pct": claimed_pct,
        "is_promo": is_promo_today,
        "kzp_category": off.kzp_category,
        "observed_on": current.day.isoformat(),
    }

    # Verdict only meaningful when the item is being marketed as a promo.
    # Otherwise it's a "regular" price and no anti-fake-promo test applies.
    if is_promo_today:
        if len(pts) >= 3:
            res = evaluate_series(pts, ref, is_promo=True)
            snap["state"] = STATE_FROM_VERDICT[res.verdict]
            snap["reason_code"] = _reason_code(res)
            if res.discount_vs_median is not None:
                snap["omnibus_pct"] = round(float(res.discount_vs_median) * 100)
            if res.stats.min_30_prior is not None:
                snap["min_30_prior"] = float(res.stats.min_30_prior)
            if res.stats.median_90 is not None:
                snap["median_90"] = float(res.stats.median_90)
        else:
            snap["state"] = "unverified"
            snap["reason_code"] = "insufficient_history"
    else:
        snap["state"] = "regular"
        snap["reason_code"] = "not_promo"

    return snap
