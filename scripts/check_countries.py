#!/usr/bin/env python3
"""group "Fire counts by region" with the rows Provinces and Countries. BUILT app or live site.
  uv run --with playwright python scripts/check_countries86.py [base_url] [shot_dir]      default http://127.0.0.1:4173/
At 390x844 and 1440x900, light and dark: labels; ticking Countries fills each country with the colour of its OWN national series (checked against monthly.json: darker = more), Provinces goes off (one level at a time),
the row has its own metric picker (kc= in the link), opacity from the (i) panel, a click on a country selects it like the Country picker, the row holds no free text, links round-trip, old links unchanged, no console errors."""
import sys, json, urllib.request
from playwright.sync_api import sync_playwright
BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:4173/").rstrip("/") + "/"
SHOTS = sys.argv[2] if len(sys.argv) > 2 else None
fails = []
def need(c, m):
    print(("ok   " if c else "FAIL ") + m, flush=True)
    if not c: fails.append(m)
def ready(pg): pg.wait_for_function("window.__appReady===true", timeout=90000)
def settle(pg):
    pg.wait_for_timeout(500)
    try: pg.evaluate("new Promise(r=>{const m=window.__map; if(m.loaded()&&!m.isMoving()) return r(); m.once('idle',r)})")
    except Exception: pass
    pg.wait_for_timeout(900)
def load(pg, h):
    pg.goto("about:blank"); pg.goto(BASE + "app/" + h); ready(pg); settle(pg)
ver = json.load(urllib.request.urlopen(BASE + "data-version.json"))
mon = json.load(urllib.request.urlopen(BASE + ver["base"] + "monthly.json"))
man = json.load(urllib.request.urlopen(BASE + ver["base"] + "manifest.json"))
CT = {c["code"]: c["total"] for c in man["countries"]}
MI = mon["months"].index("2019-09")
OPR, OPC = "__map.getPaintProperty('regions','fill-opacity')", "__map.getPaintProperty('regions-country','fill-opacity')"
ONMAP = "[...document.querySelectorAll('#onmap .lp-row')].map(r=>r.dataset.id)"
def colours(pg):  # country code -> rgb tuple from the match expression
    e = pg.evaluate("__map.getPaintProperty('regions-country','fill-color')"); out = {}
    for i in range(2, len(e) - 1, 2):
        v = e[i + 1]; out[e[i]] = tuple(int(float(x)) for x in v[v.index("(") + 1:v.index(")")].split(",")[:3]) if isinstance(v, str) and v.startswith("rgb") else v
    return out
