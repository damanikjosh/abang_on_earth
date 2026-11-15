#!/usr/bin/env python3
"""the real Harmonized VIIRS layer in the app (all 115 months, Indonesia box + northern box). BUILT app or live site.
  uv run --with playwright python scripts/check_harm86.py [base_url]
Row name and badge, the (i) panel (important block first, coverage names the countries, not 'Indonesia only'), Night box hides the layer, Day box disabled, draws in 2002-09 over Kalimantan and in 2004-03 over Thailand/Myanmar (northern box),
months outside 2002-07..2012-01 say so in the panel, no console errors, 390 and 1440 px, light and dark."""
import sys
from playwright.sync_api import sync_playwright
BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:4173/").rstrip("/") + "/"
fails = []
def need(c, m):
    print(("ok   " if c else "FAIL ") + m, flush=True)
    if not c: fails.append(m)
def ready(pg): pg.wait_for_function("window.__appReady===true", timeout=90000)
def settle(pg):
    pg.wait_for_timeout(500)
    try: pg.evaluate("new Promise(r=>{const m=window.__map; if(m.loaded()&&!m.isMoving()) return r(); m.once('idle',r)})")
    except Exception: pass
    pg.wait_for_timeout(1200)
def load(pg, h):
    pg.goto("about:blank"); pg.goto(BASE + "app/" + h); ready(pg); settle(pg)
def pts(pg, m): return pg.evaluate("(l)=>__map.getLayer(l)?__map.queryRenderedFeatures({layers:[l]}).length:-1", f"fire-harm-{m}-pts")
with sync_playwright() as p:
    b = p.chromium.launch(args=["--use-gl=swiftshader", "--enable-unsafe-swiftshader"])
    for (w, h, tg) in ((390, 844, "phone"), (1440, 900, "desk")):
        for scheme in ("light", "dark"):
            name = f"{tg}-{scheme}"
            ctx = b.new_context(viewport={"width": w, "height": h}, color_scheme=scheme); pg = ctx.new_page(); errs = []
            pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None); pg.on("pageerror", lambda e: errs.append(str(e)))
            load(pg, "#m=2002-09&r=all&k=viirs_raw&s=fire-harm&v=113.5,-1.8,9.5&t=layers")
            row = pg.locator('#onmap .lp-row[data-id="fire-harm"]')
            need(row.locator(".lp-name").inner_text() == "Harmonized VIIRS" and "important information" in (row.locator(".lp-info").get_attribute("aria-label") or ""), f"{name}: row 'Harmonized VIIRS' with the important-information badge")
            need(pg.locator("#lyr-fire-harm input[data-cls='1']").is_disabled() and pg.locator("#lyr-fire-harm input[data-cls='2']").is_checked(), f"{name}: Day greyed out, Night ticked")
            n = pts(pg, "2002-09"); need(n > 0, f"{name}: 2002-09 over Central Kalimantan: {n} harmonized points on screen")
            row.locator(".lp-info").scroll_into_view_if_needed(); row.locator(".lp-info").click(); pg.wait_for_timeout(300)
            first = pg.evaluate("document.querySelector('.lp-pop .lp-pop-body').firstElementChild.className"); txt = pg.locator(".lp-pop").inner_text(); cov = pg.locator('.lp-pop .lp-pop-sec', has_text="Coverage").inner_text() if pg.locator('.lp-pop .lp-pop-sec', has_text="Coverage").count() else ""
            need(first == "lp-pop-imp" and "Not NASA VIIRS detections" in txt and "Night only; day is not computed" in txt, f"{name}: (i) starts with the important block carrying the approved sentences")
            need("Indonesia only" not in txt and ("Thailand" in cov or "Thailand" in txt), f"{name}: coverage no longer says Indonesia only and names the northern box countries")
            pg.keyboard.press("Escape")
            box = pg.locator("#lyr-fire-harm input[data-cls='2']"); box.scroll_into_view_if_needed(); box.uncheck(); settle(pg)
            need(pts(pg, "2002-09") <= 0 and "x=fire-harm:2" in pg.url, f"{name}: unticking Night hides the layer (x=fire-harm:2)")
            load(pg, "#m=2004-03&r=all&k=viirs_raw&s=fire-harm&v=100.5,18.5,6.5&t=layers"); n2 = pts(pg, "2004-03")
            need(n2 >= 0 and pg.evaluate("__map.getStyle().layers.filter(l=>l.id.startsWith('fire-harm-2004-03')).length") == 2, f"{name}: 2004-03 (northern box) loads the month's tiles ({n2} points in this view)")
            pg.evaluate("__map.jumpTo({center:[100.0,17.5],zoom:6})"); settle(pg); n3 = pg.evaluate("__map.queryRenderedFeatures({layers:['fire-harm-2004-03-dens']}).length"); need(n3 > 0, f"{name}: 2004-03 over northern Thailand / Myanmar / Laos: {n3} harmonized density cells on screen (the northern box)")
            load(pg, "#m=2015-06&r=all&k=viirs_raw&s=fire-harm&v=113.5,-1.8,9.5&t=layers")
            hrow = pg.locator('#onmap .lp-row[data-id="fire-harm"]'); hrow.locator(".lp-info").scroll_into_view_if_needed(); hrow.locator(".lp-info").click(); pg.wait_for_timeout(300)
            mt = pg.locator('.lp-pop [data-sec="month"] p').inner_text(); imp = pg.locator(".lp-pop .lp-pop-imp").inner_text(); pg.keyboard.press("Escape")
            need(("data" in mt.lower() or "available" in mt.lower()) and mt in imp, f"{name}: 2015-06 (outside the model's months): the panel says '{mt}' in the important block")
            need(pg.evaluate("document.documentElement.scrollWidth<=innerWidth"), f"{name}: no horizontal scroll")
            need(not errs, f"{name}: no console errors" + (f" {errs[:3]}" if errs else ""))
            ctx.close()
    b.close()
print("\nALL OK" if not fails else f"\n{len(fails)} FAILED")
sys.exit(1 if fails else 0)
