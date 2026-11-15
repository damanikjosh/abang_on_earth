#!/usr/bin/env python3
""" day/night tiles, on a SERVED build (vite preview / any range-capable server; python -m http.server cannot do range requests).
  uv run --with playwright --with pillow --with numpy python scripts/check_fire_daynight_site.py NEW_BASE_URL [OLD_BASE_URL]
NEW = the build with the day/night tiles + manifest classes. OLD (optional) = the same code with the old combined tiles and no classes: the both-ticked picture must equal it.
For MODIS 2002-09, 2015-09, 2019-09 and VIIRS 2015-09, 2019-09 (VIIRS has no data before 2012-01), at 1440x900 and 390x844: both boxes ticked and enabled and drawn from the Day and Night files (not the
combined one); unticking Night keeps Day only; unticking Day keeps Night only; both off draws nothing; ticking again restores; no console errors and no failed tile requests.
With OLD: density cells at zoom 6 and 7 of the both-ticked state differ from the old combined picture in at most 0.05 % of the pixels."""
import sys, io
from playwright.sync_api import sync_playwright
from PIL import Image
import numpy as np
NEW = sys.argv[1].rstrip("/") + "/"; OLD = sys.argv[2].rstrip("/") + "/" if len(sys.argv) > 2 else None
fails = []
def need(c, m):
    print(("ok   " if c else "FAIL ") + m, flush=True)
    if not c: fails.append(m)
def settle(pg):
    pg.wait_for_timeout(500)
    try: pg.evaluate("new Promise(r=>{const m=window.__map; if(m.loaded()&&!m.isMoving()) return r(); m.once('idle',r)})")
    except Exception: pass
    pg.wait_for_timeout(1200)
def load(pg, base, h):
    pg.goto("about:blank"); pg.goto(base + "app/" + h); pg.wait_for_function("window.__appReady===true", timeout=90000); settle(pg)
def vis(pg, pre): return pg.evaluate("(p)=>Object.fromEntries(__map.getStyle().layers.filter(l=>l.id.startsWith(p)).map(l=>[l.id,l.layout.visibility||'visible']))", pre)
def px(pg): return np.asarray(Image.open(io.BytesIO(pg.locator("#map").screenshot())).convert("RGB")).astype(float)[:, 400:, :]  # right of the layer panel (its Day / Night boxes are new)
CASES = [("modis", "2002-09"), ("modis", "2015-09"), ("modis", "2019-09"), ("viirs", "2015-09"), ("viirs", "2019-09")]
with sync_playwright() as p:
    b = p.chromium.launch(args=["--use-gl=swiftshader", "--enable-unsafe-swiftshader"])
    for (w, h, tg) in ((1440, 900, "desk"), (390, 844, "phone")):
        ctx = b.new_context(viewport={"width": w, "height": h}, device_scale_factor=1); pg = ctx.new_page(); errs = []; bad = []
        pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None); pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.on("response", lambda r: bad.append(f"{r.status} {r.url}") if r.status >= 400 and "pmtiles" in r.url else None)
        for s, m in CASES:
            name = f"{tg} {s} {m}"; row = f"fire-{s}"; bx = lambda n: pg.locator(f"#lyr-{row} input[data-cls='{n}']")
            H = f"#m={m}&r=all&k=modis_raw&s={row}&v=112.58,-2.93,7&t=layers"
            load(pg, NEW, H); v = vis(pg, row); want = {f"{row}_{c}-{m}-{k}" for c in (1, 2) for k in ("dens", "pts")}
            need(set(v) == want and all(x == "visible" for x in v.values()), f"{name}: both ticked draws the Day and the Night file (not the combined one): {sorted(v)}")
            bx(1).scroll_into_view_if_needed(); need(bx(1).is_checked() and bx(2).is_checked() and not bx(1).is_disabled() and not bx(2).is_disabled(), f"{name}: both boxes ticked and enabled")
            bx(2).uncheck(); settle(pg); v = vis(pg, row)
            need(all(v[f"{row}_1-{m}-{k}"] == "visible" and v.get(f"{row}_2-{m}-{k}", "none") == "none" for k in ("dens", "pts")), f"{name}: Night unticked -> Day only")
            bx(2).check(); bx(1).uncheck(); settle(pg); v = vis(pg, row)
            need(all(v[f"{row}_2-{m}-{k}"] == "visible" and v.get(f"{row}_1-{m}-{k}", "none") == "none" for k in ("dens", "pts")), f"{name}: Day unticked -> Night only")
            bx(2).uncheck(); settle(pg); need(all(x == "none" for x in vis(pg, row).values()), f"{name}: both unticked -> nothing drawn")
            bx(1).check(); bx(2).check(); settle(pg); need(all(x == "visible" for x in vis(pg, row).values()), f"{name}: both ticked again -> everything back")
            if OLD and tg == "desk":
                for z in (6, 7):
                    hz = H.replace("7&t", f"{z}&t"); load(pg, NEW, hz); a = px(pg); load(pg, OLD, hz); o = px(pg)
                    d = float((np.abs(a - o).max(axis=2) > 12).mean()); drawn = float((np.abs(o - o[0, 0]).max(axis=2) > 12).mean())
                    need(d <= 0.0005, f"{name} z{z}: both-ticked picture vs old combined layer: {d*100:.3f} % of pixels differ (map not empty: {drawn*100:.1f} % non-background)")
        need(not errs, f"{tg}: no console errors {errs[:3]}"); need(not bad, f"{tg}: no failed tile request {bad[:3]}"); ctx.close()
    b.close()
print("\nALL OK" if not fails else f"\n{len(fails)} FAILED"); sys.exit(1 if fails else 0)
