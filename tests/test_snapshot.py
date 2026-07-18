"""Tests for savecheck.pricing.snapshot — the shared product snapshot
computation used by both gen_demo_data.py and gen_brochures.py.

The point of these tests: pin down the exact behaviour, so if either script
regresses (or the two ever get out of sync again), the failure surfaces
here first, not in production.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from savecheck.pricing import PricePoint, ProductOffering, compute_snapshot


REF = date(2026, 7, 17)


def _make_points(
    prices_and_flags: list[tuple[int, str, bool]],
) -> list[PricePoint]:
    """Build PricePoints from `(days_before_ref, price_str, is_promo)` tuples."""
    return [
        PricePoint(
            day=REF - timedelta(days=days),
            price=Decimal(price),
            is_promo=is_promo,
        )
        for days, price, is_promo in prices_and_flags
    ]


def _off(points: list[PricePoint], retail_map: dict[date, Decimal] | None = None) -> ProductOffering:
    return ProductOffering(
        key="code:1234",
        name="Test Product",
        code="1234",
        kzp_category="9",
        chain="Kaufland",
        points=points,
        retail_prices=retail_map or {},
    )


class TestEmpty:
    def test_no_points_returns_none(self):
        off = _off([])
        assert compute_snapshot(off, REF) is None

    def test_all_stale_returns_none(self):
        # Only observations older than fallback_days (default 3)
        points = _make_points([(5, "3.00", False), (10, "3.00", False)])
        assert compute_snapshot(_off(points), REF) is None


class TestFallback:
    def test_uses_ref_day_when_present(self):
        points = _make_points([(0, "2.00", True), (5, "3.00", False)])
        snap = compute_snapshot(_off(points), REF)
        assert snap["price"] == 2.00
        assert snap["observed_on"] == REF.isoformat()

    def test_falls_back_to_recent_when_ref_missing(self):
        points = _make_points([(1, "2.50", True), (2, "3.00", True)])
        snap = compute_snapshot(_off(points), REF)
        assert snap["price"] == 2.50
        assert snap["observed_on"] == (REF - timedelta(days=1)).isoformat()

    def test_respects_custom_fallback_days(self):
        points = _make_points([(2, "2.50", True)])
        # With fallback_days=1, the 2-day-old observation is stale
        assert compute_snapshot(_off(points), REF, fallback_days=1) is None
        # With fallback_days=3, it's fresh enough
        snap = compute_snapshot(_off(points), REF, fallback_days=3)
        assert snap is not None


class TestPromoDetection:
    def _promo_over_90d(self, current_price: str, current_promo: bool):
        """Build 90 days of history: 60 obs at 5.00, then today's snapshot."""
        history = [(d, "5.00", False) for d in range(1, 61)]
        return _make_points([(0, current_price, current_promo)] + history)

    def test_regular_when_not_promo_today(self):
        points = self._promo_over_90d("5.00", False)
        snap = compute_snapshot(_off(points), REF)
        assert snap["state"] == "regular"
        assert snap["is_promo"] is False
        # No verdict fields when not on promo
        assert "omnibus_pct" not in snap

    def test_real_when_promo_below_prior_min(self):
        # 60 obs at 5.00, today 3.00 with promo → clearly below prior min
        points = self._promo_over_90d("3.00", True)
        snap = compute_snapshot(_off(points), REF)
        assert snap["state"] == "real"
        assert snap["is_promo"] is True
        assert snap["omnibus_pct"] is not None
        assert snap["omnibus_pct"] > 30  # ~40% below median

    def test_fake_when_promo_same_as_regular(self):
        # 60 obs at 5.00, today 5.00 with promo flag → marketing lie
        points = self._promo_over_90d("5.00", True)
        snap = compute_snapshot(_off(points), REF)
        assert snap["state"] == "fake"
        assert snap["is_promo"] is True

    def test_unverified_when_promo_but_no_history(self):
        # Only 2 observations, one is today with promo
        points = _make_points([(0, "2.00", True), (5, "5.00", False)])
        snap = compute_snapshot(_off(points), REF)
        assert snap["state"] == "unverified"


class TestRetailAndClaimedPct:
    def test_retail_at_ref_used_when_present(self):
        points = _make_points([(0, "2.00", True)])
        retail = {REF: Decimal("3.00")}
        snap = compute_snapshot(_off(points, retail), REF)
        assert snap["retail"] == 3.00
        # (3-2)/3 = 33.33% → 33
        assert snap["claimed_pct"] == 33

    def test_falls_back_to_latest_retail(self):
        # Current obs on REF, retail only from earlier date
        points = _make_points([(0, "2.00", True), (5, "2.20", False)])
        retail = {REF - timedelta(days=5): Decimal("2.50")}
        snap = compute_snapshot(_off(points, retail), REF)
        assert snap["retail"] == 2.50

    def test_no_claimed_pct_when_retail_not_higher(self):
        points = _make_points([(0, "3.00", True)])
        retail = {REF: Decimal("3.00")}
        snap = compute_snapshot(_off(points, retail), REF)
        assert snap["claimed_pct"] is None


class TestKauflandStyleFallback:
    """Reproduces the concrete case that motivated this refactor:

    Kaufland doesn't publish for REF. Products.js's old logic would take
    the cheapest observation in the 3-day fallback (potentially a non-promo
    row from another store). Brochures's old logic would filter to promo
    rows only from the last-published day. The two disagreed.

    With the shared snapshot, both scripts see the SAME behaviour: fallback
    to the most recent day, use its aggregated is_promo flag.
    """

    def test_fallback_preserves_promo_status(self):
        # Chain didn't publish today. Two days ago it did, and the row was
        # marked as a promo below the recent low.
        # 60 days of steady 5.00 no-promo, then 2 days ago a promo at 3.00
        history = [(d, "5.00", False) for d in range(3, 63)]
        points = _make_points([(2, "3.00", True)] + history)
        snap = compute_snapshot(_off(points), REF)
        assert snap is not None
        # Should be flagged as a real promo, using the 2-day-old data
        assert snap["is_promo"] is True
        assert snap["state"] == "real"
        assert snap["observed_on"] == (REF - timedelta(days=2)).isoformat()


class TestSchemaStability:
    """These tests pin down the exact snapshot dict schema so gen_demo_data
    and gen_brochures can rely on it, and so the frontend consuming
    products.js / brochures.js keeps working.
    """

    def test_snapshot_has_all_required_fields(self):
        # A well-defined promo product with enough history
        history = [(d, "5.00", False) for d in range(1, 61)]
        points = _make_points([(0, "3.00", True)] + history)
        snap = compute_snapshot(_off(points, {REF: Decimal("6.00")}), REF)

        required = {
            "id", "name", "code", "chain", "price", "retail", "claimed_pct",
            "is_promo", "kzp_category", "observed_on", "state", "reason_code",
        }
        assert required.issubset(snap.keys()), f"Missing: {required - snap.keys()}"

    def test_regular_snapshot_omits_verdict_fields(self):
        history = [(d, "5.00", False) for d in range(1, 61)]
        points = _make_points([(0, "5.00", False)] + history)
        snap = compute_snapshot(_off(points), REF)
        assert snap["state"] == "regular"
        # These are only present for promo products
        assert "omnibus_pct" not in snap
        assert "min_30_prior" not in snap
        assert "median_90" not in snap
