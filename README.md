# SaveCheck — Реална ли е промоцията?

![SaveCheck OG image](public/og.svg)

**SaveCheck** проверява дали промоцията е истинска или измамна, като сравнява текущата цена с 90-дневната история. Прилага логиката на **EU Omnibus директива (чл. 6а)** — референцата е не „старата цена" от етикета, а реалното дъно за последните 30 дни.

🔗 **Live demo:** `save-check-murex.vercel.app`

---

## Как работи

```
КЗП open data (kolkostruva.bg)
        │  ZIP с CSV по вериги, всеки ден
        ▼
gen_demo_data.py  ──►  public/data.js               (22-категорийна витрина, legacy)
                  ──►  public/products.js           (product-first snapshot)
                  ──►  public/products-history.js   (90-дневна история per оферта)
gen_brochures.py  ──►  public/brochures.js          (седмични промоции с fallback)
        │
        ▼  (GitHub Actions, всеки ден 08:00 EET)
Vercel auto-deploy ──► Live сайт
```

За всяка оферта (продукт × верига) се изчислява **Omnibus state**:

| State | Значение |
|-------|----------|
| 🟢 **real** | Цената е под най-ниската за последните 30 дни — реална икономия |
| 🟡 **cosmetic** | Малка отстъпка спрямо медианата, но не значителна |
| 🔴 **fake** | Обявена промоция, но цената НЕ е под 30-дневното дъно |
| ⚪ **unverified** | Обявена промоция, но има под 3 наблюдения за 30 дни |
| **regular** | Не е обявена като промо (без иконка на карти-те) |

Присъдата се смята **поотделно за всеки конкретен продукт в конкретна верига**, срещу собствената му 90-дневна крива — не срещу блендната категория. Така 400-грамов кашкавал „Домлян БДС" в Kaufland се сравнява със себе си от вчера, не с най-евтиния кашкавал в категорията.

---

## Функционалности

- **🏠 Начало** — hero с реалните спестявания (акварелен банер) + лента-кука „**N подвеждащи промоции**" (последните 30 дни) + **търсене** и **филтър по верига** над списъка с топ реални промоции (6 бр., подредени по omnibus %) + мини класация на Титаните
- **Click на карта** → отваря детайл-модал с product name, chain, badge за state + обяснение, current price + retail + omnibus %, и **90-дневна графика на цената** (промо дни в червено, обичайни в тъмно сиво). Графиката се захранва от `products-history.js`, който се зарежда lazy при първия click (~1 сек, 6 MB → 0.87 MB gzip).
- **Търсене** — глобална търсачка (пише се където и да си, скача те в Начало). Пише „кашкавал" → показва всички кашкавали (5956 продукта общо), подредени по state (real → cosmetic → regular → unverified → fake), после по цена.
- **🏷️ Промоции** — всички промо оферти тази седмица по верига (секциите са свити по подразбиране), верифицирани срещу собствената история на всеки конкретен продукт. При липсваща верига за деня — fallback до 3 дни назад с маркер „от 13.7". **Битката на Титаните** (класация коя верига лъже най-много) е втори таб.
- **🛒 Пазарувай** — legacy 22-продуктова кошница с филтър по верига и по verdict (постепенно ще бъде премахнат в полза на глобалната търсачка + кошница в модалa)
- **10 езика** — BG, SR, MK, RO, EL, TR, SQ, BS, HR, SL

> Скенерът за баркод и таб „Рецепти" съществуват в кодовата база, но са скрити в текущия MVP интерфейс.

---

## Data pipeline

```
kolkostruva.bg/opendata_files/YYYY-MM-DD.zip
    └── ЛидлБългария_*.csv
    └── Kaufland_*.csv
    └── BILLA_*.csv
    └── ФАНТАСТИКО_*.csv
    └── Т МАРКЕТ_*.csv
```

Всеки ZIP съдържа по един CSV на верига с колони:
`Населено място, Търговски обект, Наименование, Код, Категория, Цена на дребно, Цена в промоция`

Когато `Цена в промоция` е попълнена → `is_promo = True` → се проверява дали е по-евтино от `min_30_prior`.

`gen_demo_data.py` работи в **product-first** модел: индексира **всеки** продукт в КЗП feed-а (не само 22-те кураторски категории) като `(product_key, chain)` двойка. `product_key` използва `product_code` когато е наличен, иначе нормализирано име (lowercase + collapsed whitespace + trailing punct стрипнат). За текущия dataset това дава **5956 уникални оферти** от 5 вериги.

Три output-a се генерират в един pass:

