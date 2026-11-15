#!/usr/bin/env python3
"""map type dropdown (Plain map / Satellite) + Peatland label. BUILT app or live site.
  uv run --with playwright --with pillow --with numpy python scripts/check_basemap.py [base_url] [shot_dir]      default http://127.0.0.1:4173/
At 390x844 and 1440x900, light and dark: the select is labelled and defaults to Plain map; satellite requests the imagery host (none before) and changes the pixels;
the choice is in the link (b=sat), restored on reload, survives a layer toggle, switching back removes it; no console errors; blocked imagery falls back to the plain map with a notice;
the peat row says Peatland, has the hint, and does not wrap badly."""
import sys, io, re, os
from playwright.sync_api import sync_playwright
from PIL import Image
import numpy as np
BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:4173/").rstrip("/") + "/"
SHOTS = sys.argv[2] if len(sys.argv) > 2 else None
HOST = "gibs.earthdata.nasa.gov"
VIEW = "v=113.5,-1.8,6.5"  # Central Kalimantan
fails = []
def need(c, m):
    print(("ok   " if c else "FAIL ") + m, flush=True)
    if not c: fails.append(m)
def px(pg): return np.asarray(Image.open(io.BytesIO(pg.locator("#map").screenshot())).convert("RGB")).astype(float)
def ready(pg): pg.wait_for_function("window.__appReady===true", timeout=90000)
def settle(pg):
    pg.wait_for_timeout(500)
    try: pg.evaluate("new Promise(r=>{const m=window.__map; if(m.loaded()&&!m.isMoving()) return r(); m.once('idle',r)})")
    except Exception: pass
    pg.wait_for_timeout(1500)
