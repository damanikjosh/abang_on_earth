"""saved links restore. Opens a link with month, province, metric, layers, fire layers, map view and layer order,
reads the app state back, then reads the address the app wrote itself and opens THAT in a fresh browser: both must show the same state.
  uv run --with playwright python scripts/check_links.py [site_url]      default http://127.0.0.1:4801/"""
import sys, re, os
from playwright.sync_api import sync_playwright
from _sel import select_option
BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:4801/").rstrip("/") + "/"
REG, VLON, VLAT = os.environ.get("REG", "riau"), float(os.environ.get("VLON", 102.0)), float(os.environ.get("VLAT", 0.4))  # REG/VLON/VLAT: check a link in another country
LINK = f"#m=2016-03&r={REG}&k=viirs_clearing&f=clrv,viirs&l=loss,tmfdef,peat&v={VLON},{VLAT},7.5&o=fire-clrv,fire-viirs,loss,peat"  # names the removed forest-loss fire layer and metric: both are ignored
IDLE = "new Promise(r=>{const m=window.__map;const f=()=>m.loaded()&&!m.isMoving()?r():m.once('idle',r);requestAnimationFrame(()=>requestAnimationFrame(f))})"
STATE = """({month:document.querySelector('#cal .c.sel')?.dataset.m, region:document.getElementById('region').value, metric:document.getElementById('metric').value,
  on:[...document.querySelectorAll('#onmap .lp-row')].map(r=>r.dataset.id).sort(),
  order:[...document.querySelectorAll('#onmap .lp-row')].map(r=>r.dataset.id).slice(0,4),
  view:[+__map.getCenter().lng.toFixed(1), +__map.getCenter().lat.toFixed(1), +__map.getZoom().toFixed(1)], root:__dataRoot.base})"""
fails = []
def need(c, m):
    print(("ok   " if c else "FAIL ") + m)
    if not c: fails.append(m)
with sync_playwright() as p:
    b = p.chromium.launch(args=["--use-gl=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"])
    def load(h):
        ctx = b.new_context(viewport={"width": 1440, "height": 900}); pg = ctx.new_page(); errs = []
        if os.environ.get("FORCE_V4"): pg.route(re.compile(r".*data-version\.json.*"), lambda r: r.fulfill(status=200, content_type="application/json", body='{"version":"v4","base":"data-v4/","fallback":"data-v3/"}'))  # live check before the pointer flip
        pg.on("console", lambda m: errs.append(m.text[:100]) if m.type == "error" and "openfreemap" not in m.text else None)
        pg.goto(BASE + "app/" + h); pg.wait_for_function("window.__appReady===true"); pg.wait_for_timeout(1200); pg.evaluate(IDLE); return ctx, pg, errs
    ctx, pg, errs = load(LINK); s1 = pg.evaluate(STATE); print("state from the saved link:", s1)
    need(s1["month"] == "2016-03" and s1["region"] == REG and s1["metric"] == "viirs_eq", "month and province restored; the removed metric viirs_clearing falls back to the default")
    need(s1["on"] == sorted(["fire-viirs", "loss", "tmfdef", "peat", "regions"]), f"layers restored (regions = the metric colour row, on by default)  {s1['on']}")
    need(s1["order"][:3] == ["fire-viirs", "loss", "peat"], f"layer order restored {s1['order']}")
    need(abs(s1["view"][0] - VLON) < .2 and abs(s1["view"][1] - VLAT) < .2 and abs(s1["view"][2] - 7.5) < .2, f"map view restored {s1['view']}")
    select_option(pg, "#region", "kalimantan-tengah") if pg.evaluate("[...document.querySelectorAll('#region option')].some(o=>o.value==='kalimantan-tengah')") else None
    pg.wait_for_timeout(1500); h2 = pg.evaluate("location.hash"); print("address the app wrote:", h2)
    ctx.close(); ctx, pg, errs2 = load(h2); s2 = pg.evaluate(STATE)
    s1b = dict(s1); need(s2["on"] == s1["on"] and s2["month"] == s1["month"] and s2["metric"] == s1["metric"], "address written by the app restores the same month, metric and layers")
    need(not errs and not errs2, f"no console errors {errs[:2] + errs2[:2]}")
    ctx.close(); b.close()
print("FAILED" if fails else "PASS"); sys.exit(1 if fails else 0)
