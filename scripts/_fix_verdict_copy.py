#!/usr/bin/env python3
"""One-off: correct two false statements in the verdict copy.

    python scripts/_fix_verdict_copy.py --dry
    python scripts/_fix_verdict_copy.py

CLAIM 1 — "the price is below the 30-day low"
    The comparison is <=, and equality is the normal case rather than a
    corner: min_30_prior spans [ref-30, ref-1] and includes promo days,
    so from day two of any multi-day promotion it equals today's price.
    The live home screen currently shows an item at 0.08 whose 30-day
    low is 0.08, explained as being below it.

    Fixed in the copy, not the comparison. Tightening to < would mark
    essentially every real week-long promotion as fake on its second day
    — see test_ongoing_promo_stays_real_after_first_day.

CLAIM 2 — "fewer than 3 observations in 30 days"
    That is not the rule being applied. evaluate() returns UNKNOWN below
    VerdictConfig.min_sample_90, which is 10 observations inside the
    90-day window.

    Three-in-thirty does exist in this codebase, but it governs
    something else: whether an offering enters products.js at all. That
    filter is correct and is left alone. The bug is that the verdict
    copy quotes the inclusion filter while describing the judgement
    threshold.

Some strings are shared between locales — bs and hr carry identical
"real" text, and sr/bs share an "unverified" phrasing — so replacements
are applied everywhere they occur with an expected count asserted.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "docs" / "index.html"
README = ROOT / "README.md"
DRY = "--dry" in sys.argv

# (label, old, new, expected occurrences)
INDEX_EDITS: list[tuple[str, str, str, int]] = [
    # ── claim 1: the "real" explanation, 11 locales ──────────────────
    ("bg real", "Цената е под най-ниската от последните 30 дни.",
     "Това е най-ниската цена за последните 30 дни.", 1),
    ("en real", "The price is below the lowest of the last 30 days.",
     "This is the lowest price of the last 30 days.", 1),
    ("sr real", "Cena je ispod najniže cene poslednjih 30 dana.",
     "Ovo je najniža cena poslednjih 30 dana.", 1),
    ("mk real", "Цената е под најниската од последните 30 дена.",
     "Ова е најниската цена од последните 30 дена.", 1),
    ("ro real", "Prețul este sub cel mai mic din ultimele 30 de zile.",
     "Acesta este cel mai mic preț din ultimele 30 de zile.", 1),
    ("el real", "Η τιμή είναι κάτω από τη χαμηλότερη των τελευταίων 30 ημερών.",
     "Αυτή είναι η χαμηλότερη τιμή των τελευταίων 30 ημερών.", 1),
    ("tr real", "Fiyat, son 30 günün en düşüğünün altında.",
     "Bu, son 30 günün en düşük fiyatı.", 1),
    ("sq real", "Çmimi është më i ulët në 30 ditëve të fundit.",
     "Ky është çmimi më i ulët i 30 ditëve të fundit.", 1),
    # bs and hr ship the same sentence.
    ("bs+hr real", "Cijena je ispod najniže cijene posljednjih 30 dana.",
     "Ovo je najniža cijena posljednjih 30 dana.", 2),
    ("sl real", "Cena je pod najnižjo v zadnjih 30 dneh.",
     "To je najnižja cena v zadnjih 30 dneh.", 1),

    # ── claim 2: the observation threshold, both copies per locale ───
    # Each phrase appears twice — once in PRODUCT_MODAL_I18N.stateExplain
    # and once in the info modal's iconUnverifiedText — except where
    # locales share wording, noted below.
    ("bg threshold", "3 наблюдения за 30 дни", "10 наблюдения за 90 дни", 2),
    ("en threshold", "3 observations in 30 days", "10 observations in 90 days", 2),
    # sr uses this in both its strings; bs reuses it for iconUnverifiedText.
    ("sr+bs threshold", "3 osmatranja za 30 dana", "10 osmatranja za 90 dana", 3),
    # bs stateExplain and hr iconUnverifiedText.
    ("bs+hr threshold", "3 opažanja za 30 dana", "10 opažanja za 90 dana", 2),
    ("hr threshold", "3 opažanja u 30 dana", "10 opažanja u 90 dana", 1),
    ("mk threshold", "3 набљудувања за 30 дена", "10 набљудувања за 90 дена", 2),
    ("ro threshold", "3 observații în 30 de zile", "10 observații în 90 de zile", 2),
    ("el threshold", "3 παρατηρήσεις σε 30 ημέρες", "10 παρατηρήσεις σε 90 ημέρες", 2),
    ("tr threshold", "30 günde 3 gözlemden az", "90 günde 10 gözlemden az", 2),
    ("sq threshold", "3 vëzhgime në 30 ditë", "10 vëzhgime në 90 ditë", 2),
    ("sl threshold", "3 opažanja v 30 dneh", "10 opažanja v 90 dneh", 2),
]

README_EDITS: list[tuple[str, str, str, int]] = [
    ("verdict table — real",
     "| 🟢 **real** | Промо цената е под най-ниската от последните 30 дни — реална икономия |",
     "| 🟢 **real** | Промо цената е най-ниската за последните 30 дни — реална икономия |", 1),
    ("verdict table — unverified",
     "| ⚪ **unverified** | Обявена промоция, но има под 3 наблюдения за 30 дни — недостатъчна история |",
     "| ⚪ **unverified** | Обявена промоция, но има под 10 наблюдения за 90 дни — недостатъчна история"
     " (`VerdictConfig.min_sample_90`; различен праг от филтъра за влизане в `products.js`) |", 1),
]


def apply(path: Path, edits: list[tuple[str, str, str, int]], text: str) -> str:
    for label, old, new, expected in edits:
        n = text.count(old)
        if n == expected:
            text = text.replace(old, new)
            print(f"  OK    {label:<20} ({n})")
        elif n == 0 and text.count(new) >= 1:
            print(f"  --    {label:<20} (already applied)")
        else:
            raise SystemExit(
                f"\nABORT: {label!r} matched {n} times, expected {expected}.\n"
                f"       Nothing written to any file."
            )
    return text


def main() -> None:
    for p in (INDEX, README):
        if not p.exists():
            raise SystemExit(f"ABORT: {p} not found — run from the repo root.")

    print("Verdict copy fix" + ("  (DRY RUN)" if DRY else ""))

    print("\n  docs/index.html")
    idx = apply(INDEX, INDEX_EDITS, INDEX.read_text(encoding="utf-8"))

    print("\n  README.md")
    rdm = apply(README, README_EDITS, README.read_text(encoding="utf-8"))

    if DRY:
        print("\nDry run — nothing written.")
        return

    INDEX.write_text(idx, encoding="utf-8")
    README.write_text(rdm, encoding="utf-8")
    print("\nDone.  Review:  git diff")


if __name__ == "__main__":
    main()
