#!/usr/bin/env python3
"""small behaviours that had no check. BUILT app or live site.
  uv run --with playwright python scripts/check_misc39.py [base_url]      default http://127.0.0.1:4829/
no 'o=' in the link until the user moves a layer row; moving one (keyboard: Down on its handle) adds it. dark theme logs no 'could not be loaded' image warning.
a panel body that scrolls is marked data-more (fade) and the mark goes when scrolled to the end. layer handle and info button hit areas >= 44 px."""
import sys
from playwright.sync_api import sync_playwright
BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:4829/").rstrip("/") + "/"
fails = []
def need(c, m):
    print(("ok   " if c else "FAIL ") + m, flush=True)
    if not c: fails.append(m)
with sync_playwright() as p:
    b = p.chromium.launch(args=["--use-gl=swiftshader", "--enable-unsafe-swiftshader"])
    ctx = b.new_context(viewport={"width": 1440, "height": 900}, color_scheme="dark"); pg = ctx.new_page(); logs = []
    pg.on("console", lambda m: logs.append(m.text) if m.type in ("warning", "error") else None)
    pg.goto(BASE + "app/#m=2019-09&f=viirs"); pg.wait_for_function("window.__appReady===true", timeout=90000); pg.wait_for_timeout(3000)
    need(not any("could not be loaded" in l for l in logs), f" dark theme: no 'image could not be loaded' warning ({[l[:60] for l in logs if 'loaded' in l][:1]})")
    h = pg.evaluate("location.hash"); need("o=" not in h, f" fresh load: no layer order in the link ({len(h)} chars)")
    pg.click('#layers .lp-group[data-group=land] .lp-gbtn'); pg.click('#layers .lp-crow[data-id=loss] input'); pg.wait_for_timeout(500)
    need("s=" in pg.evaluate("location.hash") and pg.evaluate("document.querySelector('#onmap .lp-row').dataset.id") == "loss", "#75 switching a layer on lists it on top of On the map and writes s= (part 2: the new layer goes to the top)")
    pg.focus("#onmap .lp-row[data-id=loss] .lp-handle"); pg.keyboard.press("Space"); pg.keyboard.press("ArrowDown"); pg.keyboard.press("Space"); pg.wait_for_timeout(500)
    need("o=" in pg.evaluate("location.hash") and pg.evaluate("[...document.querySelectorAll('#onmap .lp-row')].map(r=>r.dataset.id).indexOf('loss')") == 1, " moving a layer row (keyboard) keeps o= in the link")
    sizes = pg.evaluate("(()=>{const g=document.querySelector('#onmap .lp-handle'),i=document.querySelector('#onmap .lp-info');return {gripH:g.getBoundingClientRect().height,gripAfterW:g.getBoundingClientRect().width,infoW:i.getBoundingClientRect().width,infoH:i.getBoundingClientRect().height}})()")
    need(sizes["gripH"] >= 44 and sizes["gripAfterW"] >= 44 and sizes["infoW"] >= 44 and sizes["infoH"] >= 44, f" touch targets: grip {sizes['gripAfterW']:.0f}x{sizes['gripH']:.0f}, info {sizes['infoW']:.0f}x{sizes['infoH']:.0f}")
    more = pg.evaluate("(()=>{const e=document.querySelector('.p-details .pbody');return [e.hasAttribute('data-more'),e.scrollHeight>e.clientHeight+4]})()")
    need(more[0] == more[1], f" details panel: fade mark ({more[0]}) matches 'has more to scroll' ({more[1]})")
    pg.evaluate("(()=>{const e=document.querySelector('.p-details .pbody');e.scrollTop=e.scrollHeight})()"); pg.wait_for_timeout(300)
    need(not pg.evaluate("document.querySelector('.p-details .pbody').hasAttribute('data-more')"), " fade mark gone at the end of the scroll")
    b.close()
print("ALL OK" if not fails else f"FAILED {len(fails)}"); sys.exit(1 if fails else 0)
