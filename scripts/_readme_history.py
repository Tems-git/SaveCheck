#!/usr/bin/env python3
"""One-off: add a decision-log section to the README.

    python scripts/_readme_history.py --dry
    python scripts/_readme_history.py

WHY A DECISION LOG AND NOT A CHANGELOG
    A list of commits duplicates git log and helps nobody. What is
    expensive to lose is the reasoning: why the rename stopped at
    user-facing strings, why the font is vendored, why chain marks
    appear in exactly one place, and above all what was measured and
    abandoned. The design mockup still shows a chain-ranking home
    screen; without a written record that it was ruled out on evidence,
    the obvious next move keeps looking like "build it".

    Wrong turns are included on purpose. A confident hypothesis that
    the data contradicted is precisely what someone re-suspects later.

Inserted before the licence section. Delete this script afterwards.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
DRY = "--dry" in sys.argv

ANCHOR = "## Данни и лиценз"

HISTORY = """## История

Дневник на решенията: какво е направено, защо, и — по-важното — какво е отхвърлено и на
какво основание. Целта е следваща сесия да не преоткрива затворени въпроси. Подробностите
за всяка промяна са в commit съобщенията; тук стоят само решенията. Нов запис се добавя
най-отгоре.

### 06.08.2026 — Измервания преди строеж

Три read-only анализа (`scripts/analyze_*.py`) затвориха два roadmap елемента и отвориха трети.

**Cross-chain matching — отпадна окончателно.** Измерено, не предположено: 4310 оферти, нула
съвпадения по продуктов код между вериги, 15 групи по нормализирано име. Всичките са маркова
пакетирана стока. Заедно с него отпада и класацията на вериги по цена на кошницата, която е
началният екран в дизайна.

**Категорийна кошница — приета като път, отложена като работа.** „Къде е най-евтино" минава
през 22-те BASKET категории, а не през конкретни продукти. Възможно, но не преди нормализация
на разфасовките: сега се сравнява масло 125 г срещу 250 г и пилешко бутче срещу филе.

**Дял на реалните промоции — отворен въпрос.** Петдесеткратна разлика между Kaufland (20.2%) и
Billa (0.4%). Ако е артефакт от различно попълване към КЗП, Битката на Титаните мери грешно нещо.

**Опровергана хипотеза, записана нарочно.** Заподозрях, че Fantastico дублира оферти по
доставчик и това изкривява всички бройки — четири реда „ПЛЕШКА СВИНСКА" от различни производители
на една и съща цена изглеждаха убедително. Измерено: коефициент 1.01x, ефект −2 промоции.
Дублирането е пренебрежимо. Не си струва да се проверява пак.

### 04–05.08.2026 — Real365 и редизайн

Приложението се преименува от SaveCheck на Real365, за да съвпадне с домейна, на който живее
от старта.

**Преименуването е само user-facing.** `window.SAVECHECK_*`, пакетът `src/savecheck/`, префиксът
на SW кеша и ключът `savecheck_lang` остават непроменени — нулева видима полза срещу реален риск
от разсинхрон между Python генераторите и фронтенда.

**Golos Text се хоства локално.** CSP е `default-src 'self'` без собствен `font-src`, тоест
Google Fonts би бил блокиран. Вариативен woff2, по един файл на unicode subset. Гръцки няма —
шрифтът не поддържа гръцка азбука и EL локалът пада на системен.

**Дебелините са капнати на 800.** Golos носи чувствително повече мастило от Segoe UI и на 900
върху наситен фон отворите на буквите се запълват; надписите изглеждат размазани. Изолирано чрез
подмяна само на дебелината, при непроменен шрифт.

**Чиповете за вериги са само във филтърния ред.** Дизайнът ги слага навсякъде, но приложението
харчи целия си цветови бюджет за присъдата — зелено реална, амбър слаба, червено фалшива.
Kaufland и Billa са червени марки, Fantastico е амбър. До индикатор за присъда цветът се чете
като присъда.

**Началният екран от дизайна не е построен** — изисква cross-chain, който по-късно отпадна.

### 02–04.08.2026 — Надеждност на pipeline-а

**Инцидент: сайтът стоя с четиридневни данни.** Един осакатен CSV от КЗП — незавършена multi-byte
последователност в края — вдигаше `UnicodeDecodeError`, който събаряше целия дневен pipeline
преди commit стъпката. Три последователни cron пускания се провалиха, без нищо да сигнализира
навън. Ingest-ът вече понася такива файлове с lossy fallback и предупреждение в лога.

**ZIP-овете се валидират преди кеширане.** `curl -f` хваща HTTP грешки, но не и прекъснат по
средата отговор — частичен файл влизаше в седмичния кеш и го тровеше до изтичането му.

**Cloudflare заобикаля кеша за данните.** Четирите data файла минават с Bypass cache правило.
Преди това edge кешът държеше стар snapshot с дни, независимо какво комитваше cron-ът — и точно
това маскираше инцидента по-горе.

**Disclaimer за покритието.** Потребител видя диня на промоция в магазина и не я намери в
приложението. КЗП покрива само регулираната потребителска кошница; сезонните стоки не влизат в
подаването. Записано в info модала на 11 езика, за да не изглежда като дефект.

### До 27.07.2026

Архитектурата, описана по-горе в този документ, е резултат от по-ранна работа: product-first
модел, споделен `compute_snapshot`, outlier филтър, verdict-first подредба на брошурите, i18n на
11 езика, PWA със service worker, Cloudflare security headers. Подробностите са в `git log`.

---

"""


def main() -> None:
    if not README.exists():
        raise SystemExit(f"ABORT: {README} not found — run from the repo root.")

    text = README.read_text(encoding="utf-8")
    print("README history patch" + ("  (DRY RUN)" if DRY else ""))
    print()

    if "## История" in text:
        print("  --  section already present — nothing to do")
        return

    n = text.count(ANCHOR)
    if n != 1:
        raise SystemExit(
            f"ABORT: anchor {ANCHOR!r} matched {n} times (expected 1).\n"
            "       Nothing written."
        )

    text = text.replace(ANCHOR, HISTORY + ANCHOR, 1)
    print(f"  OK  inserted '## История' before '{ANCHOR}'")
    print(f"      {HISTORY.count(chr(10))} lines, 4 dated entries")

    if DRY:
        print("\nDry run — nothing written.")
        return

    README.write_text(text, encoding="utf-8")
    print("\nDone.  Review:  git diff README.md")


if __name__ == "__main__":
    main()
