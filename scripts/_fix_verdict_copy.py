#!/usr/bin/env python3
"""One-off: correct two false statements in the verdict copy.

    python scripts/_fix_verdict_copy.py --dry
    python scripts/_fix_verdict_copy.py

CLAIM 1 — "the price is below the 30-day low"
    The comparison is <=, and equality is the normal case rather than a
    corner: min_30_prior spans [ref-30, ref-1] and includes promo days,
    so from day two of any multi-day promotion it equals today's price.
    The live home screen shows an item at 0.08 whose 30-day low is 0.08,
    explained as being below it.

    Fixed in the copy, not the comparison. Tightening to < would mark
    essentially every real week-long promotion fake on its second day —
    see test_ongoing_promo_stays_real_after_first_day.

CLAIM 2 — "fewer than 3 observations in 30 days"
    Not the rule being applied. evaluate() returns UNKNOWN below
    VerdictConfig.min_sample_90 — 10 observations inside the 90-day
    window. Three-in-thirty exists here but governs something else:
    whether an offering enters products.js at all. That filter is
    correct and untouched.

PER-EDIT, NOT ALL-OR-NOTHING
    These are independent sentences in eleven locales. A mistyped anchor
    in one language is no reason to withhold the other twenty-one, so
    each edit is applied on its own and misses are reported at the end
    with the locale's real text printed for inspection.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "docs" / "index.html"
README = ROOT / "README.md"
DRY = "--dry" in sys.argv

# (label, locale, old, new, expected occurrences)
INDEX_EDITS = [
    # ── claim 1: the "real" explanation ──────────────────────────────
    ("real", "bg", "Цената е под най-ниската от последните 30 дни.",
     "Това е най-ниската цена за последните 30 дни.", 1),
    ("real", "en", "The price is below the lowest of the last 30 days.",
     "This is the lowest price of the last 30 days.", 1),
    ("real", "sr", "Cena je ispod najniže cene poslednjih 30 dana.",
     "Ovo je najniža cena poslednjih 30 dana.", 1),
    ("real", "mk", "Цената е под најниската од последните 30 дена.",
     "Ова е најниската цена од последните 30 дена.", 1),
    ("real", "ro", "Prețul este sub cel mai mic din ultimele 30 de zile.",
     "Acesta este cel mai mic preț din ultimele 30 de zile.", 1),
    ("real", "el", "Η τιμή είναι κάτω από τη χαμηλότερη των τελευταίων 30 ημερών.",
     "Αυτή είναι η χαμηλότερη τιμή των τελευταίων 30 ημερών.", 1),
    ("real", "tr", "Fiyat, son 30 günün en düşüğünün altında.",
     "Bu, son 30 günün en düşük fiyatı.", 1),
    ("real", "sq", "Çmimi është më i ulët në 30 ditëve të fundit.",
     "Ky është çmimi më i ulët i 30 ditëve të fundit.", 1),
    # bs and hr ship the same sentence.
    ("real", "bs+hr", "Cijena je ispod najniže cijene posljednjih 30 dana.",
     "Ovo je najniža cijena posljednjih 30 dana.", 2),
    ("real", "sl", "Cena je pod najnižjo v zadnjih 30 dneh.",
     "To je najnižja cena v zadnjih 30 dneh.", 1),

    # ── claim 2: the observation threshold ───────────────────────────
    # Each phrase appears in PRODUCT_MODAL_I18N.stateExplain and again in
    # the info modal's iconUnverifiedText, except where locales share
    # wording — noted per line.
    ("threshold", "bg", "3 наблюдения за 30 дни", "10 наблюдения за 90 дни", 2),
    ("threshold", "en", "3 observations in 30 days", "10 observations in 90 days", 2),
    ("threshold", "sr+bs", "3 osmatranja za 30 dana", "10 osmatranja za 90 dana", 3),
    ("threshold", "bs+hr", "3 opažanja za 30 dana", "10 opažanja za 90 dana", 2),
    ("threshold", "hr", "3 opažanja u 30 dana", "10 opažanja u 90 dana", 1),
    ("threshold", "mk", "3 набљудувања за 30 дена", "10 набљудувања за 90 дена", 2),
    ("threshold", "ro", "3 observații în 30 de zile", "10 observații în 90 de zile", 2),
    ("threshold", "el", "3 παρατηρήσεις σε 30 ημέρες", "10 παρατηρήσεις σε 90 ημέρες", 2),
    ("threshold", "tr", "30 günde 3 gözlemden az", "90 günde 10 gözlemden az", 2),
    ("threshold", "sq", "3 vëzhgime në 30 ditë", "10 vëzhgime në 90 ditë", 2),
    ("threshold", "sl", "3 opažanja v 30 dneh", "10 opažanja v 90 dneh", 2),
]

README_EDITS = [
    ("table", "real",
     "| 🟢 **real** | Промо цената е под най-ниската от последните 30 дни — реална икономия |",
     "| 🟢 **real** | Промо цената е най-ниската за последните 30 дни — реална икономия |", 1),
    ("table", "unverified",
     "| ⚪ **unverified** | Обявена промоция, но има под 3 наблюдения за 30 дни — недостатъчна история |",
     "| ⚪ **unverified** | Обявена промоция, но има под 10 наблюдения за 90 дни — недостатъчна история"
     " (`VerdictConfig.min_sample_90`; различен праг от филтъра за влизане в `products.js`) |", 1),
]


def apply(edits, text):
    misses = []
    for kind, loc, old, new, expected in edits:
        label = f"{loc} {kind}"
        n = text.count(old)
        if n == expected:
            text = text.replace(old, new)
            print(f"  OK      {label:<18} ({n})")
        elif n == 0 and new in text:
            print(f"  --      {label:<18} already applied")
        elif n == 0:
            print(f"  MISS    {label:<18} anchor not found")
            misses.append((kind, loc))
        else:
            print(f"  SKIP    {label:<18} found {n}, expected {expected}")
            misses.append((kind, loc))
    return text, misses


def show_locale(text, loc):
    """Print a locale's real stateExplain line, so a bad anchor can be read off."""
    for i, line in enumerate(text.splitlines(), 1):
        s = line.strip()
        if s.startswith(f"{loc}: {{") or s == f"{loc}: {{":
            for j, follow in enumerate(text.splitlines()[i - 1: i + 3], i):
                if "stateExplain" in follow:
                    print(f"\n    line {j}:\n    {follow.strip()[:400]}")
                    return
    print(f"\n    (could not locate a stateExplain line for {loc!r})")


