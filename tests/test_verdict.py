"""Tests for the traffic-light verdict. Pure stdlib; no DB needed."""

from __future__ import annotations

import sys
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from savecheck.pricing.aggregates import PricePoint  # noqa: E402
from savecheck.pricing.verdict import Verdict, VerdictConfig, evaluate_series  # noqa: E402

REF = date(2026, 6, 13)


def steady(price: str, days: int = 60) -> list[PricePoint]:
    """A flat price history of `days` daily observations ending the day before REF."""
    return [PricePoint.of(REF - timedelta(days=d), price) for d in range(1, days + 1)]


def test_unknown_when_history_too_short():
    points = [PricePoint.of(REF - timedelta(days=d), "3.00") for d in range(1, 5)]
    res = evaluate_series(points, REF, is_promo=True, current_price=Decimal("2.00"))
    assert res.verdict is Verdict.UNKNOWN


def test_real_discount_near_floor():
    # Typical price ~3.00 for two months; today it drops to 2.50 (~17% off).
    points = steady("3.00")
    res = evaluate_series(points, REF, is_promo=True, current_price=Decimal("2.50"))
    assert res.verdict is Verdict.REAL
    assert res.discount_vs_median is not None and res.discount_vs_median > Decimal("0.15")


def test_fake_promo_inflated_then_discounted():
    # Price was 3.00, got bumped, and the "promo" 3.00 is not below the 30d low.
    points = steady("3.00")
    res = evaluate_series(points, REF, is_promo=True, current_price=Decimal("3.00"))
    assert res.verdict is Verdict.FAKE


def test_fake_promo_when_not_below_recent_low():
    # Recent 30 days were as low as 2.80; a "promo" at 2.90 saves nothing real.
    points = (
        [PricePoint.of(REF - timedelta(days=d), "3.20") for d in range(31, 90)]
        + [PricePoint.of(REF - timedelta(days=d), "2.80") for d in range(1, 31)]
    )
    res = evaluate_series(points, REF, is_promo=True, current_price=Decimal("2.90"))
    assert res.verdict is Verdict.FAKE


def test_cosmetic_small_discount_not_promo():
    points = steady("3.00")
    # ~3% under median, not advertised as a promo -> small real cut.
    res = evaluate_series(points, REF, is_promo=False, current_price=Decimal("2.90"))
    assert res.verdict is Verdict.COSMETIC


def test_everyday_price_not_promo_is_cosmetic():
    points = steady("3.00")
    res = evaluate_series(points, REF, is_promo=False, current_price=Decimal("3.00"))
    assert res.verdict is Verdict.COSMETIC


def test_genuine_promo_below_prior_low_is_real():
    # Was 3.00 normally, briefly 2.90 last week; today a true low of 2.40.
    points = (
        steady("3.00", days=60)
        + [PricePoint.of(REF - timedelta(days=d), "2.90") for d in (6, 7, 8)]
    )
    res = evaluate_series(points, REF, is_promo=True, current_price=Decimal("2.40"))
    assert res.verdict is Verdict.REAL


# ── sample-size threshold ────────────────────────────────────────────────
# The effective cutoff is VerdictConfig.min_sample_90 observations inside the
# 90-day window — not the "3 observations in 30 days" the README and info
# modal claimed. snapshot.py has its own >= 3 pre-gate, but it never binds:
# anything between 3 and 9 reaches evaluate() and comes back UNKNOWN anyway.


def test_two_observations_unknown():
    res = evaluate_series(steady("3.00", days=2), REF, is_promo=True,
                          current_price=Decimal("2.00"))
    assert res.verdict is Verdict.UNKNOWN


def test_three_observations_still_unknown():
    # Three is the number the docs advertised. It is not the threshold.
    res = evaluate_series(steady("3.00", days=3), REF, is_promo=True,
                          current_price=Decimal("2.00"))
    assert res.verdict is Verdict.UNKNOWN


def test_nine_observations_unknown():
    res = evaluate_series(steady("3.00", days=9), REF, is_promo=True,
                          current_price=Decimal("2.00"))
    assert res.verdict is Verdict.UNKNOWN


def test_ten_observations_is_judged():
    # One more observation and the same input becomes judgeable.
    assert VerdictConfig().min_sample_90 == 10
    res = evaluate_series(steady("3.00", days=10), REF, is_promo=True,
                          current_price=Decimal("2.00"))
    assert res.verdict is not Verdict.UNKNOWN


# ── the <= comparison against min_30_prior ───────────────────────────────


def test_ongoing_promo_stays_real_after_first_day():
    """A multi-day promotion must not turn fake on day two.

    min_30_prior is computed over [ref-30, ref-1] and includes promo days, so
    once a promotion has run for a day the prior window already contains the
    promo price and min_30_prior == current. Equality is therefore the normal
    state of a genuine week-long promotion, not an edge case.

    This test fails if the comparison is tightened from <= to <, which is the
    change that reading "below the 30-day low" in the UI naturally suggests.
    """
    points = (
        [PricePoint.of(REF - timedelta(days=d), "3.00") for d in range(4, 64)]
        + [PricePoint.of(REF - timedelta(days=d), "2.40") for d in (1, 2, 3)]
    )
    res = evaluate_series(points, REF, is_promo=True, current_price=Decimal("2.40"))
    assert res.verdict is Verdict.REAL


# ── missing Omnibus reference ────────────────────────────────────────────


def test_promo_without_prior_window_is_unknown():
    """No observations in the prior 30 days means no reference to test against.

    Plenty of 90-day history, but the product dropped out of the feed a month
    ago and reappeared today. Before this was fixed the missing reference
    counted as passing the Omnibus test and the item came back REAL purely on
    the 90-day median.
    """
    points = [PricePoint.of(REF - timedelta(days=d), "3.00") for d in range(31, 71)]
    res = evaluate_series(points, REF, is_promo=True, current_price=Decimal("2.00"))
    assert res.verdict is Verdict.UNKNOWN


def test_no_prior_window_without_promo_is_not_real():
    """Same gap, no promo flag: REAL asserts a 30-day floor we never saw."""
    points = [PricePoint.of(REF - timedelta(days=d), "3.00") for d in range(31, 71)]
    res = evaluate_series(points, REF, is_promo=False, current_price=Decimal("2.00"))
    assert res.verdict is not Verdict.REAL


if __name__ == "__main__":
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS {name}")
            except AssertionError as exc:
                failures += 1
                print(f"FAIL {name}: {exc}")
    print(f"\n{('OK' if not failures else str(failures) + ' FAILED')}")
    sys.exit(1 if failures else 0)
