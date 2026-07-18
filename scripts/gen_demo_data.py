"""Generate the demo dataset for the web preview from REAL KZP price data.

Reads the daily ZIP exports from a local cache directory and produces:
  * ``docs/products.js`` — product-first snapshot: every offering (product
    at a chain) observed at least 3 times in the last 30 days, with current
    price, Omnibus verdict when the item is on promo, KZP category and
    matching BASKET tags. This is the dataset the search / home feed / cart
    reads from.
  * ``docs/products-history.js`` — per-product 90-day price series for
    every offering in products.js, in a compact ``[day_offset, price,
    is_promo]`` triplet form. Loaded lazily by the UI when the user opens
    a product detail view.
  * ``docs/data.js`` — legacy 22-category snapshot, produced for backward
    compatibility with the current Products tab (category chips + charts).
    The category series is reconstructed from the product-first index by
    picking the cheapest matching product per day per chain — same behaviour
    as before, just derived from the new model.
  * chain scorecard ("Битката на титаните") over the last 30 days.

    python scripts/gen_demo_data.py [--zip-dir /tmp/kzp_zips]

Output is BGN-denominated; the website applies FX conversion at render time.
"""

from __future__ import annotations

import argparse
import io
import json
import re
import sys
import zipfile
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from savecheck.ingest.kolkostruva import chain_name_from_filename, parse_chain_csv  # noqa: E402
from savecheck.pricing import (  # noqa: E402
    PricePoint,
    ProductOffering,
    STATE_FROM_VERDICT,
    Verdict,
    build_chart,
    compute_snapshot,
    evaluate_series,
)
from savecheck.pricing.aggregates import compute_stats  # noqa: E402
from savecheck.shopping import (  # noqa: E402
    Staple,
    build_shopping_list,
    merge_inventory,
    to_inventory_item,
)

# ---------------------------------------------------------------------------
# Chain mapping: КЗП chain name (after chain_name_from_filename) → display label
# ---------------------------------------------------------------------------
CHAIN_DISPLAY: dict[str, str] = {
    "Лидл България":    "Lidl",
    "Кауфланд България": "Kaufland",
    "Билла":            "Billa",
    "ФАНТАСТИКО":       "Fantastico",
    "T Market":         "T Market",
}
MAIN_CHAINS = set(CHAIN_DISPLAY)
PRIMARY_ORDER = ["Lidl", "Kaufland", "Billa", "Fantastico", "T Market"]