with sync_playwright() as p:
    b = p.chromium.launch(args=["--use-gl=swiftshader", "--enable-unsafe-swiftshader"])
    for (w, h, tag) in ((390, 844, "phone"), (1440, 900, "desk")):
        for scheme in ("light", "dark"):
            name = f"{tag}-{scheme}"
            ctx = b.new_context(viewport={"width": w, "height": h}, color_scheme=scheme, device_scale_factor=1); pg = ctx.new_page()
            errs, gibs = [], []
            pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
            pg.on("pageerror", lambda e: errs.append(str(e)))
            pg.on("request", lambda r: gibs.append(r.url) if HOST in r.url else None)
            pg.goto(BASE + "app/#" + VIEW + "&k=viirs_eq&t=layers"); ready(pg); settle(pg)
            sel = pg.get_by_label("Map type")
            need(sel.count() == 1 and sel.is_visible(), f"{name}: 'Map type' select present, visible and labelled")
            need(sel.input_value() == "plain" and [o.inner_text() for o in sel.locator("option").all()] == ["Plain map", "Satellite"], f"{name}: options Plain map / Satellite, default Plain map")
            need(len(gibs) == 0 and "b=sat" not in pg.url, f"{name}: plain map makes no request to {HOST}; link has no b=")
            plain = px(pg)
            if SHOTS: pg.screenshot(path=f"{SHOTS}/{name}-plain.png")
            sel.focus(); need(pg.evaluate("document.activeElement.id") == "basemap", f"{name}: select is keyboard focusable")
            sel.select_option("sat"); settle(pg)
            need(len(gibs) > 0, f"{name}: satellite requests tiles from {HOST} ({len(gibs)} requests, e.g. {gibs[0].split('/best/')[-1] if gibs else '-'})")
            sat = px(pg); diff = np.abs(plain - sat).max(axis=2); d = float((diff > 12).mean()); need(d > 0.2, f"{name}: map pixels change on switch ({d*100:.0f} % of pixels differ by more than 12/255; mean abs diff {float(diff.mean()):.1f})")
            pg.wait_for_timeout(400); need("b=sat" in pg.url, f"{name}: b=sat in the link")
            need(pg.evaluate("__map.getLayer('sat-raster')!=null && __map.getLayer('regions')!=null && __map.getLayer('borders-major')!=null"), f"{name}: imagery layer present with regions and borders above it")
            if SHOTS: pg.screenshot(path=f"{SHOTS}/{name}-sat.png")
            # layer toggle keeps the choice
            cb = pg.locator("#layers .lp-cb:not([disabled])").first; cb.check(); settle(pg)
            need(pg.get_by_label("Map type").input_value() == "sat" and pg.evaluate("__map.getLayer('sat-raster')!=null"), f"{name}: choice survives a layer toggle")
            if SHOTS: pg.screenshot(path=f"{SHOTS}/{name}-sat-layer.png")
            # theme switch (setStyle) keeps it
            pg.evaluate("document.getElementById('theme').click()"); settle(pg)
            need(pg.evaluate("__map.getLayer('sat-raster')!=null && __map.getLayer('regions')!=null"), f"{name}: choice survives the light/dark toggle")
            pg.evaluate("document.getElementById('theme').click()"); settle(pg)
            # restore from link
            url = pg.url; pg2 = ctx.new_page(); g2 = []; pg2.on("request", lambda r: g2.append(r.url) if HOST in r.url else None)
            pg2.goto("about:blank"); pg2.goto(url); ready(pg2); settle(pg2)
            need(pg2.get_by_label("Map type").input_value() == "sat" and len(g2) > 0 and pg2.evaluate("__map.getLayer('sat-raster')!=null"), f"{name}: state restored from the link (select = Satellite, imagery requested)")
            pg2.close()
            # back to plain
            pg.get_by_label("Map type").select_option("plain"); settle(pg)
            back = px(pg); need(pg.evaluate("__map.getLayer('sat-raster')==null") and "b=sat" not in pg.url, f"{name}: back to Plain map removes imagery and b=")
            # peat row
            pg.locator("#layers .lp-group[data-group=land] .lp-gbtn").click() if not pg.locator("#layers .lp-group[data-group=land] .lp-gbody").is_visible() else None
            pr = pg.locator('#layers .lp-crow[data-id="peat"]'); pr.scroll_into_view_if_needed()
            nm = pr.locator(".lp-name").inner_text(); hh = pr.locator(".lp-name").bounding_box()["height"]
            pr.locator(".lp-info").click(); hint = pg.locator(".lp-pop .lp-pop-sec p").first.inner_text(); hint = hint[:len("Swamp soil made of plant remains; burns underground when drained.")]; pg.keyboard.press("Escape")  # the one-line hint opens the (i) panel (part 2 of )
            if SHOTS: pr.screenshot(path=f"{SHOTS}/{name}-peat-row.png")
            need(nm == "Peatland" and hint == "Swamp soil made of plant remains; burns underground when drained." and hh < 28, f"{name}: peat row '{nm}', hint set, one line (height {hh:.0f}px)")
            need(pg.evaluate("document.documentElement.scrollWidth<=innerWidth"), f"{name}: no horizontal scroll")
            need(not errs, f"{name}: no console errors" + (f" {errs[:3]}" if errs else ""))
            ctx.close()
    # failure fallback (desktop light)
    ctx = b.new_context(viewport={"width": 1440, "height": 900}); pg = ctx.new_page(); errs = []
    pg.route(re.compile(r".*gibs\.earthdata\.nasa\.gov.*"), lambda r: r.abort())
    pg.goto(BASE + "app/#" + VIEW); ready(pg); settle(pg)
    pg.get_by_label("Map type").select_option("sat")
    try: pg.wait_for_function("document.getElementById('basemap').value==='plain'", timeout=30000); ok = True
    except Exception: ok = False
    need(ok and "could not be loaded" in pg.inner_text("#base-note") and pg.evaluate("__map.getLayer('sat-raster')==null"), "tile failure: falls back to the plain map with a notice")
    ctx.close(); b.close()
print("\nALL OK" if not fails else f"\n{len(fails)} FAILED")
sys.exit(1 if fails else 0)
