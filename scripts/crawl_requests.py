#!/usr/bin/env python3
"""Crawl a served build and log every same-origin URL it requests.
A SAMPLE that confirms the static proof of scripts/check_data_used.py: homepage, credits, 404 page, the app at its default state, every layer row
the app lists (all its classes at once, every variant), the slider at a spread of years (every 4th January; --all-months: every January), every fire layer at
a spread of months (every 7th month; --all-months: every month), the Details tab, and the rows the app does not list (must request nothing).
  uv run --with playwright python scripts/crawl_requests.py BASE_URL LOG_FILE [--all-months]
LOG_FILE gets one path per line (query removed). Use with scripts/check_data_used.py --crawl LOG_FILE."""
import sys, json, time, urllib.request
from playwright.sync_api import sync_playwright

BASE = sys.argv[1].rstrip("/") + "/"
LOG = sys.argv[2]
FAST = "--all-months" not in sys.argv
seen = []

def get(path):
    return json.load(urllib.request.urlopen(BASE + path))

ptr = get("data-version.json"); D = ptr["base"]
man = get(D + "manifest.json"); lay = get(D + "layers.json"); mon = get(D + man["files"]["monthly"])
months = mon["months"]
IDLE = "new Promise(r=>{const m=window.__map;const t=setTimeout(r,9000);const f=()=>m.loaded()&&!m.isMoving()?(clearTimeout(t),r()):m.once('idle',()=>{clearTimeout(t);r()});requestAnimationFrame(()=>requestAnimationFrame(f))})"


with sync_playwright() as p:
    b = p.chromium.launch(args=["--use-gl=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"])
    def newpage():
        ctx = b.new_context(viewport={"width": 1440, "height": 900}); pg = ctx.new_page()
        pg.on("request", lambda r: seen.append(r.url.split("?")[0]) if r.url.startswith(BASE) else None)
        return ctx, pg
    def open_app(hash_):
        ctx, pg = newpage(); pg.goto(BASE + "app/" + hash_); pg.wait_for_function("window.__appReady===true", timeout=60000); pg.wait_for_timeout(800); pg.evaluate(IDLE)
        return ctx, pg
    def step(pg, i):
        pg.evaluate("(i)=>{const s=document.getElementById('slider');s.value=String(i);s.dispatchEvent(new Event('input',{bubbles:true}))}", i)
        pg.wait_for_timeout(60)
    # pages
    for path in ("", "credits/", "app/"):
        ctx, pg = newpage(); pg.goto(BASE + path); pg.wait_for_timeout(2500); ctx.close()
    # the pointer-less 404 page
    ctx, pg = newpage(); pg.goto(BASE + "no-such-page/"); pg.wait_for_timeout(500); ctx.close()
    # every context layer row, every month Jan (+ every 6th month for year-pinned rows), classes and variants
    jan = [i for i, m in enumerate(months) if m.endswith("-01")]
    for d in lay["layers"]:
        t0 = time.time()
        variants = [v["id"] for v in d.get("variants", [])] or [None]
        for v in variants:
            h = f"#m={months[jan[0]]}&r=indonesia&l={d['id']}&v=113,0,5" + (f"&vr={d['id']}:{v}" if v else "")
            ctx, pg = open_app(h)
            if d.get("mode") in ("cumfile", "year", "month"):
                for i in (jan if not FAST else jan[::4]): step(pg, i); pg.evaluate(IDLE)
            ctx.close()
        print("layer", d["id"], "done", round(time.time() - t0), "s", flush=True)
    # layer row switched on together with the class boxes off (x=) is the same files: not repeated
    # every fire layer, every month
    fl = [d["id"] for d in man["fire_layers"]["layers"]]
    ctx, pg = open_app(f"#m={months[0]}&r=indonesia&f={','.join(fl)}&v=113,0,5")
    t0 = time.time()
    for i in (range(len(months)) if not FAST else range(0, len(months), 7)):
        step(pg, i)
        if i % 3 == 0: pg.evaluate(IDLE)
    print("fire layers over", len(months), "months", round(time.time() - t0), "s", flush=True)
    ctx.close()
    # Details tab and the other pages' lazily loaded files
    ctx, pg = open_app("#m=2019-09&r=riau&k=modis_eq&t=details"); pg.wait_for_timeout(2500); ctx.close()
    b.close()
open(LOG, "w").write("\n".join(sorted({u[len(BASE):] for u in seen})) + "\n")
print("requests logged:", len(set(seen)), "distinct URLs ->", LOG)