# ---------------------------------------------------------------------------
# BASKET: 22 curated product categories used as *tags* on top of the
# product-first index (a product can match 0..N of these). Also drives the
# legacy category-level Products tab until Slice 2 replaces it.
# ---------------------------------------------------------------------------
BASKET: dict[str, re.Pattern] = {
    "milk":   re.compile(r"прясно мляко.{0,10}(1|1[,.]0)\s*л", re.IGNORECASE),
    "oil":    re.compile(r"слънчогледово\s*(олио|масло).{0,8}(1|1[,.]0)\s*л", re.IGNORECASE),
    "cheese": re.compile(r"кашкавал.{0,30}4[0-9]{2}", re.IGNORECASE),
    "butter": re.compile(r"краве\s*масло.{0,20}(82|250|125)", re.IGNORECASE),
    "sugar":  re.compile(r"\bзахар\b.{0,10}1\s*кг|1\s*кг\s*захар", re.IGNORECASE),
    "flour":  re.compile(r"брашно.{0,25}(тип\s*500|бял|пшен).{0,25}1\s*кг|1\s*кг.{0,10}брашно", re.IGNORECASE),
    "rice":   re.compile(r"\bориз\b(?!.*пюре).{0,20}(1\s*кг|среднозърн|басмати|ризон)", re.IGNORECASE),
    "eggs":   re.compile(r"\bяйца\b.{0,10}10\s*бр|10\s*бр.{0,10}\bяйца\b", re.IGNORECASE),
    "coffee": re.compile(r"(мляно|смляно)\s*кафе", re.IGNORECASE),
    "bread":  re.compile(r"\bхляб\b(?!.*(баниц|тутманик|кашкавалк|кор[ии]|тостер))", re.IGNORECASE),
    "yogurt":   re.compile(r'кисело\s*мляко\b.{0,20}(3[.,]6|4[.,]0?|2[.,]9)\s*%', re.IGNORECASE),
    "feta":     re.compile(r'\bсирене\b.{0,30}(краве|бяло|саламура|сал\.)', re.IGNORECASE),
    "chicken":  re.compile(r'пилешко\s*(бутче|филе|гърди)', re.IGNORECASE),
    "tomatoes": re.compile(r'\bдомати\b.{0,20}(на\s*)?кг', re.IGNORECASE),
    "bananas":  re.compile(r'\bбанани\b.{0,10}(кг|на\s*кг)', re.IGNORECASE),
    "pasta":    re.compile(r'(макарон|спагет).{0,25}(500|400|250)\s*г', re.IGNORECASE),
    "water":    re.compile(r'(минерална|изворна)\s*вода.{0,15}1[,.]5\s*л', re.IGNORECASE),
    "potato":   re.compile(r'\bкартоф.{0,12}(четкани|мити|пресни|бял).{0,10}кг|\bкартоф.{0,5}(кг\.?\s*$|на\s*кг)', re.IGNORECASE),
    "onion":    re.compile(r'\bлук\b.{0,8}(жълт|червен|на\s*кг)|лук\s+на\s*кг', re.IGNORECASE),
    "salt":     re.compile(r'(трапезна|готварска|йодирана).{0,10}сол|сол.{0,10}(1\s*кг|500\s*г)', re.IGNORECASE),
    "apple":    re.compile(r'\bябълки\b.{0,10}(кг|на\s*кг)', re.IGNORECASE),
    "cucumber": re.compile(r'\bкраставиц.{0,10}(кг|на\s*кг)', re.IGNORECASE),
}

UNIT_INFO: dict[str, tuple[str, Decimal]] = {
    "milk":   ("l",   Decimal("1")),
    "oil":    ("l",   Decimal("1")),
    "cheese": ("kg",  Decimal("0.4")),
    "butter": ("kg",  Decimal("0.25")),
    "sugar":  ("kg",  Decimal("1")),
    "flour":  ("kg",  Decimal("1")),
    "rice":   ("kg",  Decimal("1")),
    "eggs":   ("pcs", Decimal("10")),
    "coffee": ("kg",  Decimal("0.25")),
    "bread":  ("kg",  Decimal("0.7")),
    "yogurt":   ("kg",  Decimal("0.4")),
    "feta":     ("kg",  Decimal("0.25")),
    "chicken":  ("kg",  Decimal("1")),
    "tomatoes": ("kg",  Decimal("1")),
    "bananas":  ("kg",  Decimal("1")),
    "pasta":    ("kg",  Decimal("0.4")),
    "water":    ("l",   Decimal("1.5")),
    "potato":   ("kg",  Decimal("1")),
    "onion":    ("kg",  Decimal("1")),
    "salt":     ("kg",  Decimal("1")),
    "apple":    ("kg",  Decimal("1")),
    "cucumber": ("kg",  Decimal("1")),
}

REF: date = date(2026, 6, 13)  # overridden in main() from latest ZIP


# ---------------------------------------------------------------------------
# Product-first data model
# ---------------------------------------------------------------------------

_WHITESPACE_RE = re.compile(r"\s+")
_TRAILING_PUNCT_RE = re.compile(r"[.,;:!\-\s]+$")


def normalize_name(name: str) -> str:
    """Lowercase + collapse whitespace + strip trailing punctuation. Used as
    the fallback dedup key when a chain doesn't supply product_code.

    Conservative on purpose — same 15-word promo header written with an extra
    space between "400" and "г" would otherwise be treated as two products.
    We do NOT fold diacritics or normalize units yet: risk of false merges
    outweighs the benefit at this stage."""
    if not name:
        return ""
    n = name.lower().strip()
    n = _WHITESPACE_RE.sub(" ", n)
    n = _TRAILING_PUNCT_RE.sub("", n)
    return n


