#!/usr/bin/env python3
"""the failure paths. BUILT app or live site (requests are blocked in the browser; nothing on the server changes).
  uv run --with playwright python scripts/check_load_failure.py [base_url]      default http://127.0.0.1:4831/
For each core file (manifest.json, regions.geojson, monthly.json, layers.json) blocked in BOTH data folders (404 and network error): the loading overlay turns into the error message
with a 'Try again' button (no spinner left), the banner is set, and after unblocking, 'Try again' brings the app up. Also: one drivers class file 404 -> the row says 6 of 7 classes with one file missing;
with prefers-reduced-motion the Play button stays enabled and steps the month."""
import sys, re
from playwright.sync_api import sync_playwright
BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:4831/").rstrip("/") + "/"
fails = []
def need(c, m):
    print(("ok   " if c else "FAIL ") + m, flush=True)
    if not c: fails.append(m)
with sync_playwright() as p:
    b = p.chromium.launch(args=["--use-gl=swiftshader", "--enable-unsafe-swiftshader"])
    for fname in ("manifest.json", "regions.geojson", "monthly.json", "layers.json"):
        for how in ("404", "abort"):
            ctx = b.new_context(viewport={"width": 390, "height": 844}); pg = ctx.new_page(); on = {"v": True}
            def handler(route):
                if not on["v"]: return route.continue_()
                return route.fulfill(status=404, body="nope") if how == "404" else route.abort()
            pg.route(re.compile(r".*/data-v\d/" + re.escape(fname) + r".*"), handler)
            pg.goto(BASE + "app/"); pg.wait_for_selector("#loading.failed", timeout=60000)
            vis = pg.is_visible("#retry") and "could not be loaded" in pg.inner_text("#loading") and pg.locator("#loading i").count() == 0 and pg.is_visible("#banner")
            need(vis, f"{fname} {how} in both folders: error + Try again, no spinner, banner shown")
            on["v"] = False; pg.click("#retry"); ok = True
            try: pg.wait_for_function("window.__appReady===true", timeout=60000)
            except Exception: ok = False
            need(ok and pg.locator("#loading").count() == 0, f"{fname} {how}: after unblocking, Try again brings the app up")
            ctx.close()
    ctx = b.new_context(viewport={"width": 1440, "height": 900}); pg = ctx.new_page()
    pg.route(re.compile(r".*/drivers/class1\.pmtiles.*"), lambda r: r.fulfill(status=404, body="nope"))
    pg.goto(BASE + "app/#m=2019-09&f=&l=drivers&v=122.15,-2.85,9"); pg.wait_for_function("window.__appReady===true", timeout=90000); pg.wait_for_timeout(4000)
    t = pg.inner_text("#ls-drivers"); need("6 of 7" in t and "1 map file missing" in t, f" class file missing is reported: {t!r}"); ctx.close()
    ctx = b.new_context(viewport={"width": 1440, "height": 900}, reduced_motion="reduce"); pg = ctx.new_page()
    pg.goto(BASE + "app/#m=2019-09&f=viirs"); pg.wait_for_function("window.__appReady===true", timeout=90000)
    need(pg.is_enabled("#play"), " reduced motion: Play is enabled")
    m0 = pg.inner_text("#slv"); pg.click("#play"); pg.wait_for_timeout(1500); pg.click("#play"); m1 = pg.inner_text("#slv")
    need(m0 != m1, f" Play steps the month ({m0} -> {m1})"); ctx.close(); b.close()
print("ALL OK" if not fails else f"FAILED {len(fails)}"); sys.exit(1 if fails else 0)
