#!/usr/bin/env python3
"""One-off: record this session's roadmap measurements in the README.

    python scripts/_readme_findings.py --dry
    python scripts/_readme_findings.py

WHY
    Three read-only analyses settled two roadmap items and opened a
    third question. That knowledge lives only in the scripts' output
    right now. The design mockup, meanwhile, still shows a chain-ranking
    home screen — so without writing the findings down, the obvious next
    move six weeks from now looks like "build the thing in the design",
    and the 4310-offerings-to-15-matches result has to be rediscovered.

WHAT IT CHANGES
    README.md — rewrites the cross-chain entry under Известни
    ограничения with the measured result, adds entries for the category
    basket and the promotion-rate asymmetry, amends the data.js removal
    plan, lists the analysis scripts in the structure tree, and updates
    the Fonts row for the self-hosted Golos Text.

Delete this file afterwards.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
DRY = "--dry" in sys.argv

EDITS: list[tuple[str, str, str]] = []


def edit(label: str, old: str, new: str) -> None:
    EDITS.append((label, old, new))


# ── cross-chain: from "future feature" to "measured and ruled out" ───
edit(
    "cross-chain entry",
    "- **Cross-chain matching** — при cart с items от 2+ вериги не сравняваме един и"
    " същ продукт между вериги. КЗП product код-ове са различни в различните вериги"
    " (същият кашкавал има различен `Код` в Kaufland и в BILLA). Отделен feature за"
    " бъдеще — вероятно fuzzy name matching + code lookup.",

    "- **Cross-chain matching — измерено и отпаднало (05.08.2026).**"
    " `scripts/analyze_cross_chain.py` върху 4310 оферти: 100% от продуктите имат"
    " `code`-базиран ключ, но **нула** съвпадения между вериги — кодовете са изцяло"
    " вътрешнофирмени, няма обща EAN основа. Съпоставяне по нормализирано име +"
    " разфасовка дава **15 групи**; хлабавото по множество от думи — 49. Всичките са"
    " маркова пакетирана стока (SYOSS, MILKA, SENSODYNE, Devin) — нищо прясно, нищо"
    " собствена марка, защото `ПЛЕШКА СВИНСКА ПР-Д АЛДАГОТ` наистина е друг продукт,"
    " а не същият под друго име. Качеството на намереното е добро (медианен разсейв"
    " 1.31x, нито една група над 2x), тоест ограничението не е в алгоритъма — няма"
    " какво да се хване, а по-хлабава нормализация само би започнала да произвежда"
    " фалшиви двойки. **Класацията на вериги по цена на кошницата от дизайна не е"
    " постижима по този път.** Не си струва преразглеждане без нов източник на данни.",
)

# ── the viable route, with its cost stated ───────────────────────────
edit(
    "category basket entry (new)",
    "- **Products / Recipes / Fridge sub-tabs** — hidden в UI",

    "- **Категорийна кошница — възможна, но иска нормализация.** Пътят към „къде е"
    " най-евтино\" минава през 22-те BASKET категории, не през конкретни продукти:"
    " сравняваме „най-евтиното прясно мляко 1л\", както правят реалните ценови"
    " индекси. `scripts/analyze_category_basket.py` показва, че в сегашния вид би"
    " подвеждало. Само **6 от 22** категории имат цена във всичките пет вериги. И"
    " по-съществено — сравняват се несравними неща: масло 125 г срещу 250 г, сирене"
    " 200 г срещу 400 г, пилешко **бутче** срещу пилешко **филе**, Evian срещу Горна"
    " баня. `UNIT_INFO` приема фиксиран грамаж за категория, вместо да чете реалния от"
    " името на продукта. Преди какъвто и да е интерфейс: четене на разфасовката от"
    " името, сравнение на килограм и литър, стесняване на изразите, решение какво"
    " правим с непълните категории. Оценка 3-5 часа, предимно Python.\n"
    "- **Делът на реалните промоции варира петдесеткратно между веригите —"
    " необяснено.** Kaufland 45/223 (20.2%), Fantastico 304/2359 (12.9%), T Market"
    " 84/762 (11.0%), Lidl 13/698 (1.9%), Billa 1/280 (0.4%). Lidl живее от промоции;"
    " 1.9% не описва нищо, което може да се види в магазин. Най-правдоподобното"
    " обяснение е, че веригите различно попълват колоната „Цена в промоция\" към КЗП —"
    " ако някои свалят направо цената на дребно, техните промоции не съществуват за"
    " pipeline-а, защото `is_promo` никога не става истина. Ако е така, **Битката на"
    " Титаните класира счетоводна дисциплина, а не честност**, а това е публично"
    " твърдение в приложението. Непроверено — виж дела на `is_promo` по вериги.\n"
    "- **Products / Recipes / Fridge sub-tabs** — hidden в UI",
)

# ── data.js removal is no longer a clean call ────────────────────────
edit(
    "data.js removal plan",
    "- **`data.js` все още се качва еагерно** (~880 KB). Titans view все още го"
    " консумира. Планиран Python change ще мигрира Titans aggregate в `products.js`"
    " meta и ще позволи drop-ване на data.js entirely.",

    "- **`data.js` все още се качва еагерно** (~880 KB). Titans view го консумира."
    " Планираното му премахване обаче е под въпрос: категорийната кошница (по-долу)"
    " стъпва точно върху неговите 22-категорийни серии, а `products.js` не ги носи в"
    " тази форма. Решението за drop чака решението за кошницата.",
)

# ── make the analysis scripts discoverable ───────────────────────────
edit(
    "scripts in structure tree",
    "├── scripts/\n"
    "│   ├── gen_demo_data.py          # Генерира data.js + products.js + products-history.js\n"
    "│   └── gen_brochures.py          # Генерира brochures.js (използва shared snapshot)",

    "├── scripts/\n"
    "│   ├── gen_demo_data.py          # Генерира data.js + products.js + products-history.js\n"
    "│   ├── gen_brochures.py          # Генерира brochures.js (използва shared snapshot)\n"
    "│   ├── analyze_cross_chain.py    # Read-only: съпоставимост на продукти между вериги\n"
    "│   ├── analyze_duplicates.py     # Read-only: дублирани оферти в рамките на верига\n"
    "│   └── analyze_category_basket.py # Read-only: годност на 22-те категории за кошница",
)

# ── the redesign shipped a second webfont ────────────────────────────
edit(
    "Fonts row",
    "| Fonts | Twemoji Country Flags WOFF2 (78 KB, unicode-range scoped,"
    " `font-display: swap`) for flag rendering on Windows 10 |",

    "| Fonts | Golos Text — self-hosted variable woff2, cyrillic + latin subsets"
    " (CSP `default-src 'self'` blocks Google Fonts) · Twemoji Country Flags WOFF2"
    " (78 KB, unicode-range scoped) for flag rendering on Windows 10 |",
)


def main() -> None:
    if not README.exists():
        raise SystemExit(f"ABORT: {README} not found — run from the repo root.")

    text = README.read_text(encoding="utf-8")
    print("README findings patch" + ("  (DRY RUN)" if DRY else ""))
    print()

    for label, old, new in EDITS:
        n = text.count(old)
        if n == 1:
            text = text.replace(old, new, 1)
            print(f"  OK    {label}")
        elif n == 0 and new[:60] in text:
            print(f"  --    {label} (already applied)")
        else:
            raise SystemExit(
                f"\nABORT: anchor for {label!r} matched {n} times (expected 1).\n"
                "       Nothing written — README.md has drifted."
            )

    if DRY:
        print("\nDry run — nothing written.")
        return

    README.write_text(text, encoding="utf-8")
    print("\nDone.  Review:  git diff README.md")


if __name__ == "__main__":
    main()