def product_key(code: str | None, name: str) -> str:
    """Stable id for a product. Prefers product_code when the chain provides
    one; falls back to a normalised form of the display name.

    The prefix ("code:" / "name:") makes the source of the key explicit and
    guarantees two products with the same numeric code and the same
    normalised name can't collide across chains that use different code
    schemes."""
    if code and code.strip():
        return f"code:{code.strip()}"
    return f"name:{normalize_name(name)}"


# ProductOffering is now imported from savecheck.pricing (shared with brochures).


def load_all_products(zip_dir: Path) -> dict[tuple[str, str], ProductOffering]:
    """Load every product observed in the KZP feed, keyed by
    ``(product_key, chain)``. No BASKET filter applied here — the 22
    categories are treated as tags at the presentation layer.
    """
    offerings: dict[tuple[str, str], ProductOffering] = {}

    zips = sorted(zip_dir.glob("*.zip"))
    if not zips:
        raise FileNotFoundError(f"No ZIP files found in {zip_dir}")

    for zip_path in zips:
        try:
            d = date.fromisoformat(zip_path.stem)
        except ValueError:
            continue

        print(f"  {zip_path.name}…", end="", flush=True)
        rows_seen = 0
        offerings_new = 0

        with zipfile.ZipFile(zip_path) as zf:
            for entry in zf.namelist():
                if not entry.lower().endswith(".csv"):
                    continue
                chain_raw = chain_name_from_filename(entry)
                if chain_raw not in MAIN_CHAINS:
                    continue
                display = CHAIN_DISPLAY[chain_raw]

                with zf.open(entry) as raw:
                    csv_bytes = raw.read()

                # First pass: pick the cheapest observation per (key, day).
                # A single CSV can list the same product multiple times (per
                # store); we want ONE price per chain per day.
                day_best: dict[str, tuple[Decimal, bool, Decimal | None, str, str | None, str | None]] = {}
                for row in parse_chain_csv(csv_bytes, chain_raw, d):
                    if row.price <= 0:
                        continue
                    rows_seen += 1
                    k = product_key(row.product_code, row.product_name)
                    existing = day_best.get(k)
                    if existing is None or row.price < existing[0]:
                        day_best[k] = (
                            row.price, row.is_promo, row.retail_price,
                            row.product_name, row.product_code, row.category,
                        )

                # Second pass: fold today's observations into the index.
                for k, (price, is_promo, retail, name, code, category) in day_best.items():
                    off_key = (k, display)
                    off = offerings.get(off_key)
                    if off is None:
                        off = ProductOffering(
                            key=k, name=name, code=code, kzp_category=category,
                            chain=display,
                        )
                        offerings[off_key] = off
                        offerings_new += 1
                    off.points.append(PricePoint(day=d, price=price, is_promo=is_promo))
                    if retail is not None:
                        off.retail_prices[d] = retail
                    # Refresh display metadata (chains sometimes fix typos or
                    # add detail over time; keep the latest).
                    off.name = name
                    if category:
                        off.kzp_category = category

        print(f" rows={rows_seen} new_offerings={offerings_new}")

    return offerings


# ---------------------------------------------------------------------------
# Backward-compat bridge: rebuild the old category-level series from the
# product-first index, so build_entry / build_chain_scorecard keep working.
# ---------------------------------------------------------------------------

def build_legacy_category_series(
    offerings: dict[tuple[str, str], ProductOffering],
) -> dict[str, dict[str, list[PricePoint]]]:
    """For each BASKET category and chain, pick the cheapest observation per
    day across all products matching the category's regex — same behaviour as
    the old load_all_zips (category = "cheapest match today")."""
    # {pid: {chain: {day: PricePoint}}}
    tmp: dict[str, dict[str, dict[date, PricePoint]]] = {
        pid: defaultdict(dict) for pid in BASKET
    }

    for (_, chain), off in offerings.items():
        for pid, pat in BASKET.items():
            if not pat.search(off.name):
                continue
            bucket = tmp[pid][chain]
            for pt in off.points:
                cur = bucket.get(pt.day)
                if cur is None or pt.price < cur.price:
                    bucket[pt.day] = pt

    return {
        pid: {chain: sorted(pts.values(), key=lambda p: p.day) for chain, pts in chains.items()}
        for pid, chains in tmp.items()
    }


