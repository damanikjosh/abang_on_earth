#!/usr/bin/env python3
"""head tags and first screen. BUILT app or live site.
  uv run --with playwright python scripts/check_home39.py [base_url]      default http://127.0.0.1:4826/
Home: title and description say Southeast Asia (not Indonesia), og:description + twitter:card + favicon link present, favicon file answers, 'Open the map' fully inside the 390x844 fold,
no horizontal scroll. App: description + favicon; the loading state exists in the HTML before the app starts and is gone when it is ready. Credits: description + favicon."""
import sys, re, urllib.request
from playwright.sync_api import sync_playwright
BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:4826/").rstrip("/") + "/"
fails = []
def need(c, m):
    print(("ok   " if c else "FAIL ") + m, flush=True)
    if not c: fails.append(m)
with sync_playwright() as p:
    b = p.chromium.launch(args=["--use-gl=swiftshader", "--enable-unsafe-swiftshader"])
    ctx = b.new_context(viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True); pg = ctx.new_page()
    pg.goto(BASE); pg.wait_for_timeout(1500)
    meta = lambda sel: pg.evaluate(f"document.querySelector('{sel}')?.content||''")
    need("Southeast Asia" in pg.title() and "Indonesia" not in pg.title(), f"home title: {pg.title()!r}")
    need("Southeast Asia" in meta("meta[name=description]") and "Indonesia" not in meta("meta[name=description]"), "home description says Southeast Asia")
    need("Southeast Asia" in meta('meta[property="og:title"]') and "Southeast Asia" in meta('meta[property="og:description"]') and meta('meta[name="twitter:card"]') == "summary", "og:title, og:description, twitter:card")
    href = pg.evaluate("document.querySelector('link[rel=icon]')?.getAttribute('href')||''"); need(href.endswith("favicon.svg"), f"favicon link {href!r}")
    need(urllib.request.urlopen(BASE + "favicon.svg").status == 200, "favicon.svg answers")
    r = pg.evaluate("(()=>{const r=document.querySelector('.ctas .pill.solid').getBoundingClientRect();return [r.top,r.bottom]})()")
    need(r[1] <= 844, f"'Open the map' inside the 390x844 fold (bottom {r[1]:.0f})")
    need(pg.evaluate("document.documentElement.scrollWidth") <= 390, "no horizontal scroll")
    pg.evaluate("document.querySelector('#shot img').scrollIntoView()"); pg.wait_for_timeout(800)
    need(pg.evaluate("document.querySelector('#shot img').naturalWidth") == 1440 and pg.evaluate("document.querySelector('#shot img').alt.length") > 20, "home: app screenshot loads (1440 px wide) and has alt text")
    html = urllib.request.urlopen(BASE + "app/").read().decode()
    need('id="loading"' in html and "Loading map and data" in html, "app HTML carries the loading state (visible before JS)")
    pg.goto(BASE + "app/"); pg.wait_for_function("window.__appReady===true", timeout=90000)
    need(pg.evaluate("!document.getElementById('loading')") and pg.evaluate("document.body.dataset.ready") == "1", "loading state removed when the app is ready")
    need("favicon" in pg.evaluate("document.querySelector('link[rel=icon]')?.href||''") and meta("meta[name=description]") != "", "app: favicon + description")
    pg.goto(BASE + "credits/"); need("favicon" in pg.evaluate("document.querySelector('link[rel=icon]')?.href||''") and meta("meta[name=description]") != "", "credits: favicon + description")
    b.close()
print("ALL OK" if not fails else f"FAILED {len(fails)}"); sys.exit(1 if fails else 0)