- **`products.js`** — compact current-snapshot: name, chain, price, retail, is_promo, state, omnibus_pct, KZP category, BASKET category tags (0..N). Filter: минимум 3 наблюдения за последните 30 дни. ~1.8 MB.
- **`products-history.js`** — full 90-day price history per оферта, в компактен `[day_offset, price, is_promo]` формат. Nested `{product_key: {chain: [[o,p,s], ...]}}`. Loaded lazy при първо отваряне на детайл-модал. ~6 MB uncompressed / 0.87 MB gzip.
- **`data.js`** — legacy 22-категорийна витрина, реконструирана от product-first index-a чрез „най-евтин мач на ден на верига". Захранва Пазарувай tab-а до неговото пълно премахване.

---

## Tech stack

| Layer | Технология |
|-------|------------|
| Frontend | Single-file HTML/CSS/JS (vanilla, no framework) |
| Charts | Chart.js 4.4 |
| Barcode | Native `BarcodeDetector` + [ZXing](https://github.com/zxing-js/library) 0.21 fallback (в кода, скрит в текущия UI) |
| Data | `window.SAVECHECK_PRODUCTS` (snapshot) + `window.SAVECHECK_HISTORY` (lazy) + `window.SAVECHECK_BROCHURES` + `window.SAVECHECK_DEMO` (legacy) |
| Backend | Python 3.11+ (`src/savecheck/`) |
| Pricing engine | `savecheck.pricing` — `evaluate_series()`, `compute_stats()` |
| Ingest | `savecheck.ingest.kolkostruva` — парсва КЗП CSV |
| CI/CD | GitHub Actions (daily cron) + Vercel (auto-deploy on push) |
| Barcode lookup | [Open Food Facts API](https://world.openfoodfacts.org/api/v2/) |

---

## Локална разработка

```bash
# 1. Clone
git clone https://github.com/Tems-git/SaveCheck.git
cd SaveCheck

# 2. Python env
python -m venv .venv && source .venv/bin/activate
pip install -e ".[ingest]"

# 3. Изтегли данни (последните 91 дни)
mkdir -p /tmp/kzp_zips
for i in $(seq 0 90); do
  D=$(date -d "$i days ago" +%Y-%m-%d)
  curl -fsSL -A "Mozilla/5.0" \
    "https://kolkostruva.bg/opendata_files/${D}.zip" \
    -o "/tmp/kzp_zips/${D}.zip" 2>/dev/null || true
done

# 4. Генерирай data files (data.js + products.js + products-history.js)
python scripts/gen_demo_data.py --zip-dir /tmp/kzp_zips
python scripts/gen_brochures.py --zip-dir /tmp/kzp_zips

# 5. Отвори в браузър
open public/index.html
# или: python -m http.server 8000 -d public
```

### Тестове

```bash
pytest tests/ -v
```

---

## Автоматично обновяване

`.github/workflows/daily-refresh.yml` — стартира всеки ден в 08:00 EET (05:00 UTC):

1. Изтегля последните ZIP-ове от КЗП (кеширва ги за седмицата)
2. Пуска `gen_demo_data.py` → `public/data.js`, `public/products.js`, `public/products-history.js`
3. Пуска `gen_brochures.py` → `public/brochures.js`
4. `git commit && git push` ако има промени
5. Vercel автоматично деплойва новия commit

След промяна в `gen_demo_data.py`/`gen_brochures.py` е нужно този workflow да се пусне ръчно (Actions → Run workflow), за да се видят новите полета в живите данни — cron-ът сам по себе си не подхваща веднага код, качен между две планирани обновявания.

---

## Структура

```
SaveCheck/
├── public/
│   ├── index.html                # Цялото приложение (single-file)
│   ├── data.js                   # Legacy 22-cat снимка (SAVECHECK_DEMO)
│   ├── products.js               # Product-first snapshot (SAVECHECK_PRODUCTS)
│   ├── products-history.js       # 90-day history, lazy loaded (SAVECHECK_HISTORY)
│   ├── brochures.js              # Седмични промоции (SAVECHECK_BROCHURES)
│   └── og.svg                    # Open Graph image
├── src/savecheck/
│   ├── pricing/
│   │   ├── verdict.py            # evaluate_series() — Omnibus логика
│   │   └── aggregates.py         # compute_stats() — 30/90-дневни статистики
│   └── ingest/
│       └── kolkostruva.py        # Парсване на КЗП CSV
├── scripts/
│   ├── gen_demo_data.py          # Генерира data.js + products.js + products-history.js
│   └── gen_brochures.py          # Генерира brochures.js
├── tests/
└── .github/workflows/
    └── daily-refresh.yml
```

---

## Данни и лиценз

Ценовите данни са от [КЗП „Колко струва"](https://kolkostruva.bg/opendata) — публичен регистър на цените, поддържан от Комисията за защита на потребителите на Р. България.

Кодът е с отворен лиценз — **MIT**.
