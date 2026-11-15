#!/usr/bin/env python3
"""Details card fixes. BUILT app or live site.
  uv run --with playwright python scripts/check_details39.py [base_url]      default http://127.0.0.1:4823/
 Brunei Jan 2008 (VIIRS-equivalent hidden): no 'estimated' flag next to 'not shown'.  all-countries oil palm shows a sum and names the countries without a map;
no percentage from < 20 detections (Jan 2001).  '2025: same-year loss only' is a note under the number, not in the value.  region names tidy (no 'Province', no ALL-CAPS, Sagaing)."""
import sys
from playwright.sync_api import sync_playwright
BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:4823/").rstrip("/") + "/"
fails = []
def need(c, m):
    print(("ok   " if c else "FAIL ") + m, flush=True)
    if not c: fails.append(m)
def load(pg, h):
    pg.goto("about:blank"); pg.goto(BASE + "app/" + h); pg.wait_for_function("window.__appReady===true && window.__studyLoaded===true", timeout=90000); pg.wait_for_timeout(1200)
with sync_playwright() as p:
    b = p.chromium.launch(args=["--use-gl=swiftshader", "--enable-unsafe-swiftshader"]); pg = b.new_page(viewport={"width": 1440, "height": 900})
    load(pg, "#m=2008-01&c=BRN&r=brunei&k=viirs_eq&f=viirs")
    need(pg.inner_text("#d-det") == "not shown" and pg.inner_text("#d-flag").strip() == "", f" Brunei Jan 2008: value 'not shown', flag {pg.inner_text('#d-flag')!r} (empty)")
    load(pg, "#m=2019-09&c=all&r=all&k=viirs_eq&f=viirs")
    t = pg.inner_text("#d-palm")
    need("ha" in t and "of 11 countries" in t and "Laos" in t and "Vietnam" in t, f" all countries 2019 oil palm: {t.replace(chr(10), ' | ')!r}")
    load(pg, "#m=2025-12&c=IDN&r=indonesia&k=viirs_eq&f=viirs")
    t = pg.inner_text("#d-palm"); need(pg.text_content("#d-palm-l") == "Oil palm planted up to 2021" and "ha" in t and "no oil-palm map after 2021" in t, f" Dec 2025: oil palm shows the 2021 value, labelled: {pg.inner_text('#d-palm-l')!r} {t.replace(chr(10), ' | ')!r}")
    need(pg.text_content("#d-loss-l") == "Forest loss in 2025" and pg.text_content("#d-tmf-l") == "Forest cleared 1990 to 2025", f" period in the labels: {pg.inner_text('#d-loss-l')!r}, {pg.inner_text('#d-tmf-l')!r}")
    need(len(pg.inner_text("#d-unit")) > 20, f" unit line under the month: {pg.inner_text('#d-unit')!r}")
    load(pg, "#m=2019-09&c=IDN&r=indonesia&k=viirs_eq&f=viirs")
    t = pg.inner_text("#d-palm"); need(pg.text_content("#d-palm-l") == "Oil palm planted up to 2019" and "no oil-palm map" not in t, f" Sep 2019: label up to 2019, no note ({t!r})")
    need(pg.locator("#d-clm").count() == 0 and pg.locator("#ds-clear").count() == 0, "#86 the forest-loss fire rows and their Details section are gone (checks of those rows removed with them)")
    names = pg.evaluate("[...document.querySelectorAll('#region option')].map(o=>o.textContent)")
    load(pg, "#c=THA&r=thailand&k=viirs_eq&f=viirs"); tha = pg.evaluate("[...document.querySelectorAll('#region option')].map(o=>o.textContent)")
    load(pg, "#c=SGP&r=singapore&k=viirs_eq&f=viirs"); sgp = pg.evaluate("[...document.querySelectorAll('#region option')].map(o=>o.textContent)")
    load(pg, "#c=MMR&r=myanmar&k=viirs_eq&f=viirs"); mmr = pg.evaluate("[...document.querySelectorAll('#region option')].map(o=>o.textContent)")
    need(not any(n.endswith(" Province") for n in tha) and any(n == "Roi Et" for n in tha), f" Thailand names tidy ({len(tha)} options, no ' Province')")
    need(not any(n == n.upper() and len(n) > 4 and any(c.isalpha() for c in n) for n in sgp), f" Singapore regions not ALL-CAPS: {sgp[1:4]}")
    need("Sagaing" in mmr and "Saigang" not in mmr, " Myanmar: Sagaing spelled right")
    b.close()
print("ALL OK" if not fails else f"FAILED {len(fails)}"); sys.exit(1 if fails else 0)
