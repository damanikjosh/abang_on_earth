#!/usr/bin/env python3
"""a share link keeps the class switches of the drivers layer (x=), the layer opacity (p=) and the open tab (t=); older links (without them) open with the defaults. BUILT app or live site.
  uv run --with playwright python scripts/check_share39.py [base_url]      default http://127.0.0.1:4811/"""
import sys
from playwright.sync_api import sync_playwright
BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:4811/").rstrip("/") + "/"
fails = []
def need(c, m):
    print(("ok   " if c else "FAIL ") + m, flush=True)
    if not c: fails.append(m)
STATE = """(()=>{const q=s=>[...document.querySelectorAll(s)];const cls=Object.fromEntries(q('input[data-cls][data-row=drivers]').map(e=>[e.dataset.cls,e.checked]));
 const op=Object.fromEntries([...window.__panel().opacity]);const m=window.__map;const src=Object.keys(m.getStyle().sources).filter(s=>s.startsWith('ctx-drivers-'));
 const L=m.getStyle().layers.filter(l=>l.source&&l.source.startsWith('ctx-loss-')).map(l=>l.paint&&(l.paint['raster-opacity']??l.paint['fill-opacity']));
 return {cls,op,tab:document.getElementById('dock').dataset.tab,src,lossOp:L,hash:location.hash}})()"""
def load(pg, h):
    pg.goto("about:blank"); pg.goto(BASE + "app/" + h); pg.wait_for_function("window.__appReady===true", timeout=90000); pg.wait_for_timeout(2500)
with sync_playwright() as p:
    b = p.chromium.launch(args=["--use-gl=swiftshader", "--enable-unsafe-swiftshader"])
    ctx = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True); pg = ctx.new_page()
    # 1. an older link (no x, p, t): defaults
    load(pg, "#m=2019-09&r=indonesia&k=viirs_raw&l=drivers,loss&f=viirs&v=118,-2,3.6"); s = pg.evaluate(STATE)
    need(all(s["cls"].values()) and len(s["cls"]) == 7, f"old link: all 7 drivers classes on ({s['cls']})")
    need(not s["op"] and s["tab"] == "timeline", f"old link: every opacity 1, tab timeline ({s['tab']})")
    need(not any(k in s["hash"] for k in ("&x=", "&p=", "&t=")), f"old link: the app does not add x/p/t on its own ({s['hash'][:90]})")
    # 2. a link with the new keys
    load(pg, "#m=2019-09&r=indonesia&k=viirs_raw&l=drivers,loss&f=viirs&v=118,-2,3.6&x=drivers:3.5&p=loss:0.5~fire-viirs:0.35&t=layers"); s = pg.evaluate(STATE)
    need([k for k, v in s["cls"].items() if not v] == ["3", "5"], f"link: classes 3 and 5 are off ({s['cls']})")
    need(s["op"].get("loss") == 0.5 and s["op"].get("fire-viirs") == 0.35 and "drivers" not in s["op"], f"link: opacity loss 0.5, fire-viirs 0.35, drivers untouched ({s['op']})")
    need(s["tab"] == "layers", f"link: Layers tab open ({s['tab']})")
    need(sorted(x.split("-")[-1] for x in s["src"]) == ["c1", "c2", "c4", "c6", "c7"], f"link: the map draws only the five classes left on ({s['src']})")
    need(s["lossOp"] and all(abs(v - 0.45) < 0.02 for v in s["lossOp"]), f"link: forest-loss opacity on the map = 0.9 x 0.5 ({s['lossOp'][:2]})")
    q = dict(kv.split("=", 1) for kv in s["hash"][1:].split("&") if "=" in kv)
    need(q.get("x") == "drivers:3.5" and sorted(q.get("p", "").split("~")) == ["fire-viirs:0.35", "loss:0.5"] and q.get("t") == "layers", f"link: the app writes the same keys back (x={q.get('x')}, p={q.get('p')}, t={q.get('t')})")
    # 3. garbage in the keys is ignored
    load(pg, "#m=2019-09&r=indonesia&k=viirs_raw&l=drivers&f=viirs&v=118,-2,3.6&x=drivers:9.zz~nope:1~a\"]:2&p=loss:abc~drivers:5~a\"]:0.5&t=bogus"); s = pg.evaluate(STATE)
    need(all(s["cls"].values()) and "drivers" not in s["op"] and s["tab"] == "timeline", f"bad keys ignored (classes on, drivers opacity {s['op'].get('drivers')}, tab {s['tab']})")
    # 4. round trip from the UI: switch class 2 off, set drivers opacity, open Details, reload the link
    load(pg, "#m=2019-09&r=indonesia&k=viirs_raw&l=drivers&f=viirs&v=118,-2,3.6")
    pg.evaluate("(()=>{const e=document.querySelector('input[data-cls=\"2\"][data-row=drivers]');e.click()})()")
    pg.click("#tab-layers"); pg.click("#onmap .lp-row[data-id=drivers] .lp-info"); pg.locator(".lp-pop input[type=range]").fill("40"); pg.keyboard.press("Escape")  # opacity lives in the (i) panel
    pg.click("#tab-details"); pg.wait_for_timeout(700); h = pg.evaluate("location.hash")
    need("x=drivers:2" in h and "p=drivers:0.4" in h and "t=details" in h, f"round trip: UI changes are in the link ({h[-80:]})")
    load(pg, h); s = pg.evaluate(STATE)
    need([k for k, v in s["cls"].items() if not v] == ["2"] and s["op"].get("drivers") == 0.4 and s["tab"] == "details", f"round trip: reloading the link restores class 2 off, opacity 0.4, Details ({[k for k,v in s['cls'].items() if not v]}, {s['op'].get('drivers')}, {s['tab']})")
    load(pg, h.replace("&t=details", "")); need(pg.evaluate("document.getElementById('dock').dataset.tab") == "timeline", "round trip: without t= the Timeline tab opens")
    # 5. tab back to Timeline removes t=
    pg.click("#tab-timeline"); pg.wait_for_timeout(500); need("t=" not in pg.evaluate("location.hash"), "closing back to Timeline leaves no t= in the link")
    b.close()
print("ALL OK" if not fails else f"FAILED {len(fails)}"); sys.exit(1 if fails else 0)
