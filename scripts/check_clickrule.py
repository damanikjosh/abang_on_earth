#!/usr/bin/env python3
"""what a click on an area selects. Countries row on = country; Provinces row on = province; both off = by zoom (country on a wide view, province from zoom 5, hysteresis 0.3). BUILT app or live site.
  uv run --with playwright python scripts/check_clickrule.py [base_url]      default http://127.0.0.1:4173/
At 390x844 and 1440x900, light and dark: the click target and the hover outline follow the rule at a wide and a close zoom with both rows off and with each row on; the level does not flip while zooming across the boundary;
the link (r=, c=) and the pickers match the selection; a click on the sea changes nothing; no console errors."""
import sys
from playwright.sync_api import sync_playwright
BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:4173/").rstrip("/") + "/"
fails = []
def need(c, m):
    print(("ok   " if c else "FAIL ") + m, flush=True)
    if not c: fails.append(m)
def ready(pg): pg.wait_for_function("window.__appReady===true", timeout=90000)
def settle(pg):
    pg.wait_for_timeout(400)
    try: pg.evaluate("new Promise(r=>{const m=window.__map; if(m.loaded()&&!m.isMoving()) return r(); m.once('idle',r)})")
    except Exception: pass
    pg.wait_for_timeout(700)
def load(pg, h):
    pg.goto("about:blank"); pg.goto(BASE + "app/" + h); ready(pg); settle(pg)
T = [113.5, -1.8]  # Central Kalimantan, Indonesia
def target(pg, z, ll=T):
    pg.evaluate("([c,z])=>__map.jumpTo({center:c,zoom:z})", [ll, z]); settle(pg)
    q = pg.evaluate("(c)=>{const p=__map.project(c);return [p.x,p.y]}", ll)
    h = pg.viewport_size["height"]
    if pg.viewport_size["width"] < 700 and q[1] > h * 0.3:  # phone: the dock covers the lower part; bring the point into the free top
        pg.evaluate("(d)=>__map.panBy([0,d],{duration:0})", int(q[1] - h * 0.25)); settle(pg); q = pg.evaluate("(c)=>{const p=__map.project(c);return [p.x,p.y]}", ll)
    bb = pg.locator("#map").bounding_box(); return bb["x"] + q[0], bb["y"] + q[1]
