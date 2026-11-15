#!/usr/bin/env python3
"""Countries is the default region level on a fresh start. BUILT app or live site.
  uv run --with playwright python scripts/check_default_rows.py [base_url]      default http://127.0.0.1:4173/
390x844 and 1440x900, light and dark: a bare /app/ opens with Countries on and Provinces off (rows, map opacities, Details chip 'by country', click level 'country', a click on Kalimantan selects Indonesia);
the link the app writes always carries s=; a link copied after switching to Provinces reopens with Provinces; a state link WITHOUT s (written by an older version) keeps Provinces; rg=0 without s = no colouring at all; an explicit s= is obeyed;
an old format l/f link keeps Provinces; one level at a time still holds; no console errors."""
import sys
from playwright.sync_api import sync_playwright
BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:4173/").rstrip("/") + "/"
fails = []
def need(c, m):
    print(("ok   " if c else "FAIL ") + m, flush=True)
    if not c: fails.append(m)
def ready(pg): pg.wait_for_function("window.__appReady===true", timeout=90000)
def settle(pg):
    pg.wait_for_timeout(500)
    try: pg.evaluate("new Promise(r=>{const m=window.__map; if(m.loaded()&&!m.isMoving()) return r(); m.once('idle',r)})")
    except Exception: pass
    pg.wait_for_timeout(1000)
def load(pg, h=""):
    pg.goto("about:blank"); pg.goto(BASE + "app/" + h); ready(pg); settle(pg)
ONMAP = "[...document.querySelectorAll('#onmap .lp-row')].map(r=>r.dataset.id)"
OPR, OPC = "__map.getPaintProperty('regions','fill-opacity')", "__map.getPaintProperty('regions-country','fill-opacity')"
def state(pg): return pg.evaluate("({on:" + ONMAP + ",pr:" + OPR + ",pc:" + OPC + ",lvl:__clickLevel(),chip:document.getElementById('d-chip').textContent,hash:location.hash})")
with sync_playwright() as p:
    b = p.chromium.launch(args=["--use-gl=swiftshader", "--enable-unsafe-swiftshader"])
    for (w, h, tg) in ((390, 844, "phone"), (1440, 900, "desk")):
        for scheme in ("light", "dark"):
            name = f"{tg}-{scheme}"
            ctx = b.new_context(viewport={"width": w, "height": h}, color_scheme=scheme); pg = ctx.new_page(); errs = []
            pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None); pg.on("pageerror", lambda e: errs.append(str(e)))
            load(pg); s = state(pg)
            need("countries" in s["on"] and "regions" not in s["on"] and s["pr"] == 0 and s["pc"] > 0 and s["lvl"] == "country", f"{name}: bare /app/: Countries on, Provinces off (rows {s['on']}, opacity provinces {s['pr']}, countries {s['pc']:.2f}), click level {s['lvl']}")
            need("by country" in s["chip"], f"{name}: Details chip says '{s['chip']}'")
            need("s=" in s["hash"] and "countries" in s["hash"].split("s=")[1].split("&")[0], f"{name}: the link the app writes carries s= ({s['hash'][-60:]})")
            grp = pg.locator('#layers .lp-group[data-group="colour"]')
            if w < 1200: pg.click("#tab-layers"); pg.wait_for_timeout(200)
            need(grp.locator('.lp-crow[data-id="countries"] input').is_checked() and not grp.locator('.lp-crow[data-id="regions"] input').is_checked(), f"{name}: catalogue: Countries ticked, Provinces not")
            if w >= 1200:  # click on Kalimantan selects Indonesia
                pg.evaluate("__map.jumpTo({center:[113.5,-1.8],zoom:4})"); settle(pg); pt = pg.evaluate("(()=>{const q=__map.project([113.5,-1.8]);return [q.x,q.y]})()"); bb = pg.locator("#map").bounding_box()
                pg.mouse.click(bb["x"] + pt[0], bb["y"] + pt[1]); pg.wait_for_timeout(2000)
                need(pg.locator("#country").input_value() == "IDN" and pg.locator("#region").input_value() == "indonesia", f"{name}: a click on the map selects the country (country {pg.locator('#country').input_value()}, region {pg.locator('#region').input_value()})")
            # switch to Provinces, copy the link, reopen it
            grp.scroll_into_view_if_needed(); grp.locator('.lp-crow[data-id="regions"] input').check(); pg.wait_for_timeout(900); s2 = state(pg)
            need("regions" in s2["on"] and "countries" not in s2["on"] and s2["lvl"] == "region", f"{name}: ticking Provinces switches Countries off (rows {s2['on']})")
            url = pg.evaluate("location.hash"); load(pg, url); s3 = state(pg)
            need("regions" in s3["on"] and "countries" not in s3["on"] and s3["pr"] > 0 and s3["pc"] == 0, f"{name}: the copied link reproduces Provinces (rows {s3['on']})")
            # older links
            load(pg, "#m=2019-09&r=riau&k=viirs_raw&v=102,0.4,7.5"); s4 = state(pg)
            need("regions" in s4["on"] and "countries" not in s4["on"], f"{name}: a state link without s (older version) keeps Provinces (rows {s4['on']})")
            load(pg, "#m=2019-09&r=riau&k=viirs_raw&rg=0&v=102,0.4,7.5"); s5 = state(pg)
            need("regions" not in s5["on"] and "countries" not in s5["on"] and s5["pr"] == 0 and s5["pc"] == 0, f"{name}: a part-1 link (rg=0, no s) = no region colouring (rows {s5['on']})")
            load(pg, "#m=2019-09&r=riau&k=viirs_raw&f=viirs&l=loss&v=102,0.4,7.5"); s6 = state(pg)
            need("regions" in s6["on"] and "countries" not in s6["on"] and "loss" in s6["on"], f"{name}: an old format link (l/f) keeps Provinces (rows {s6['on']})")
            load(pg, "#m=2019-09&r=all&k=viirs_raw&s=fire-viirs&v=102,0.4,5"); s7 = state(pg)
            need(s7["on"] == ["fire-viirs"], f"{name}: an explicit s= is obeyed (rows {s7['on']})")
            load(pg, "#m=2019-09&r=all&k=viirs_raw&s=fire-viirs,countries&v=102,0.4,5"); s8 = state(pg)
            need(s8["on"][-1] == "countries" or "countries" in s8["on"], f"{name}: s= with countries opens with Countries on")
            load(pg, "#t=layers"); s9 = state(pg)
            need("countries" in s9["on"] and "regions" not in s9["on"], f"{name}: a link with only the open tab is a fresh start (rows {s9['on']})")
            need(pg.evaluate("document.documentElement.scrollWidth<=innerWidth"), f"{name}: no horizontal scroll")
            need(not errs, f"{name}: no console errors" + (f" {errs[:3]}" if errs else ""))
            ctx.close()
    b.close()
print("\nALL OK" if not fails else f"\n{len(fails)} FAILED")
sys.exit(1 if fails else 0)
