#!/usr/bin/env python3
""" credits button icon drawn once;  home button in the 360x640 fold;  stalled requests end in the error state;  touch devices >= 1200 px get the dock.
  uv run --with playwright python scripts/check_ui_details.py [base_url]      default http://127.0.0.1:4837/   (needs pillow: uv run --with playwright --with pillow ...)"""
import sys, re, io
from playwright.sync_api import sync_playwright
from PIL import Image, ImageStat
BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:4837/").rstrip("/") + "/"
fails = []
def need(c, m):
    print(("ok   " if c else "FAIL ") + m, flush=True)
    if not c: fails.append(m)
with sync_playwright() as p:
    b = p.chromium.launch(args=["--use-gl=swiftshader", "--enable-unsafe-swiftshader"])
    # one icon, not four (computed style + pixels outside the central 30 px square are one flat colour)
    for theme in ("light", "dark"):
        for w, h in ((390, 844), (820, 1180)):
            ctx = b.new_context(viewport={"width": w, "height": h}, color_scheme=theme, has_touch=True, is_mobile=True); pg = ctx.new_page()
            pg.goto(BASE + "app/"); pg.wait_for_function("window.__appReady===true", timeout=90000); pg.wait_for_timeout(1500)
            st = pg.evaluate("(()=>{const e=document.querySelector('.maplibregl-ctrl-attrib-button');const c=getComputedStyle(e);const r=e.getBoundingClientRect();return [c.backgroundRepeat,c.backgroundSize,r.x,r.y,r.width,r.height]})()")
            need(st[0] == "no-repeat" and st[1].startswith("24px"), f" {theme} {w}x{h}: credits button background {st[0]} / {st[1]}")
            pg.add_style_tag(content=".maplibregl-canvas{visibility:hidden!important}"); pg.wait_for_timeout(200)  # the control is translucent: hide the map beneath it so only the button itself is measured
            im = Image.open(io.BytesIO(pg.screenshot(clip={"x": st[2], "y": st[3], "width": st[4], "height": st[5]}))).convert("L")
            W, H = im.size; mask = Image.new("L", (W, H), 255); mask.paste(0, ((W - 30) // 2, (H - 30) // 2, (W + 30) // 2, (H + 30) // 2))
            sd = ImageStat.Stat(im, mask).stddev[0]
            need(sd < 14, f" {theme} {w}x{h}: nothing but the flat button colour outside the central icon (std {sd:.1f})")
            ctx.close()
    # a touch tablet 1366x1024 gets the dock and 44 px targets
    ctx = b.new_context(viewport={"width": 1366, "height": 1024}, has_touch=True, is_mobile=True); pg = ctx.new_page()
    pg.goto(BASE + "app/#l=drivers"); pg.wait_for_function("window.__appReady===true", timeout=90000); pg.wait_for_timeout(1000)
    need(pg.evaluate("matchMedia('(pointer: coarse)').matches") and pg.evaluate("document.getElementById('dock').getBoundingClientRect().width") > 300, " touch 1366x1024: the dock is used")
    pg.click("#dock [role=tab][data-tab=layers]"); pg.wait_for_timeout(400)
    rows = pg.evaluate("[...document.querySelectorAll('.lp-row')].filter(e=>e.offsetParent).map(e=>e.getBoundingClientRect().height)")
    need(rows and min(rows) >= 44, f" touch 1366x1024: layer rows >= 44 px (min {min(rows) if rows else None})"); ctx.close()
    # home button inside the fold at 360x640
    ctx = b.new_context(viewport={"width": 360, "height": 640}, has_touch=True, is_mobile=True); pg = ctx.new_page(); pg.goto(BASE); pg.wait_for_timeout(1500)
    bt = pg.evaluate("document.querySelector('.ctas .pill.solid').getBoundingClientRect().bottom")
    need(bt <= 640, f" home 360x640: 'Open the map' bottom at {bt:.0f} px (<= 640)")
    need(pg.evaluate("document.documentElement.scrollWidth") <= 360, " no horizontal scroll"); ctx.close()
    # a request that hangs (never answers) ends in the error state with Try again, for each core file in both folders
    for fname in ("data-version.json", "manifest.json", "regions.geojson", "monthly.json", "layers.json", "annual.json"):
        ctx = b.new_context(viewport={"width": 390, "height": 844}); pg = ctx.new_page(); on = {"v": True}
        pg.route(re.compile(r".*/(data-v\d/)?" + re.escape(fname) + r"(\?.*)?$"), lambda r: None if on["v"] else r.continue_())
        pg.goto(BASE + "app/?load_timeout_ms=2000")
        if fname in ("data-version.json", "annual.json"):  # these have a fallback / are optional: the app must still come up
            try: pg.wait_for_function("window.__appReady===true", timeout=60000); ok = True
            except Exception: ok = False
            need(ok, f" {fname} stalled: the app still starts (default folder / no yearly figures)")
        else:
            try: pg.wait_for_selector("#loading.failed", timeout=60000); ok = pg.is_visible("#retry") and pg.locator("#loading i").count() == 0
            except Exception: ok = False
            need(ok, f" {fname} stalled in both folders: error + Try again after the deadline, no spinner")
            on["v"] = False
            if ok:
                pg.click("#retry"); 
                try: pg.wait_for_function("window.__appReady===true", timeout=60000); ok2 = True
                except Exception: ok2 = False
                need(ok2, f" {fname}: after the stall ends, Try again brings the app up")
        ctx.close()
    b.close()
print("ALL OK" if not fails else f"FAILED {len(fails)}"); sys.exit(1 if fails else 0)
