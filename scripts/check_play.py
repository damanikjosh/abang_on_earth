"""Play the timeline for a few months with fire layers on; no console errors, one fire source per sensor after it settles."""
import sys
from playwright.sync_api import sync_playwright
BASE = sys.argv[1]
with sync_playwright() as p:
    b = p.chromium.launch(args=["--use-gl=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"])
    pg = b.new_page(viewport={"width": 1440, "height": 900}); errs = []
    pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(BASE + "app/#m=2015-06&r=indonesia&k=viirs_raw"); pg.wait_for_function("window.__appReady===true"); pg.wait_for_timeout(1500)
    pg.click("#play"); pg.wait_for_timeout(6000); pg.click("#play"); pg.wait_for_timeout(2500)
    m = pg.inner_text("#slv")
    srcs = pg.evaluate("Object.keys(window.__map.getStyle().sources).filter(s=>s.startsWith('fire-'))")
    vis = pg.evaluate("window.__map.getStyle().layers.filter(l=>l.id.startsWith('fire-')&&l.paint&&(l.paint['fill-opacity']||l.paint['circle-opacity'])).length")
    print("stopped at", m, "fire sources", srcs, "errors", errs[:3])
    print("PASS" if not errs and len(srcs) <= 6 else "FAIL")
    b.close()