# ---------------------------------------------------------------------------
# Legacy 22-category snapshot (drives current Products tab — docs/data.js)
# ---------------------------------------------------------------------------

def _reason_code(result, stats) -> str:
    if result.verdict is Verdict.REAL:
        return "real"
    if result.verdict is Verdict.COSMETIC:
        return "cosmetic"
    if result.verdict is Verdict.UNKNOWN:
        return "unknown"
    cheaper = stats.min_30_prior is None or (
        stats.current_price is not None and stats.current_price < stats.min_30_prior
    )
    return "fake_equal" if cheaper else "fake_not_below"


def _recent_day_at(chart_series, value) -> str | None:
    if value is None:
        return None
    found = None
    for p in chart_series:
        if p.price == value:
            found = p.day
    return found.isoformat() if found else None


def _compute_chain_stats(pts: list[PricePoint]) -> dict | None:
    """Full Omnibus stats/chart for one product at one specific chain."""
    if len(pts) < 3:
        return None
    pts = sorted(pts, key=lambda p: p.day)
    f = lambda v: float(v) if v is not None else None  # noqa: E731

    current_pts = [p for p in pts if p.day == REF]
    if not current_pts:
        recent = [p for p in pts if p.day >= REF - timedelta(days=3)]
        current_pts = [max(recent, key=lambda p: p.day)] if recent else []
    is_promo_today = any(p.is_promo for p in current_pts)
    result = evaluate_series(pts, REF, is_promo=is_promo_today)
    s = result.stats
    if s.current_price is None:
        return None
    chart = build_chart(pts, REF)
    disc = result.discount_vs_median

    return {
        "is_promo": is_promo_today,
        "verdict": {
            Verdict.REAL: "green", Verdict.COSMETIC: "yellow",
            Verdict.FAKE: "red",  Verdict.UNKNOWN: "gray",
        }[result.verdict],
        "reason_code": _reason_code(result, s),
        "discount_pct": round(float(disc) * 100) if disc is not None else None,
        "current_price": f(s.current_price),
        "median_90": f(s.median_90),
        "min_90": f(s.min_90),
        "max_90": f(s.max_90),
        "min_30_prior": f(s.min_30_prior),
        "lowest_day": _recent_day_at(chart.series, s.min_90),
        "highest_day": _recent_day_at(chart.series, s.max_90),
        "series": [{"day": p.day.isoformat(), "price": float(p.price)} for p in chart.series],
    }


def build_entry(pid: str, chain_series: dict[str, list[PricePoint]]) -> dict | None:
    unit_kind, size_base = UNIT_INFO[pid]

    by_chain: dict[str, dict] = {}
    for c in PRIMARY_ORDER:
        stats = _compute_chain_stats(chain_series.get(c, []))
        if stats:
            stats["current_unit_price"] = round(stats["current_price"] / float(size_base), 4)
            by_chain[c] = stats

    if not by_chain:
        print(f"  WARNING: no data for {pid}")
        return None

    best_chain = min(by_chain, key=lambda c: by_chain[c]["current_price"])
    best = by_chain[best_chain]

    offers = []
    for c in PRIMARY_ORDER:
        cpts = chain_series.get(c, [])
        today = [p for p in cpts if p.day == REF]
        if not today:
            recent = [p for p in cpts if p.day >= REF - timedelta(days=3)]
            if not recent:
                continue
            today = [max(recent, key=lambda p: p.day)]
        offers.append({"chain": c, "price": float(min(p.price for p in today))})
    offers.sort(key=lambda o: o["price"])

    return {
        "id": pid,
        "unit_kind": unit_kind,
        "best_chain": best_chain,
        "is_promo": best["is_promo"],
        "verdict": best["verdict"],
        "reason_code": best["reason_code"],
        "discount_pct": best["discount_pct"],
        "current_price": best["current_price"],
        "current_unit_price": best["current_unit_price"],
        "median_90": best["median_90"],
        "min_90": best["min_90"],
        "max_90": best["max_90"],
        "min_30_prior": best["min_30_prior"],
        "lowest_day": best["lowest_day"],
        "highest_day": best["highest_day"],
        "series": best["series"],
        "offers": offers,
        "by_chain": by_chain,
    }


