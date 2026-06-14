"""Ingest a real КЗП "Колко струва" open-data export.

  # A downloaded export ZIP (one CSV per chain). Date inferred from the name
  # if it contains YYYYMMDD, else pass --date.
  python scripts/ingest_kolkostruva.py --zip ~/Downloads/31a3e9ec-20260612.zip

  # An already-unzipped directory
  python scripts/ingest_kolkostruva.py --dir ./export --date 2026-06-12

Prints how many rows parsed, the chains and product counts, promo counts and a
sample — confirming the parser matches the real КЗП format.
"""

from __future__ import annotations

import argparse
import re
import sys
import tempfile
import zipfile
from collections import Counter
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from savecheck.ingest.kolkostruva import parse_export  # noqa: E402


def _infer_date(name: str) -> date | None:
    m = re.search(r"(\d{4})(\d{2})(\d{2})", name)
    return date(int(m[1]), int(m[2]), int(m[3])) if m else None


def summarize(directory: Path, observed_on: date) -> int:
    rows = list(parse_export(directory, observed_on))
    if not rows:
        print("⚠️  0 rows parsed — check the column headers against the parser.")
        return 1

    chains = Counter(r.chain_name for r in rows)
    promos = sum(1 for r in rows if r.is_promo)
    products = {r.product_name for r in rows}
    print(f"✅ parsed {len(rows):,} price rows for {observed_on} across {len(chains)} chains")
    print(f"   distinct products: {len(products):,}")
    print(f"   on promotion: {promos:,} ({100*promos/len(rows):.1f}%)")
    print("   top chains by rows:")
    for chain, n in chains.most_common(8):
        print(f"     {n:>8,}  {chain}")
    print("\n   sample (chain | product | price | promo?):")
    for r in rows[:6]:
        tag = "PROMO" if r.is_promo else ""
        print(f"     {r.chain_name} | {r.product_name[:42]} | {r.price} | {tag}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Parse a real КЗП kolkostruva export")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--zip", type=Path, help="Export ZIP (one CSV per chain)")
    g.add_argument("--dir", type=Path, help="Already-unzipped export directory")
    ap.add_argument("--date", type=date.fromisoformat, help="Snapshot date (YYYY-MM-DD)")
    args = ap.parse_args()

    src_name = (args.zip or args.dir).name
    observed_on = args.date or _infer_date(src_name)
    if observed_on is None:
        ap.error("could not infer date from the name — pass --date YYYY-MM-DD")

    if args.dir:
        return summarize(args.dir, observed_on)

    with tempfile.TemporaryDirectory() as tmp:
        with zipfile.ZipFile(args.zip) as zf:
            zf.extractall(tmp)
        return summarize(Path(tmp), observed_on)


if __name__ == "__main__":
    sys.exit(main())