lum = lambda c: 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]  # light theme: more = darker; dark theme: more = lighter (the heat ramp flips)
with sync_playwright() as p:
    b = p.chromium.launch(args=["--use-gl=swiftshader", "--enable-unsafe-swiftshader"])
    for (w, h, tg) in ((390, 844, "phone"), (1440, 900, "desk")):
        for scheme in ("light", "dark"):
            name = f"{tg}-{scheme}"
            ctx = b.new_context(viewport={"width": w, "height": h}, color_scheme=scheme, device_scale_factor=1); pg = ctx.new_page(); errs = []
            pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None); pg.on("pageerror", lambda e: errs.append(str(e)))
            load(pg, "#m=2019-09&r=all&k=viirs_raw&s=regions&v=108,2,4.2&t=layers")
            grp = pg.locator('#layers .lp-group[data-group="colour"]'); grp.scroll_into_view_if_needed()
            need(grp.locator(".lp-glabel").inner_text() == "Fire counts by region" and [e.inner_text() for e in grp.locator(".lp-crow .lp-name").all()] == ["Countries", "Provinces"], f"{name}: group 'Fire counts by region' lists Countries first, then Provinces")
            need(pg.locator('#onmap .lp-row[data-id="regions"] .lp-name').inner_text() == "Provinces", f"{name}: the On the map row is called Provinces")
            cb = grp.locator('.lp-crow[data-id="countries"] input'); cb.check(); pg.wait_for_timeout(800)
            need(pg.evaluate(ONMAP) == ["countries"] or "countries" in pg.evaluate(ONMAP), f"{name}: ticking Countries lists it on the map {pg.evaluate(ONMAP)}")
            need("regions" not in pg.evaluate(ONMAP) and not grp.locator('.lp-crow[data-id="regions"] input').is_checked() and pg.evaluate(OPR) == 0 and pg.evaluate(OPC) > 0, f"{name}: Provinces switched off (one level at a time): provinces opacity {pg.evaluate(OPR)}, countries {pg.evaluate(OPC):.2f}")
            need("countries" in pg.url.split("s=")[-1].split("&")[0], f"{name}: link has countries in s=")
            settle(pg); col = colours(pg)
            need(set(col) == set(CT), f"{name}: the colour expression names all {len(CT)} countries")
            sg = -1 if scheme == "dark" else 1
            vals = {cc: (mon["series"][t]["viirs_raw"][MI] or 0) for cc, t in CT.items()}
            hi, lo = max(vals, key=vals.get), min(vals, key=vals.get)
            need(vals[hi] > vals[lo] and sg * lum(col[hi]) < sg * lum(col[lo]), f"{name}: real national series: {hi} ({vals[hi]}) is drawn {'lighter' if scheme == 'dark' else 'darker'} than {lo} ({vals[lo]}) (the ramp reads more = {'lighter' if scheme == 'dark' else 'darker'} in this theme)")
            ranked = sorted((c for c in vals if vals[c] > 0), key=vals.get); need(all(sg * lum(col[a]) >= sg * lum(col[b]) - 1e-6 for a, b in zip(ranked, ranked[1:])), f"{name}: darkness follows the national value for every country with data")
            if SHOTS: pg.screenshot(path=f"{SHOTS}/ct-{name}-on.png")
            # own metric picker, kc= in link
            row = pg.locator('#onmap .lp-row[data-id="countries"]')
            sel = row.locator("#metric-country"); opts = [o.get_attribute("value") for o in sel.locator("option").all()]
            need(sel.count() == 1 and opts == ["viirs_eq", "modis_eq", "modis_raw", "viirs_raw"], f"{name}: Countries row has its own metric picker with the Provinces options {opts}")
            before = json.dumps(pg.evaluate("__map.getPaintProperty('regions-country','fill-color')")); sel.select_option("modis_raw"); settle(pg)
            need(json.dumps(pg.evaluate("__map.getPaintProperty('regions-country','fill-color')")) != before and "kc=modis_raw" in pg.url and pg.locator("#metric").evaluate("e=>e.value") == "viirs_raw", f"{name}: the picker changes the country colours and writes kc=modis_raw; the Provinces metric is untouched")
            # no free text in the row
            free = row.evaluate("""r=>{const c=r.cloneNode(true);c.querySelectorAll('.lp-name,select,.field span,button,[hidden]').forEach(e=>e.remove());return c.textContent.replace(/\\s+/g,' ').trim()}""")
            need(free == "", f"{name}: no free text in the Countries row ('{free}')")
            # (i): ramp text, opacity
            row.locator(".lp-info").scroll_into_view_if_needed(); row.locator(".lp-info").click(); pg.wait_for_timeout(300)
            txt = pg.locator(".lp-pop").inner_text(); base = pg.evaluate(OPC); pg.locator(".lp-pop input[type=range]").fill("50"); pg.wait_for_timeout(400); half = pg.evaluate(OPC)
            need("Darkest" in txt and "separate from the Provinces scale" in txt and abs(half - base * 0.5) < 1e-6 and "p=countries:0.5" in pg.url, f"{name}: (i) explains the per-level scale; opacity 50 % halves the overlay ({base:.2f} -> {half:.2f}), p=countries:0.5"); pg.keyboard.press("Escape")
            # click selects the country
            if w >= 1200:
                pg.evaluate("__map.jumpTo({center:[113.5,-1.8],zoom:5})"); settle(pg); pt = pg.evaluate("(()=>{const q=__map.project([113.5,-1.8]);return [q.x,q.y]})()")
                bb = pg.locator("#map").bounding_box(); pg.mouse.click(bb["x"] + pt[0], bb["y"] + pt[1]); pg.wait_for_timeout(1500)
                need(pg.locator("#country").input_value() == "IDN" and pg.locator("#region").input_value() == "indonesia", f"{name}: a click on Kalimantan selects Indonesia (country picker {pg.locator('#country').input_value()}, region {pg.locator('#region').input_value()})")
            # link round trip
            url = pg.url; load(pg, url[url.index("#"):])
            need("countries" in pg.evaluate(ONMAP) and pg.locator("#metric-country").input_value() == "modis_raw" and pg.evaluate(OPR) == 0 and abs(pg.evaluate(OPC) - half) < 1e-6, f"{name}: reload from the link restores Countries on, its metric and its opacity")
            load(pg, "#m=2019-09&r=all&k=viirs_raw&s=regions,countries&t=layers")
            need(pg.evaluate(ONMAP) == ["regions"] and pg.evaluate(OPC) == 0, f"{name}: a link with both levels on opens with Provinces only")
            load(pg, "#m=2019-09&r=all&k=viirs_raw&v=108,2,4.2&t=layers"); need("countries" not in pg.evaluate(ONMAP) and pg.evaluate(OPR) > 0 and pg.evaluate(OPC) == 0, f"{name}: a link without the new keys opens as before (Provinces on, Countries off)")
            # Provinces back: Countries off
            grp = pg.locator('#layers .lp-group[data-group="colour"]'); grp.scroll_into_view_if_needed(); grp.locator('.lp-crow[data-id="countries"] input').check(); pg.wait_for_timeout(500); grp.locator('.lp-crow[data-id="regions"] input').check(); pg.wait_for_timeout(500)
            need("countries" not in pg.evaluate(ONMAP) and pg.evaluate(OPC) == 0 and pg.evaluate(OPR) > 0, f"{name}: ticking Provinces again switches Countries off")
            need(pg.evaluate("document.documentElement.scrollWidth<=innerWidth"), f"{name}: no horizontal scroll")
            need(not errs, f"{name}: no console errors" + (f" {errs[:3]}" if errs else ""))
            ctx.close()
    b.close()
print("\nALL OK" if not fails else f"\n{len(fails)} FAILED")
sys.exit(1 if fails else 0)