# ---------------------------------------------------------------------------
# Product-first snapshot (new — drives docs/products.js and, later, search
# and the top-deals home feed)
# ---------------------------------------------------------------------------

# STATE_FROM_VERDICT is now imported from savecheck.pricing.


def _compute_product_snapshot(off: ProductOffering) -> dict | None:
    """Product snapshot with BASKET category tags added.

    Delegates the core computation to the shared `compute_snapshot` in
    savecheck.pricing (single source of truth used by both this script and
    gen_brochures.py). Only the BASKET regex tagging remains here — it's
    presentation metadata, not part of the pricing decision.
    """
    snap = compute_snapshot(off, REF, fallback_days=3)
    if snap is None:
        return None

    tags = [pid for pid, pat in BASKET.items() if pat.search(off.name)]
    if tags:
        snap["category_tags"] = tags

    return snap


def build_products_dataset(
    offerings: dict[tuple[str, str], ProductOffering],
) -> tuple[list[dict], set[tuple[str, str]]]:
    """Compact product-first dataset (drives docs/products.js).

    Filter: an offering must appear at least 3 times in the last 30 days.
    This drops one-off items that only showed up in a single brochure but
    aren't part of the regular assortment — they'd otherwise clutter the
    search UI without adding signal.

    Returns (list_of_snapshots, set_of_kept_offering_keys). The second value
    is used by build_products_history_dataset so the two datasets stay
    perfectly aligned on which (product, chain) pairs they cover."""
    min_recent = REF - timedelta(days=30)
    products: list[dict] = []
    kept: set[tuple[str, str]] = set()
    dropped_sparse = 0

    for off_key, off in offerings.items():
        recent = sum(1 for p in off.points if min_recent <= p.day <= REF)
        if recent < 3:
            dropped_sparse += 1
            continue
        snap = _compute_product_snapshot(off)
        if snap is None:
            continue
        snap["obs_30d"] = recent
        snap["obs_total"] = len(off.points)
        products.append(snap)
        kept.add(off_key)

    products.sort(key=lambda p: (p["chain"], p["name"]))
    print(f"  → {len(products)} products kept, {dropped_sparse} dropped (< 3 obs in last 30d)")

    state_counts = Counter(p.get("state") for p in products)
    for st in ("real", "cosmetic", "fake", "unverified", "regular"):
        n = state_counts.get(st, 0)
        if n:
            print(f"      {st:<12} {n}")

    return products, kept


# ---------------------------------------------------------------------------
# Product-first history (new — drives docs/products-history.js)
# ---------------------------------------------------------------------------

def build_products_history_dataset(
    offerings: dict[tuple[str, str], ProductOffering],
    kept_keys: set[tuple[str, str]],
    window_days: int = 90,
) -> dict:
    """Full price history per (product, chain), for offerings that made it
    into products.js.

    Point format is a compact 3-element array: ``[day_offset, price, is_promo]``,
    where ``day_offset`` is days back from REF (0 = REF, 1 = day before, ...).
    This shaves ~35% off the naive ISO-date format and is trivial for the UI
    to expand: ``new Date(refMs - offset * 86400000)``.

    Nested shape keeps chains grouped under each product so the UI can look
    up "history for this product across all chains it's sold in" without
    scanning the whole dataset."""
    cutoff = REF - timedelta(days=window_days)
    products: dict[str, dict[str, list]] = {}
    total_points = 0

    for off_key in kept_keys:
        off = offerings.get(off_key)
        if off is None:
            continue
        pts = sorted(
            (p for p in off.points if cutoff <= p.day <= REF),
            key=lambda p: p.day,
        )
        if not pts:
            continue
        compact = [
            [(REF - p.day).days, float(p.price), 1 if p.is_promo else 0]
            for p in pts
        ]
        products.setdefault(off.key, {})[off.chain] = compact
        total_points += len(compact)

    avg = total_points / max(1, sum(len(v) for v in products.values())) if products else 0
    print(f"  → {len(products)} products, {total_points} points total "
          f"({avg:.1f} avg per (product,chain))")

    return {
        "generated_for": REF.isoformat(),
        "ref_day": REF.isoformat(),
        "window_days": window_days,
        "point_schema": ["day_offset_from_ref", "price", "is_promo_01"],
        "products": products,
    }


