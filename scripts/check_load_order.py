#!/usr/bin/env python3
"""the cold-load order that makes the app faster, checked by holding single files back (BUILT app or live site; no throttling needed).
  uv run --with playwright python scripts/check_load_order.py [base_url]      default http://127.0.0.1:4811/
1. the early script is imported from an inline script ahead of the stylesheets.   2. with app.js held back 4 s the data requests (pointer, manifest, regions, monthly, layers.json) have already started.
3. with regions.geojson held back 4 s the basemap style has already been requested (the map starts from the manifest).   4. annual/peat/burned-area/tmf are not requested before the map is idle,
   the Details card shows an ellipsis until they are in, and the numbers appear afterwards.   5. a link with a region (r=) and no saved view (v=) still waits for the data: the map starts after regions arrive."""
import sys, re, time, urllib.request
from playwright.sync_api import sync_playwright
BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:4811/").rstrip("/") + "/"
fails = []
def need(c, m):
    print(("ok   " if c else "FAIL ") + m, flush=True)
    if not c: fails.append(m)
html = urllib.request.urlopen(BASE + "app/").read().decode()
i_early, i_css = html.find('import("'), html.find('rel="stylesheet"')
need(0 <= i_early < i_css, f"1. inline import() of the early script comes before the first stylesheet (at {i_early} vs {i_css}): {html[i_early:i_early + 45]}")
PW = sync_playwright().start()
def run(hold, hash_, wait_ready=True, during=None):
    """loads the app with one URL pattern held back for 4 s; returns request start times (s since navigation) and the time the held file was released"""
    b = PW.chromium.launch(args=["--use-gl=swiftshader", "--enable-unsafe-swiftshader"]); ctx = b.new_context(viewport={"width": 390, "height": 844}); pg = ctx.new_page()
    t0 = [0.0]; seen = {}; rel = [None]; held = []
    pg.on("request", lambda r: seen.setdefault(re.sub(r"\?.*", "", r.url).split("/")[-1] if "openfreemap" not in r.url else "OFM:" + r.url.split("/")[-1], time.time() - t0[0]))
    if hold: ctx.route(hold, lambda route: held.append(route))
    pg.add_init_script("window.__idle=[];const iv=setInterval(()=>{const m=window.__map;if(m){window.__mapAt=performance.now();m.on('idle',()=>window.__idle.push(performance.now()));clearInterval(iv)}},5)")
    t0[0] = time.time(); pg.goto(BASE + "app/" + hash_, wait_until="commit")
    if hold:
        pg.wait_for_timeout(4000)
        if during: during(pg)
        rel[0] = time.time() - t0[0]
        for r in held: r.continue_()
    if wait_ready: pg.wait_for_function("window.__appReady===true", timeout=90000)
    return b, ctx, pg, seen, rel, t0
HASH = "#m=2019-09&r=indonesia&k=viirs_raw&f=viirs&v=118,-2,3.6"
b, ctx, pg, seen, rel, t0 = run("**/assets/app-*.js", HASH)
d = {k: round(v, 2) for k, v in seen.items() if k in ("data-version.json", "manifest.json", "regions.geojson", "monthly.json", "layers.json")}
need(len(d) == 5 and all(v < rel[0] for v in d.values()), f"2. app.js held until {rel[0]:.1f} s: the five data requests started at {d}")
b.close()
mapat = []
b, ctx, pg, seen, rel, t0 = run("**/regions.geojson", HASH, wait_ready=False, during=lambda pg: mapat.append(pg.evaluate("window.__mapAt")))
need(mapat[0] is not None and mapat[0] / 1000 < 1.5, f"3. regions.geojson held for 4 s: the map already existed {mapat[0]} ms after the page started (basemap does not wait for the data)")
b.close()
b, ctx, pg, seen, rel, t0 = run(None, HASH, wait_ready=False)
pg.wait_for_function("window.__appReady===true", timeout=90000); pg.wait_for_function("window.__studyLoaded===true", timeout=90000)
idle = pg.evaluate("window.__idle[0]") / 1000; ann = seen.get("annual.json")
need(ann is not None and ann >= idle - 0.3, f"4. annual.json requested at {ann:.2f} s, not before the map's first idle ({idle:.2f} s since page start)")
need(pg.text_content("#d-peat") != "…", f"4. Details card shows figures after loading ({pg.text_content('#d-loss')!r}, {pg.text_content('#d-peat')!r})")
b.close()
early = []
b, ctx, pg, seen, rel, t0 = run("**/annual.json", HASH + "&t=details", wait_ready=False, during=lambda pg: (pg.wait_for_function("window.__appReady===true", timeout=60000), early.append(pg.text_content("#d-loss"))))  # Details tab open in the link: asked for at once, held back 4 s
pg.wait_for_function("window.__studyLoaded===true", timeout=90000); late = pg.text_content("#d-loss")
need(early[0] == "…" and late != "…", f"4b. Details figure is '…' while annual.json is held ({early[0]!r}) and a value afterwards ({late!r}); Details tab opened from the link")
b.close()
mapat = []
b, ctx, pg, seen, rel, t0 = run("**/data-v4/regions.geojson", "#m=2019-09&r=riau&k=viirs_raw&f=viirs", wait_ready=False, during=lambda pg: mapat.append(pg.evaluate("window.__mapAt")))
need(mapat[0] is None, f"5. link with r= and no v=: no map while regions.geojson is held for 4 s ({mapat[0]}): the view needs the region's outline")
pg.wait_for_function("window.__appReady===true", timeout=90000); b.close()
PW.stop()
print("ALL OK" if not fails else f"FAILED {len(fails)}"); sys.exit(1 if fails else 0)
