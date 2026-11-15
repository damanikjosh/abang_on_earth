#!/usr/bin/env python3
"""scrubbing the timeline must not pile up map sources. BUILT app or live site.
  uv run --with playwright python scripts/check_scrub.py [base_url]      default http://127.0.0.1:4823/
Moves the month slider 200 times (every ~60 ms, MODIS + VIIRS fire layers on), then waits for idle: fire month sources must be < 20 while scrubbing and <= 4 at rest
(before the fix: one per visited month, 299 after two minutes). Exit 1 on failure."""
import sys, re
from playwright.sync_api import sync_playwright
BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:4823/").rstrip("/") + "/"
CNT = "Object.keys(window.__map.getStyle().sources).filter(s=>/^fire-[a-z0-9_]+-\\d{4}-\\d{2}$/i.test(s)).length"
with sync_playwright() as p:
    b = p.chromium.launch(args=["--use-gl=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"])
    pg = b.new_page(viewport={"width": 1440, "height": 900}); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)[:150]))
    pg.on("console", lambda m: errs.append(m.text[:150]) if m.type == "error" and not re.search("openfreemap|Failed to fetch|Failed to load resource", m.text) else None)
    pg.goto(BASE + "app/#m=2010-01&f=viirs,modis"); pg.wait_for_function("window.__appReady===true", timeout=90000); pg.wait_for_timeout(1500)
    peak = 0
    for i in range(200):
        pg.evaluate(f"(()=>{{const s=document.getElementById('slider');s.value=String(120+{i}%170);s.dispatchEvent(new Event('input'))}})()")
        pg.wait_for_timeout(60)
        if i % 10 == 0: peak = max(peak, pg.evaluate(CNT))
    mid = pg.evaluate(CNT)
    pg.evaluate("new Promise(r=>{const m=window.__map;const f=()=>m.loaded()?r():m.once('idle',r);setTimeout(f,300)})"); pg.wait_for_timeout(1500)
    rest = pg.evaluate(CNT); heap = pg.evaluate("performance.memory?performance.memory.usedJSHeapSize/1e6:0")
    print(f"fire month sources: peak while scrubbing {peak}, after 200 steps {mid}, at rest {rest}; JS heap {heap:.0f} MB; page errors {errs[:2]}")
    ok = peak < 20 and rest <= 4 and not errs
    print("ALL OK" if ok else "FAILED"); b.close(); sys.exit(0 if ok else 1)
