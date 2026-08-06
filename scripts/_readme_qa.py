#!/usr/bin/env python3
"""One-off: add a QA checklist to the README, and fix the test count.

    python scripts/_readme_qa.py --dry
    python scripts/_readme_qa.py

Every check on the list corresponds to a defect that reached main in
this project. Nothing generic.

The important one is opening things rather than looking at them. The
appbar restyle cleared several rounds of visual review while the
language dropdown was being clipped by overflow:hidden and stacked under
the search field — nine locales unreachable, and nothing on screen
looked wrong, because switching language only needs the first row.

The service worker note is the expensive one. The shell is cache-first,
so skipping the unregister means reviewing yesterday's HTML and
concluding a patch failed. That misdiagnosis happened three times in a
single session.

Delete this file once it has run.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
DRY = "--dry" in sys.argv

ANCHOR = "57 unit тестове (aggregates, verdict, snapshot, history, alerts, ingest parser)."

NEW = """63 unit тестове (aggregates, verdict, snapshot, history, alerts, ingest parser).

### QA преди push

Четири проверки. Всяка от тях е хващала реален дефект в този проект — нито една не е от общ списък.

**Смени езика.** През чипа в хедъра или с `country.lang='ro'; render()` в конзолата. Всеки нов
твърдо зашит низ изскача веднага, защото остава на български, докато всичко около него е на
румънски.

**Отваряй нещата, не само ги гледай.** Падащото меню за език, модалите, всичко, което излиза
извън родителя си. Рестайл може да изглежда безупречно и същевременно да е счупил изрязване или
подредба на слоеве: `overflow:hidden` върху лентата отгоре веднъж отряза езиковото меню и остави
девет от единайсетте локала недостъпни. На екрана нищо не изглеждаше нередно, защото смяната на
език има нужда само от първия ред, а той продължаваше да работи.

**И двете теми, и двете ширини.** Тъмната се пуска с
`document.documentElement.setAttribute('data-theme','dark')`. Ширините са 375 и над 480 — под 480
действа единственото media query в проекта и приложението е на цял екран, без рамка.

**Разкачи service worker-а.** Application → Service Workers → Unregister, или чекни
*Update on reload*. Shell-ът е cache-first, тоест без това преглеждаш вчерашния HTML и стигаш до
извода, че промяната не е приложена. Тази погрешна диагноза се случи три пъти в една сесия и
костваше повече време от всичко друго."""


def main() -> None:
    if not README.exists():
        raise SystemExit(f"ABORT: {README} not found — run from the repo root.")

    text = README.read_text(encoding="utf-8")
    print("README QA checklist" + ("  (DRY RUN)" if DRY else ""))
    print()

    if "### QA преди push" in text:
        print("  --  already applied")
        return

    n = text.count(ANCHOR)
    if n != 1:
        raise SystemExit(
            f"\nABORT: anchor matched {n} times (expected 1). Nothing written."
        )

    text = text.replace(ANCHOR, NEW)
    print("  OK    QA checklist added under Локална разработка")
    print("  OK    test count 57 -> 63")

    if DRY:
        print("\nDry run — nothing written.")
        return

    README.write_text(text, encoding="utf-8")
    print("\nDone.  Review:  git diff README.md")


if __name__ == "__main__":
    main()