def main() -> None:
    for p in (INDEX, README):
        if not p.exists():
            raise SystemExit(f"ABORT: {p} not found — run from the repo root.")

    print("Verdict copy fix" + ("  (DRY RUN)" if DRY else ""))

    print("\n  docs/index.html")
    idx_before = INDEX.read_text(encoding="utf-8")
    idx, idx_miss = apply(INDEX_EDITS, idx_before)

    print("\n  README.md")
    rdm, rdm_miss = apply(README_EDITS, README.read_text(encoding="utf-8"))

    if not DRY:
        INDEX.write_text(idx, encoding="utf-8")
        README.write_text(rdm, encoding="utf-8")

    if idx_miss:
        print("\n" + "-" * 66)
        print("UNRESOLVED — actual text for the locales that did not match:")
        print("-" * 66)
        for _, loc in {(k, l) for k, l in idx_miss}:
            for one in loc.split("+"):
                show_locale(idx_before, one)

    total = len(INDEX_EDITS) + len(README_EDITS)
    done = total - len(idx_miss) - len(rdm_miss)
    print(f"\n{done} of {total} applied." + ("  (dry run — nothing written)" if DRY else ""))
    if idx_miss or rdm_miss:
        print("Re-run after the remaining anchors are corrected; applied edits are idempotent.")
    else:
        print("Review:  git diff")


if __name__ == "__main__":
    main()