# ---------------------------------------------------------------------------
# Битката на титаните — chain-level real vs fake promo scorecard
# ---------------------------------------------------------------------------

SCORECARD_DAYS = 30


def build_chain_scorecard(
    series: dict[str, dict[str, list[PricePoint]]],
) -> list[dict]:
    """Per-chain count of real vs fake promo events over the last 30 days."""
    window_start = REF - timedelta(days=SCORECARD_DAYS)

    totals: dict[str, dict] = {
        c: {"chain": c, "real": 0, "fake": 0, "total_promos": 0, "products_tracked": 0}
        for c in PRIMARY_ORDER
    }

    for pid, chain_series in series.items():
        for c in PRIMARY_ORDER:
            pts = chain_series.get(c, [])
            if not pts:
                continue
            totals[c]["products_tracked"] += 1
            for pt in pts:
                if pt.day < window_start or pt.day > REF:
                    continue
                if not pt.is_promo:
                    continue
                totals[c]["total_promos"] += 1
                stats = compute_stats(pts, pt.day, current_price=pt.price)
                if stats.min_30_prior is None or pt.price <= stats.min_30_prior:
                    totals[c]["real"] += 1
                else:
                    totals[c]["fake"] += 1

    result = []
    for c in PRIMARY_ORDER:
        t = totals[c]
        total = t["total_promos"]
        result.append({
            "chain": c,
            "real": t["real"],
            "fake": t["fake"],
            "total_promos": total,
            "real_pct": round(100 * t["real"] / total) if total else None,
            "products_tracked": t["products_tracked"],
        })
        pct = f"{t['real']}/{total}" if total else "no promos"
        print(f"  {c:<12} real={t['real']} fake={t['fake']} ({pct} real promos)")

    return result


# ---------------------------------------------------------------------------
# Стълб 2 — fridge demo (synthetic; vision requires a real camera)
# ---------------------------------------------------------------------------
ID_BG = {
    "milk": "Прясно мляко", "oil": "Олио", "cheese": "Кашкавал", "coffee": "Кафе",
    "eggs": "Яйца", "butter": "Масло", "yogurt": "Кисело мляко",
}


