"""Tests for the real КЗП kolkostruva parser. Pure stdlib; no network needed."""

from __future__ import annotations

import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from savecheck.ingest.kolkostruva import (  # noqa: E402
    chain_name_from_filename,
    parse_chain_csv,
)

DAY = date(2026, 6, 12)

REAL_CSV = (
    '"Населено място","Търговски обект","Наименование на продукта",'
    '"Код на продукта","Категория","Цена на дребно","Цена в промоция"\n'
    '"14218","114 - Габрово/ул. Свищовска 68","Слънчогледово олио 1Л","6810910","42","2.04",""\n'
    '"68134","Ф01 - ОБОРИЩЕ","Прясно мляко 1Л","001102","6","2.19","1.89"\n'
    '"68134","Ф01 - ОБОРИЩЕ","","000000","6","9.99",""\n'  # nameless -> skipped
)


def test_chain_name_from_filename():
    assert chain_name_from_filename("Лидл България_131071587.csv") == "Лидл България"
    assert chain_name_from_filename(
        "ФАНТАСТИКО (ФАНТАСТИКО ГРУП ООД)_206255903.csv"
    ) == "ФАНТАСТИКО"
    assert chain_name_from_filename("eBag (Кънвиниънс АД)_204786976.csv") == "eBag"


def test_parse_skips_nameless_rows():
    rows = list(parse_chain_csv(REAL_CSV, "Лидл", DAY))
    assert len(rows) == 2


def test_retail_row_is_not_promo():
    rows = list(parse_chain_csv(REAL_CSV, "Лидл", DAY))
    oil = rows[0]
    assert oil.chain_name == "Лидл"
    assert oil.product_name == "Слънчогледово олио 1Л"
    assert oil.price == Decimal("2.04")
    assert oil.is_promo is False
    assert oil.observed_on == DAY


def test_promo_row_uses_promo_price():
    rows = list(parse_chain_csv(REAL_CSV, "Фантастико", DAY))
    milk = rows[1]
    assert milk.is_promo is True
    assert milk.price == Decimal("1.89")  # shopper pays the promo price
    assert milk.retail_price == Decimal("2.19")
    assert milk.product_code == "001102"


def test_metadata_fields_captured():
    rows = list(parse_chain_csv(REAL_CSV, "Лидл", DAY))
    assert rows[0].region == "14218"
    assert rows[0].store == "114 - Габрово/ул. Свищовска 68"
    assert rows[0].category == "42"


def test_bytes_with_bom_decode():
    rows = list(parse_chain_csv(REAL_CSV.encode("utf-8-sig"), "Лидл", DAY))
    assert len(rows) == 2


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
