#!/usr/bin/env python3
"""keyboard path. BUILT app or live site.
  uv run --with playwright python scripts/check_keyboard.py [base_url]      default http://127.0.0.1:4829/
First Tab = 'Skip to the map controls', visible; Enter moves focus into the dock; the month slider announces 'May 2023'-style text (aria-valuetext) and follows the arrow keys;
the calendar is one image with a label (not a fake grid); every button/select in the dock has an accessible name."""
import sys
from playwright.sync_api import sync_playwright
BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:4829/").rstrip("/") + "/"
fails = []
def need(c, m):
    print(("ok   " if c else "FAIL ") + m, flush=True)
    if not c: fails.append(m)
with sync_playwright() as p:
    b = p.chromium.launch(args=["--use-gl=swiftshader", "--enable-unsafe-swiftshader"]); pg = b.new_page(viewport={"width": 1440, "height": 900})
    pg.goto(BASE + "app/#m=2019-09&f=viirs"); pg.wait_for_function("window.__appReady===true", timeout=90000); pg.wait_for_timeout(1000)
    pg.keyboard.press("Tab")
    need(pg.evaluate("document.activeElement.className") == "skip" and pg.evaluate("document.activeElement.getBoundingClientRect().top") >= 0, "first Tab = skip link, on screen")
    pg.keyboard.press("Enter"); pg.wait_for_timeout(300)
    need(pg.evaluate("!!document.activeElement.closest('#dock')") and "m=2019-09" in pg.evaluate("location.hash"), "Enter moves focus into the dock and keeps the link state in the address bar")
    pg.goto(BASE + "app/#m=2019-09&f=viirs"); pg.wait_for_function("window.__appReady===true", timeout=90000); pg.wait_for_timeout(800)
    stops = []
    for _ in range(7):
        pg.keyboard.press("Tab"); stops.append(pg.evaluate("document.activeElement.className||document.activeElement.id||document.activeElement.tagName"))
    need(not any("maplibregl" in x or x == "CANVAS" for x in stops), f" the first 7 tab stops are the page's own controls, not the map canvas or its links: {stops}")
    need(pg.evaluate("document.querySelectorAll('h1').length") == 1, " the app page has one h1")
    pg.goto(BASE + "app/#m=2019-09&f=viirs"); pg.wait_for_function("window.__appReady===true", timeout=90000); pg.wait_for_timeout(800)
    t0 = pg.get_attribute("#slider", "aria-valuetext"); pg.focus("#slider"); pg.keyboard.press("ArrowLeft"); pg.wait_for_timeout(300); t1 = pg.get_attribute("#slider", "aria-valuetext")
    need(t0 == "Sep 2019" and t1 == "Aug 2019", f"slider valuetext follows the keys ({t0!r} -> {t1!r})")
    need(pg.get_attribute("#cal", "role") == "img" and len(pg.get_attribute("#cal", "aria-label") or "") > 20, "calendar: role=img with a label")
    unnamed = pg.evaluate("[...document.querySelectorAll('#dock button, #dock select, #dock input')].filter(e=>!(e.getAttribute('aria-label')||e.closest('label')?.textContent.trim()||e.textContent.trim()||e.getAttribute('title'))).map(e=>e.outerHTML.slice(0,80))")
    need(not unnamed, f"every control in the dock has a name {unnamed[:2]}")
    b.close()
print("ALL OK" if not fails else f"FAILED {len(fails)}"); sys.exit(1 if fails else 0)
