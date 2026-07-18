# SaveCheck — Реална ли е промоцията?

![SaveCheck OG image](docs/og.svg)

**SaveCheck** проверява дали промоцията в супермаркета е истинска или маркетингова измама. Сравнява текущата цена на всеки конкретен продукт с 90-дневната му история и прилага логиката на **EU Omnibus директива (чл. 6а)** — референцията е не „старата цена" от етикета, а реалното дъно за последните 30 дни преди промоцията.

🔗 **Live demo:** [real365.store](https://real365.store)

---

## Как работи

```
КЗП open data (kolkostruva.bg)
        │  ZIP с CSV по вериги, всеки ден
        ▼
scripts/gen_demo_data.py  ──►  docs/products.js             (product-first snapshot)
                          ──►  docs/products-history.js     (90-дневна история per оферта)
                          ──►  docs/data.js                 (22-категорийна легенда, legacy)
scripts/gen_brochures.py  ──►  docs/brochures.js            (седмични промоции с fallback)
        │
        ▼  (GitHub Actions, всеки ден 10:00 UTC / 13:00 EET)
GitHub Pages auto-deploy ──► Live сайт
```

**Core module:** [`src/savecheck/pricing/snapshot.py`](src/savecheck/pricing/snapshot.py) — `compute_snapshot(offering, ref)` е single source of truth. И `gen_demo_data.py` (products.js), и `gen_brochures.py` (brochures.js) използват точно същата функция за да изчислят verdict-a на всеки продукт. Това гарантира, че броят real deals в Home и броят green items в брошурата за същата верига **винаги съвпадат**.

За всяка оферта (продукт × верига) се изчислява **Omnibus state**:

| State | Значение |
|-------|----------|
| 🟢 **real** | Промо цената е под най-ниската от последните 30 дни — реална икономия |
| 🟡 **cosmetic** | Има малка отстъпка спрямо 90-дневната медиана, но не значителна |
| 🔴 **fake** | Обявена промоция, но цената НЕ е под 30-дневното дъно — маркетинг |
| ⚪ **unverified** | Обявена промоция, но има под 3 наблюдения за 30 дни — недостатъчна история |
| **regular** | Не е обявена като промо (без иконка на картите) |

Присъдата се смята **поотделно за всеки конкретен продукт в конкретна верига**, срещу собствената му 90-дневна крива — не срещу блендната категория. Така 400-грамов кашкавал „Домлян БДС" в Kaufland се сравнява със себе си от вчера, не с най-евтиния кашкавал в категорията.

---

## Функционалности

### 🏠 Начало

- **Hero карта** — реалните спестявания в кошницата ти (retail − price)
- **Fake hook** — „N подвеждащи промоции (последните 30 дни)"
- **Търсене** (глобално, пише се където и да си, скача те в Начало)
- **Филтър по верига** (chips) + бутон **× за изчистване на search-a**
- **Топ 6 реални промоции**, подредени по omnibus % desc
- **Бутон „Виж всички N реални промоции"** — разширява до 50 items
- **Мини класация „Битката на титаните"** — коя верига лъже най-често

### Детайл модал на продукт

- Име, верига, KZP категория
- Badge за state с обяснение
- Разграничение на процентите:
  - **„Реално −N%"** (зелен, спрямо 90-дневната медиана)
  - **„Обявено на етикета −N%"** (сив, спрямо retail) — показва се само когато двата се различават
- 90-дневна графика на цената (промо дни в червено, обичайни в тъмно сиво). Данните се зареждат lazy (~1 сек) от `products-history.js`.
- Stale маркер „от dd.m" ако цената е от преди днешния snapshot

### 🛒 Кошница

- **+/− количество** на всеки item
- **Общо** и **Спестяваш спрямо етикета** (сумите скалират с количеството)
- Разбивка **по вериги** (само информативно — не сравняваме между веригите, защото един и същ продукт има различен код в различните вериги)

### 🏷️ Промоции (брошури)

- Всички промо оферти тази седмица, по верига (секциите свити по подразбиране)
- Верифицирани срещу собствената 90-дневна история на всеки конкретен продукт
- При липсваща верига за деня — fallback до 3 дни назад с маркер „от dd.m"
- **Битката на титаните** — класация коя верига лъже най-често (втори таб)

### Общи UX

- **Escape** затваря модала
- **„Първите 30 от N"** в search резултатите — ясно е, че виждаш само част
- **Auto-refresh** на Home hero и кошница когато добавяш/маха продукти
- **HTML escape** на всички КЗП имена преди render (защита от stored XSS)

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

`gen_demo_data.py` работи в **product-first** модел: индексира **всеки** продукт в КЗП feed-а като `(product_key, chain)` двойка. `product_key` използва `product_code` когато е наличен, иначе нормализирано име (lowercase + collapsed whitespace + trailing punct стрипнат). За текущия dataset това дава около **5700 уникални оферти** от 5 вериги.

Filter: минимум 3 наблюдения в последните 30 дни (drop-ва еднократни flyer items които не са част от асортимента).

Три output-a се генерират в един pass:

- **`products.js`** — compact current-snapshot: name, chain, price, retail, is_promo, state, omnibus_pct, KZP category, BASKET category tags (0..N). ~1.8 MB.
- **`products-history.js`** — full 90-day price history per оферта, в компактен `[day_offset, price, is_promo]` формат. Nested `{product_key: {chain: [[o,p,s], ...]}}`. Loaded lazy при първо отваряне на детайл-модал. ~6 MB uncompressed / 0.87 MB gzip.
- **`data.js`** — legacy 22-категорийна витрина, реконструирана от product-first index-a. Захранва Битката на титаните и остатъчна легенда.

`gen_brochures.py` използва същия `load_all_products` + `compute_snapshot` pipeline, филтрира по `is_promo=True` at REF, сортира по basket-first → omnibus_pct desc → cap 500 per chain.

---

## Валута

Приложението работи **native в EUR**. КЗП feed-а вече публикува цените в EUR (след адопцията на еврото от 01.01.2026), затова UI-ят не прави никаква конверсия.

---

## Tech stack

| Layer | Технология |
|-------|------------|
| Frontend | Single-file HTML/CSS/JS (vanilla, no framework), ~155 KB |
| Charts | Chart.js 4.4 (jsDelivr CDN, sync) |
| Data | `window.SAVECHECK_PRODUCTS` (snapshot) + `window.SAVECHECK_HISTORY` (lazy) + `window.SAVECHECK_BROCHURES` + `window.SAVECHECK_DEMO` (legacy) |
| Backend | Python 3.11+ (`src/savecheck/`) |
| Pricing engine | `savecheck.pricing` — `evaluate_series()`, `compute_stats()`, `compute_snapshot()` |
| Ingest | `savecheck.ingest.kolkostruva` — парсва КЗП CSV |
| CI/CD | GitHub Actions (daily cron 10:00 UTC) + GitHub Pages (auto-deploy on push към main) |

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

# 4. Генерирай data files
python scripts/gen_demo_data.py --zip-dir /tmp/kzp_zips
python scripts/gen_brochures.py --zip-dir /tmp/kzp_zips

# 5. Отвори в браузър
open docs/index.html
# или: python -m http.server 8000 -d docs
```

### Тестове

```bash
pytest tests/ -v
```

57 unit тестове (aggregates, verdict, snapshot, history, alerts, ingest parser).

---

## Автоматично обновяване

`.github/workflows/daily-refresh.yml` — стартира всеки ден в **10:00 UTC (13:00 EET)**:

1. Изтегля последните ZIP-ове от КЗП (кеширва ги за седмицата)
2. Пуска `gen_demo_data.py` → `docs/data.js`, `docs/products.js`, `docs/products-history.js`
3. Пуска `gen_brochures.py` → `docs/brochures.js`
4. `git commit && git push` ако има промени
5. GitHub Pages автоматично деплойва новия commit на `https://real365.store`

След промяна в `gen_demo_data.py` / `gen_brochures.py` / `snapshot.py` е нужно този workflow да се пусне ръчно (Actions → Run workflow), за да се видят новите полета в живите данни — cron-ът не подхваща веднага код, качен между две планирани обновявания.

Cron времето (10:00 UTC) е избрано защото КЗП понякога публикува feed-а по-късно сутринта. Ако workflow-ът тръгне преди КЗП да е публикувал днешния файл, ще ползва последния наличен и REF може да бъде вчера.

---

## Структура

```
SaveCheck/
├── docs/
│   ├── index.html                # Цялото приложение (single-file)
│   ├── data.js                   # Legacy 22-cat снимка (SAVECHECK_DEMO)
│   ├── products.js               # Product-first snapshot (SAVECHECK_PRODUCTS)
│   ├── products-history.js       # 90-day history, lazy loaded (SAVECHECK_HISTORY)
│   ├── brochures.js              # Седмични промоции (SAVECHECK_BROCHURES)
│   └── og.svg                    # Open Graph image
├── src/savecheck/
│   ├── pricing/
│   │   ├── snapshot.py           # compute_snapshot() — SINGLE SOURCE OF TRUTH
│   │   ├── verdict.py            # evaluate_series() — Omnibus логика
│   │   ├── aggregates.py         # compute_stats() — 30/90-дневни статистики
│   │   ├── history.py            # build_chart() — chart series builder
│   │   └── alerts.py             # evaluate_watch() — price watch alerts
│   ├── ingest/
│   │   └── kolkostruva.py        # Парсване на КЗП CSV
│   └── shopping/                 # Shopping list logic (за bg fridge feature)
├── scripts/
│   ├── gen_demo_data.py          # Генерира data.js + products.js + products-history.js
│   └── gen_brochures.py          # Генерира brochures.js (използва shared snapshot)
├── tests/
│   ├── test_snapshot.py          # 15 теста за shared snapshot
│   ├── test_verdict.py
│   ├── test_aggregates.py
│   ├── test_history.py
│   ├── test_alerts.py
│   ├── test_shopping_list.py
│   └── test_ingest_parser.py
└── .github/workflows/
    └── daily-refresh.yml
```

---

## Данни и лиценз

Ценовите данни са от [КЗП „Колко струва"](https://kolkostruva.bg/opendata) — публичен регистър на цените, поддържан от Комисията за защита на потребителите на Р. България.

Кодът е с отворен лиценз — **MIT**.
