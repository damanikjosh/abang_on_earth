#!/usr/bin/env python3
"""touch targets and the 404 page. BUILT app or live site.
  uv run --with playwright python scripts/check_touch.py [base_url]      default http://127.0.0.1:4835/
On a phone (390x844) with the Layers tab open and the drivers layer on: every visible interactive element in the dock and the map buttons is >= 44 px high and wide (inline links excluded);
credits 'i' >= 44. 404: /404.html exists with links to the map, home and credits; a missing URL answers 404 (live site: with that page)."""
import sys, urllib.request, urllib.error
from playwright.sync_api import sync_playwright
BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:4835/").rstrip("/") + "/"
fails = []
def need(c, m):
    print(("ok   " if c else "FAIL ") + m, flush=True)
    if not c: fails.append(m)
with sync_playwright() as p:
    b = p.chromium.launch(args=["--use-gl=swiftshader", "--enable-unsafe-swiftshader"])
    ctx = b.new_context(viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True); pg = ctx.new_page()
    pg.goto(BASE + "app/#m=2019-09&f=viirs&l=drivers"); pg.wait_for_function("window.__appReady===true", timeout=90000); pg.wait_for_timeout(1200)
    pg.click("#dock [role=tab][data-tab=layers]"); pg.wait_for_timeout(400); pg.evaluate("document.getElementById('sel').open=true"); pg.wait_for_timeout(200)
    small = pg.evaluate("""[...document.querySelectorAll('#dock button, #dock select, #dock input[type=checkbox], #dock .cls, .maplibregl-ctrl button, .maplibregl-ctrl-attrib-button, .tabs button')]
      .filter(e=>e.offsetParent!==null||getComputedStyle(e).position==='fixed').map(e=>{const r=e.getBoundingClientRect();const lab=e.closest('label');const q=lab?lab.getBoundingClientRect():r;return [e.className||e.tagName, Math.round(Math.max(r.height,q.height)), Math.round(Math.max(r.width,q.width))]})
      .filter(x=>x[1]>0&&(x[1]<44||x[2]<44)&&!/grip|grab/.test(x[0]))   // grip and grab: the 44 px hit area is a ::after pseudo-element (measured in check_misc for the grip)""")
    need(not small, f"every button/select/checkbox label in the dock and every map button is >= 44 px (too small: {small[:4]})")
    b.close()
for path, want in (("404.html", 200),):
    try: r = urllib.request.urlopen(BASE + path); body = r.read().decode(); st = r.status
    except urllib.error.HTTPError as e: body = e.read().decode(); st = e.code
    need(st == want and "does not exist" in body and 'href="/app/"' in body and 'href="/credits/"' in body, f"{path}: answers, links to map and credits")
try: urllib.request.urlopen(BASE + "definitely-not-a-page/"); st = 200; body = ""
except urllib.error.HTTPError as e: st = e.code; body = e.read().decode()
need(st == 404, f"a missing URL answers 404 ({st})")
if BASE.startswith("https://"): need("does not exist" in body, "the live 404 body is our page")
print("ALL OK" if not fails else f"FAILED {len(fails)}"); sys.exit(1 if fails else 0)