def build_fridge() -> dict:
    recognized = [
        {"id": "milk",   "quantity": 1, "unit": "l",    "confidence": 0.95},
        {"id": "butter", "quantity": 1, "unit": "pack", "confidence": 0.90},
        {"id": "yogurt", "quantity": 2, "unit": "pcs",  "confidence": 0.80},
        {"id": "cheese", "quantity": 1, "unit": "pack", "confidence": 0.70},
    ]
    inventory = merge_inventory(
        [to_inventory_item({**r, "name": ID_BG[r["id"]]}) for r in recognized]
    )
    staples_def = [
        ("milk",   3,  "l"),
        ("oil",    1,  "l"),
        ("eggs",   10, "pcs"),
        ("coffee", 1,  "pack"),
        ("butter", 1,  "pack"),
    ]
    unit_by_id = {sid: u for sid, _, u in staples_def}
    staples = [Staple(ID_BG[sid], q, u) for sid, q, u in staples_def]
    bg_to_id = {v: k for k, v in ID_BG.items()}

    shopping = []
    for it in build_shopping_list(inventory, staples):
        sid = bg_to_id[it.name]
        shopping.append({
            "id": sid,
            "needed_quantity": it.needed_quantity,
            "unit": unit_by_id.get(sid),
            "reason_code": "missing" if it.reason.startswith("липсва") else "low",
        })
    return {"recognized": recognized, "shopping": shopping}


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--zip-dir", default="/tmp/kzp_zips",
                        help="Directory with YYYY-MM-DD.zip files (default: /tmp/kzp_zips)")
    args = parser.parse_args()

    zip_dir = Path(args.zip_dir)

    zips = sorted(zip_dir.glob("*.zip"))
    if not zips:
        raise FileNotFoundError(f"No ZIP files found in {zip_dir}")
    global REF
    REF = date.fromisoformat(zips[-1].stem)
    print(f"Reference date: {REF} (from {zips[-1].name})")

    print(f"Loading product-first index from {zip_dir} …")
    offerings = load_all_products(zip_dir)
    print(f"  → {len(offerings)} distinct (product, chain) offerings")

    print("\nBuilding product-first dataset (products.js) …")
    products_dataset, kept_keys = build_products_dataset(offerings)

    print("\nBuilding product history dataset (products-history.js) …")
    history_dataset = build_products_history_dataset(offerings, kept_keys)

    print("\nBuilding legacy 22-category dataset (data.js) …")
    legacy_series = build_legacy_category_series(offerings)
    legacy_products = []
    for pid in BASKET:
        entry = build_entry(pid, legacy_series[pid])
        if entry:
            legacy_products.append(entry)
            promo_tag = " [PROMO]" if entry.get("is_promo") else ""
            chains_str = ", ".join(f"{o['chain']} {o['price']:.2f}" for o in entry["offers"])
            print(f"  {pid:<10} {entry['verdict']:<7} {entry['current_price']:.2f} BGN{promo_tag}  [{chains_str}]")

    print("\nBattle of the Titans — chain scorecard (last 30 days):")
    titans = build_chain_scorecard(legacy_series)

    # ---- data.js (legacy 22-category dataset, unchanged shape) ----
    data_payload = {
        "generated_for": REF.isoformat(),
        "base_currency": "BGN",
        "products": legacy_products,
        "fridge": build_fridge(),
        "titans": titans,
    }
    data_out = ROOT / "public" / "data.js"
    data_out.write_text(
        "window.SAVECHECK_DEMO = " + json.dumps(data_payload, ensure_ascii=False, indent=2) + ";\n",
        encoding="utf-8",
    )
    print(f"\nWrote {data_out}  ({len(legacy_products)} legacy category entries, "
          f"{data_out.stat().st_size / 1024:.1f} KB)")

    # ---- products.js (product-first snapshot, new) ----
    products_payload = {
        "generated_for": REF.isoformat(),
        "base_currency": "BGN",
        "min_obs_days": 3,           # filter parameter (surfaced in "How it works")
        "recency_window_days": 30,
        "products": products_dataset,
    }
    products_out = ROOT / "public" / "products.js"
    products_out.write_text(
        "window.SAVECHECK_PRODUCTS = " + json.dumps(products_payload, ensure_ascii=False, separators=(",", ":")) + ";\n",
        encoding="utf-8",
    )
    size_kb = products_out.stat().st_size / 1024
    print(f"Wrote {products_out}  ({len(products_dataset)} products, {size_kb:.1f} KB)")
    if size_kb > 2048:
        print(f"  ⚠  products.js exceeds 2 MB — consider tightening the min_obs filter "
              f"or moving history to an API endpoint before Slice 2.")

    # ---- products-history.js (per-product 90-day series, new) ----
    history_out = ROOT / "public" / "products-history.js"
    history_out.write_text(
        "window.SAVECHECK_HISTORY = " + json.dumps(history_dataset, ensure_ascii=False, separators=(",", ":")) + ";\n",
        encoding="utf-8",
    )
    hist_size_mb = history_out.stat().st_size / 1024 / 1024
    print(f"Wrote {history_out}  ({hist_size_mb:.2f} MB)")
    if hist_size_mb > 25:
        print(f"  ⚠  products-history.js exceeds 25 MB — time to migrate to an API endpoint "
              f"(Vercel Edge Function + KV) rather than static hosting.")


if __name__ == "__main__":
    main()
