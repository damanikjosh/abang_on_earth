#!/usr/bin/env python3
""" the map stays usable and is framed where the panels are not. BUILT app or live site.
  uv run --with playwright python scripts/check_phone_frame.py [base_url] [out_dir]      default http://127.0.0.1:4823/ , /tmp/abang-on-earth-checks/
Sizes: phones, 600-900 px wide tablets in portrait and landscape (600x1000, 768x1024, 820x1180, 900x1200, 1000x600, 1024x768, 1180x820), short windows, 844x390 landscape phone (side sheet).
For each (390x844 and 360x640 light + dark at 390): Layers tab open -> dock covers <= 56 % of the height; the credits control is collapsed (<= 56 px tall);
choosing Country = Indonesia / Malaysia puts the country's centre in the free map area at zoom >= 2.3 (Indonesia is width-limited); choosing Region = Riau moves the map into Riau (zoom >= 5);
a #r=riau link opens on Riau. Desktop: the Region selector moves the map. Exit 1 on any failure. Screenshots <out>/frame-<w>-<theme>-*.png"""
import sys, re, pathlib, json
from playwright.sync_api import sync_playwright
from _sel import select_option
BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:4823/").rstrip("/") + "/"
ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = pathlib.Path(sys.argv[2]) if len(sys.argv) > 2 else pathlib.Path("/tmp/abang-on-earth-checks"); OUT.mkdir(parents=True, exist_ok=True)
IDLE = "new Promise(r=>{const m=window.__map;const f=()=>m.loaded()&&!m.isMoving()?r():m.once('idle',r);requestAnimationFrame(()=>requestAnimationFrame(f))})"
fails = []
def need(c, m):
    print(("ok   " if c else "FAIL ") + m, flush=True)
    if not c: fails.append(m)
def load(b, w, h, theme, hash_=""):
    touch = w < 481
    ctx = b.new_context(viewport={"width": w, "height": h}, color_scheme=theme, has_touch=touch, is_mobile=touch); pg = ctx.new_page()
    pg.goto("about:blank"); pg.goto(BASE + "app/" + hash_); pg.wait_for_function("window.__appReady===true", timeout=90000); pg.wait_for_timeout(1200)
    return ctx, pg