def sel(pg): return pg.evaluate("({c:document.getElementById('country').value,r:document.getElementById('region').value,h:location.hash})")
def hover_filters(pg): return pg.evaluate("({r:JSON.stringify(__map.getFilter('borders-hover-r')),c:__map.getLayer('borders-hover-c')?JSON.stringify(__map.getFilter('borders-hover-c')):null})")
with sync_playwright() as p:
    b = p.chromium.launch(args=["--use-gl=swiftshader", "--enable-unsafe-swiftshader"])
    for (w, h, tg) in ((390, 844, "phone"), (1440, 900, "desk")):
        for scheme in ("light", "dark"):
            name = f"{tg}-{scheme}"
            ctx = b.new_context(viewport={"width": w, "height": h}, color_scheme=scheme, device_scale_factor=1); pg = ctx.new_page(); errs = []
            pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None); pg.on("pageerror", lambda e: errs.append(str(e)))
            # --- both rows off, wide view -> country
            load(pg, "#m=2019-09&r=all&k=viirs_raw&s=fire-viirs&v=113,-2,4&t=layers")
            need(pg.evaluate("__clickLevel()") == "country", f"{name}: both rows off at zoom 4 -> click level 'country'")
            x, y = target(pg, 4); pg.mouse.move(x, y); pg.wait_for_timeout(600); hf = hover_filters(pg)
            need(('"IDN"' in (hf["c"] or "")) or ('"IDN"' in hf["r"]), f"{name}: hover previews the country outline (IDN) {hf}")
            pg.mouse.click(x, y); pg.wait_for_timeout(2500); s0 = sel(pg)
            need(s0["c"] == "IDN" and s0["r"] == "indonesia" and "r=indonesia" in s0["h"] and "c=IDN" in s0["h"], f"{name}: wide view, both rows off: a click selects the country ({s0['c']} / {s0['r']}, link r=indonesia c=IDN)")
            # --- both rows off, close view -> province
            load(pg, "#m=2019-09&r=all&k=viirs_raw&s=fire-viirs&v=113,-2,8&t=layers")
            need(pg.evaluate("__clickLevel()") == "region", f"{name}: both rows off at zoom 8 -> click level 'region'")
            x, y = target(pg, 8); pg.mouse.move(x, y); pg.wait_for_timeout(600); hf = hover_filters(pg)
            need('"get","id"' in hf["r"].replace(" ", "") and '""]' not in hf["r"].replace(" ", ""), f"{name}: hover previews the province outline {hf['r']}")
            pg.mouse.click(x, y); pg.wait_for_timeout(1500); s1 = sel(pg)
            need(s1["r"] not in ("indonesia", "all") and f"r={s1['r']}" in s1["h"], f"{name}: close view, both rows off: a click selects the province ({s1['r']}), link r={s1['r']}")
            # --- Central Kalimantan fits the screen (zoom 5.5): a click selects the province; all of Indonesia (zoom 3.7): the country
            load(pg, "#m=2019-09&r=all&k=viirs_raw&s=fire-viirs&v=113.5,-1.5,5.5&t=layers")
            x, y = target(pg, 5.5, [113.5, -1.5]); need(pg.evaluate("__clickLevel()") == "region", f"{name}: at zoom 5.5 (a large Kalimantan province fills the view) the level is 'region'")
            pg.mouse.move(x, y); pg.wait_for_timeout(500); hf = hover_filters(pg); need('"get","id"' in hf["r"].replace(" ", "") and '""]' not in hf["r"].replace(" ", ""), f"{name}: hover shows the province outline at zoom 5.5")
            pg.mouse.click(x, y); pg.wait_for_timeout(1500); sk = sel(pg); need(sk["r"] not in ("indonesia", "all") and f"r={sk['r']}" in sk["h"], f"{name}: zoom 5.5, both rows off: a click on Central Kalimantan selects the province ({sk['r']}), not Indonesia")
            load(pg, "#m=2019-09&r=all&k=viirs_raw&s=fire-viirs&v=118,-2,3.7&t=layers"); x, y = target(pg, 3.7, [113.5, -1.5]); need(pg.evaluate("__clickLevel()") == "country", f"{name}: a view of all Indonesia (zoom 3.7) is level 'country'")
            pg.mouse.click(x, y); pg.wait_for_timeout(2500); si = sel(pg); need(si["c"] == "IDN" and si["r"] == "indonesia", f"{name}: all of Indonesia in view: a click selects the country ({si['c']} / {si['r']})")
            # --- rows on
            load(pg, "#m=2019-09&r=all&k=viirs_raw&s=regions&v=113,-2,4&t=layers")
            x, y = target(pg, 4); need(pg.evaluate("__clickLevel()") == "region", f"{name}: Provinces row on at a wide zoom -> 'region'")
            pg.mouse.click(x, y); pg.wait_for_timeout(1500); s2 = sel(pg)
            need(s2["r"] not in ("indonesia", "all"), f"{name}: Provinces on, wide view: a click selects the province ({s2['r']})")
            load(pg, "#m=2019-09&r=all&k=viirs_raw&s=countries&v=113,-2,8&t=layers")
            x, y = target(pg, 8); need(pg.evaluate("__clickLevel()") == "country", f"{name}: Countries row on at a close zoom -> 'country'")
            pg.mouse.click(x, y); pg.wait_for_timeout(2500); s3 = sel(pg)
            need(s3["c"] == "IDN" and s3["r"] == "indonesia", f"{name}: Countries on, close view: a click selects the country ({s3['c']} / {s3['r']})")
            # --- hysteresis (both rows off)
            load(pg, "#m=2019-09&r=all&k=viirs_raw&s=fire-viirs&v=113,-2,4&t=layers"); lv = lambda z: (pg.evaluate("(z)=>{__map.jumpTo({zoom:z});return null}", z), pg.wait_for_timeout(200), pg.evaluate("__clickLevel()"))[2]
            seq = [(4.0, "country"), (5.1, "country"), (5.29, "country"), (5.4, "region"), (5.0, "region"), (4.75, "region"), (4.6, "country")]
            got = [(z, lv(z)) for z, _ in seq]
            need(got == seq, f"{name}: the click level flips at zoom 5.3 going in and 4.7 coming out (hysteresis): {got}")
            # --- sea: nothing changes
            x, y = target(pg, 5, [118.0, 5.5]) if False else (None, None)
            load(pg, "#m=2019-09&r=riau&k=viirs_raw&s=fire-viirs&v=113,-2,8&t=layers"); before = sel(pg)["r"]; x, y = target(pg, 8, [113.0, -6.6])  # Java Sea
            pg.mouse.click(x, y); pg.wait_for_timeout(800); need(sel(pg)["r"] == before, f"{name}: a click on the sea changes nothing (region still {before})")
            need(pg.evaluate("document.documentElement.scrollWidth<=innerWidth"), f"{name}: no horizontal scroll")
            need(not errs, f"{name}: no console errors" + (f" {errs[:3]}" if errs else ""))
            ctx.close()
    b.close()
print("\nALL OK" if not fails else f"\n{len(fails)} FAILED")
sys.exit(1 if fails else 0)
