#!/usr/bin/env python3
"""Smoke test of a served build (local or live): the pages load, every layer row switches on and its tiles answer without an error for three months,
the Harmonized VIIRS points draw, the MapBiomas rows and the Countries / Provinces overlay change the picture, no console errors, the paper row and PDF link work.
  uv run --with playwright --with pillow --with numpy python scripts/check_smoke.py [base_url=http://127.0.0.1:4173/]"""
import io, sys, urllib.request
import numpy as np
from PIL import Image
from playwright.sync_api import sync_playwright

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:4173/").rstrip("/") + "/"
fails = []
def need(c, m):
    print(("ok   " if c else "FAIL ") + m, flush=True)
    if not c: fails.append(m)
def ready(pg): pg.wait_for_function("window.__appReady===true", timeout=90000)
def settle(pg):
    pg.wait_for_timeout(500)
    try: pg.evaluate("new Promise(r=>{const m=window.__map; const t=setTimeout(r,15000); const f=()=>m.loaded()&&!m.isMoving()?(clearTimeout(t),r()):m.once('idle',()=>{clearTimeout(t);r()}); requestAnimationFrame(()=>requestAnimationFrame(f))})")
    except Exception: pass
    pg.wait_for_timeout(1200)
def shot(pg): return np.asarray(Image.open(io.BytesIO(pg.locator("#map").screenshot())).convert("RGB")).astype(int)

with sync_playwright() as p:
    b = p.chromium.launch(args=["--use-gl=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"])
    ctx = b.new_context(viewport={"width": 1440, "height": 900}); ctx.set_default_navigation_timeout(120000); pg = ctx.new_page(); errs, bad = [], []
    pg.on("console", lambda m: errs.append(m.text[:160]) if m.type == "error" and "openfreemap" not in m.text and "gibs" not in m.text else None)
    pg.on("pageerror", lambda e: errs.append(str(e)[:160]))
    pg.on("response", lambda r: bad.append(f"{r.status} {r.url[len(BASE):]}") if r.url.startswith(BASE) and r.status >= 400 else None)
    # pages
    for path, word in (("", "Abang on Earth"), ("credits/", "Credits"), ("app/", "Abang on Earth")):
        r = pg.goto(BASE + path); pg.wait_for_timeout(1500)
        need(r.status == 200 and word in pg.title() + pg.inner_text("body")[:2000], f"/{path} loads (HTTP {r.status}, title {pg.title()!r})")
    bad.clear()
    r = pg.goto("about:blank"); r404 = pg.goto(BASE + "no-such-page/")
    local = "127.0.0.1" in BASE or "localhost" in BASE  # the local preview server answers unknown paths with the home page; GitHub Pages serves 404.html
    need(r404.status == 404 or "not found" in pg.title().lower() or local, f"unknown page answers 404 / the 404 page (HTTP {r404.status}, title {pg.title()!r})")
    bad.clear()
    # paper row
    pg.goto(BASE); pg.wait_for_timeout(2000)
    shown = pg.locator("#paper").is_visible(); href = pg.locator("#paper-link").get_attribute("href") if shown else None
    need(shown and href, f"homepage paper row is shown, link {href}")
    if href:
        rq = pg.request.get(BASE + href.lstrip("./")); need(rq.status == 200 and rq.body()[:4] == b"%PDF", f"the PDF link answers with a PDF ({rq.status}, {len(rq.body())} bytes)")
    # every catalogue row, three months
    pg.goto(BASE + "app/#m=2019-09&r=all&k=viirs_raw&v=113.5,-1.8,5"); ready(pg); settle(pg)
    ids = pg.evaluate("[...document.querySelectorAll('.lp-crow')].filter(r=>!r.querySelector('input').disabled).map(r=>r.dataset.id)")
    need(len(ids) >= 15, f"{len(ids)} switchable layer rows in the catalogue: {ids}")
    for m in ("2002-09", "2015-09", "2019-09"):
        bad.clear(); errs.clear()
        pg.goto("about:blank"); pg.goto(BASE + f"app/#m={m}&r=all&k=viirs_raw&s={','.join(ids)}&v=113.5,-1.8,6"); ready(pg); settle(pg)
        on = pg.evaluate("[...document.querySelectorAll('#onmap .lp-row')].map(r=>r.dataset.id)")
        want = set(ids) - {"countries"}  # the Countries overlay row is checked separately below
        need(want <= set(on), f"{m}: all {len(want)} rows are on the map" + ("" if want <= set(on) else f" (missing {sorted(want - set(on))})"))
        need(not bad, f"{m}: no tile or data request answered with an error {bad[:4]}")
        need(not errs, f"{m}: no console errors {errs[:3]}")
    # harmonized points
    pg.goto("about:blank"); pg.goto(BASE + "app/#m=2006-08&r=all&k=viirs_raw&s=fire-harm&v=113.5,-1.8,9.5"); ready(pg); settle(pg)
    n = pg.evaluate("(l)=>__map.getLayer(l)?__map.queryRenderedFeatures({layers:[l]}).length:-1", "fire-harm-2006-08-pts")
    need(n > 0, f"2006-08 Harmonized VIIRS draws {n} points")
    # MapBiomas rows and the overlays change the picture
    def diff(h_on, h_off):
        pg.goto("about:blank"); pg.goto(BASE + "app/" + h_off); ready(pg); settle(pg); a = shot(pg)
        pg.goto("about:blank"); pg.goto(BASE + "app/" + h_on); ready(pg); settle(pg); c = shot(pg)
        return float(np.abs(a - c).mean())
    v = "&v=101.6,0.6,8"
    for row in ("mb_palm", "mb_pulp", "mb_mine"):
        d = diff(f"#m=2010-06&r=riau&k=viirs_raw&s={row}{v}", f"#m=2010-06&r=riau&k=viirs_raw&s=fire-viirs{v}")
        need(d > 0.2, f"{row} draws in 2010 (picture differs by {d:.2f} grey levels from the same view without it)")
    pv = "&v=113,-1,4"
    dp = diff(f"#m=2019-09&r=all&k=viirs_raw&s=regions{pv}", f"#m=2019-09&r=all&k=viirs_raw&s=fire-viirs{pv}")
    dc = diff(f"#m=2019-09&r=all&k=viirs_raw&s=countries{pv}", f"#m=2019-09&r=all&k=viirs_raw&s=fire-viirs{pv}")
    need(dp > 0.5, f"Provinces overlay draws ({dp:.2f})"); need(dc > 0.5, f"Countries overlay draws ({dc:.2f})")
    b.close()
print("\nALL OK" if not fails else f"\n{len(fails)} FAILED"); sys.exit(1 if fails else 0)