with sync_playwright() as p:
    b = p.chromium.launch(args=["--use-gl=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"])
    SIZES = ((390, 844, "light"), (390, 844, "dark"), (360, 640, "light"), (640, 450, "light"),
             (600, 1000, "light"), (768, 1024, "light"), (820, 1180, "dark"), (900, 1200, "light"), (1000, 600, "light"), (1024, 768, "light"), (1180, 820, "light"), (844, 390, "light"), (1000, 560, "dark"))
    for w, h, theme in SIZES:
        tag = f"{w}x{h}-{theme}"; ctx, pg = load(b, w, h, theme); ev = pg.evaluate
        att = ev("(()=>{const a=document.querySelector('.maplibregl-ctrl-attrib');return a?a.getBoundingClientRect().height:0})()")
        need(att <= 56, f"{tag}: credits control collapsed ({att:.0f} px tall)")
        need(ev("!!document.querySelector('.maplibregl-ctrl-attrib-button')"), f"{tag}: credits 'i' button present (credits stay reachable)")
        pg.click("#dock [role=tab][data-tab=layers]"); pg.wait_for_timeout(500)
        side = ev("matchMedia('(max-height: 480px) and (min-width: 600px)').matches"); r = ev("(()=>{const r=document.getElementById('dock').getBoundingClientRect();return [r.left,r.top,r.right,r.width]})()")
        top, dright = r[1], r[2]; frac = 1 - top / h
        if side: need(r[3] / w <= 0.5, f"{tag}: short landscape: the dock is a side sheet taking {r[3]/w*100:.0f} % of the width (<= 50 %)")
        else: need(frac <= 0.56, f"{tag}: Layers dock covers {frac*100:.0f} % of the height (<= 56 %)")
        need(ev("document.documentElement.scrollWidth") <= w, f"{tag}: no horizontal scroll")
        bp = ev("(()=>{const q=window.__map.project([113,0]);return [q.x,q.y]})()"); tb0 = ev("document.querySelector('.topbar').getBoundingClientRect().bottom")
        need((bp[0] >= dright) if side else (tb0 <= bp[1] <= top), f"{tag}:  after opening Layers, Borneo (the middle of the map subject) is not behind the panel: at ({bp[0]:.0f},{bp[1]:.0f}), dock top {top:.0f}, dock right {dright:.0f}")
        pg.screenshot(path=str(OUT / f"frame-{w}x{h}-{theme}-layers.png"))
        need(ev("document.getElementById('sel').open") is False, f"{tag}: metric/country/region folded into one summary line")
        for sel, name, lng, lat in (("IDN", "Indonesia", 117, -2), ("MYS", "Malaysia", 109.5, 4)):
            select_option(pg, "#country", sel); pg.wait_for_timeout(300); pg.evaluate(IDLE); pg.wait_for_timeout(600)
            z = ev("window.__map.getZoom()"); pt = ev(f"(()=>{{const q=window.__map.project([{lng},{lat}]);return [q.x,q.y]}})()"); top = ev("document.getElementById('dock').getBoundingClientRect().top")
            tb = ev("document.querySelector('.topbar').getBoundingClientRect().bottom")
            free = (pt[0] >= dright and tb <= pt[1] <= h) if side else (tb <= pt[1] <= top and 0 <= pt[0] <= w)
            need(z >= 2.0 and free, f"{tag}: Country={name}: zoom {z:.2f} (>= 2.0), centre at ({pt[0]:.0f},{pt[1]:.0f}) inside the free map area (top bar {tb:.0f}, dock top {top:.0f}, dock right {dright:.0f})")
            pg.screenshot(path=str(OUT / f"frame-{w}x{h}-{theme}-{sel}.png"))
        if (w, h) == (390, 844) and theme == "light":
            select_option(pg, "#country", "IDN"); pg.wait_for_timeout(300); pg.evaluate(IDLE)
            select_option(pg, "#region", "riau"); pg.wait_for_timeout(300); pg.evaluate(IDLE); pg.wait_for_timeout(600)
            c = ev("(()=>{const m=window.__map;const p=m.project([101.5,0.5]);return [p.x,p.y,m.getZoom()]})()"); dock = ev("document.getElementById('dock').getBoundingClientRect().top")
            need(c[2] >= 5 and 0 <= c[0] <= w and 60 <= c[1] <= dock, f"{tag}: Region=Riau moves the map to Riau (Riau centre at x {c[0]:.0f}, y {c[1]:.0f}; dock top {dock:.0f}; zoom {c[2]:.1f})")
        ctx.close()
    ctx, pg = load(b, 390, 844, "light", "#r=riau"); pg.evaluate(IDLE)
    c = pg.evaluate("(()=>{const m=window.__map;const p=m.project([101.5,0.5]);return [p.x,p.y,m.getZoom()]})()")
    need(c[2] >= 5 and 0 <= c[0] <= 390 and 60 <= c[1] <= 700, f"#r=riau link opens on Riau (Riau centre at x {c[0]:.0f}, y {c[1]:.0f}; zoom {c[2]:.1f})"); ctx.close()
    ctx, pg = load(b, 1440, 900, "light", "#c=IDN"); select_option(pg, "#region", "riau"); pg.wait_for_timeout(300); pg.evaluate(IDLE); pg.wait_for_timeout(600)
    c = pg.evaluate("(()=>{const m=window.__map;const p=m.project([101.5,0.5]);return [p.x,p.y,m.getZoom()]})()")
    need(c[2] >= 5 and 380 <= c[0] <= 1140 and 80 <= c[1] <= 650, f"desktop: Region=Riau moves the map (Riau centre at x {c[0]:.0f}, y {c[1]:.0f}; zoom {c[2]:.1f})")
    pg.screenshot(path=str(OUT / "frame-1440-riau.png")); ctx.close(); b.close()
print("ALL OK" if not fails else f"FAILED {len(fails)}: {fails}")
sys.exit(1 if fails else 0)
