#!/usr/bin/env python3
"""MapBiomas rows mb_palm, mb_pulp, mb_mine, mode cumfile like "Oil palm". BUILT app or live site.
  uv run --with playwright --with pillow python scripts/check_mapbiomas80.py [base_url] [shot_dir] [--only phone-light|phone-dark|desk-light|desk-dark]      default http://127.0.0.1:4173/
At 390x844 and 1440x900, light and dark: the three rows (Oil palm / Pulpwood plantation / Mining, each "(MapBiomas)") are in the group "Plantations and mines", off by default, with no variant picker;
ticking one adds it on top of On the map and to the link; the slider year picks the file (source ctx-<row>-<year>, 2023 for later years) and moving it swaps the file; opacity in the (i) works; drag reorder works;
the (i) panel shows source, licence, legend and the caveats; for each of the ten known sites of  the 7 x 7 pixels at the site are the basemap before the site's first year
and the expected class colour (alpha from the tile) from it on, up to 2023, on the plain basemap, and on the satellite basemap for one site per class; with Country = Malaysia the layer is flagged as no data there; over Bangkok nothing is drawn;
no failed MapBiomas file request, no console errors, no horizontal scroll."""
import sys, json, io, pathlib
from playwright.sync_api import sync_playwright
from PIL import Image
A = [x for x in sys.argv[1:] if not x.startswith("--")]
BASE = (A[0] if A else "http://127.0.0.1:4173/").rstrip("/") + "/"
SHOTS = A[1] if len(A) > 1 else None
ONLY = next((sys.argv[i + 1] for i, x in enumerate(sys.argv) if x == "--only"), None)   # e.g. --only phone-light: run one viewport/theme combination (the four can run in parallel)
SITES = json.loads((pathlib.Path(__file__).parent / "mapbiomas_sites.json").read_text())
CLS = {"palm": "mb_palm", "pulp": "mb_pulp", "mine": "mb_mine"}
NAMES = {"mb_palm": "Oil palm (MapBiomas)", "mb_pulp": "Pulpwood plantation (MapBiomas)", "mb_mine": "Mining (MapBiomas)"}
OPACITY = 0.85
fails = []
def need(c, m):
    print(("ok   " if c else "FAIL ") + m, flush=True)
    if not c: fails.append(m)
def ready(pg): pg.wait_for_function("window.__appReady===true", timeout=90000)
def settle(pg):
    pg.wait_for_timeout(400)
    try: pg.evaluate("new Promise(r=>{const m=window.__map; if(m.loaded()&&!m.isMoving()) return r(); m.once('idle',r)})")
    except Exception: pass
    pg.wait_for_timeout(500)
def load(pg, hash_):
    pg.goto("about:blank"); pg.goto(BASE + "app/" + hash_); ready(pg); settle(pg)
ONMAP = "[...document.querySelectorAll('#onmap .lp-row')].map(r=>r.dataset.id)"
def styleidx(pg, prefix): return pg.evaluate("(p)=>{const ids=__map.getStyle().layers.map(l=>l.id);let m=-1;ids.forEach((id,i)=>{if(id===p||id.startsWith(p+'-'))m=i});return m}", prefix)
def srcs(pg, rid): return pg.evaluate("(r)=>Object.keys(__map.getStyle().sources).filter(k=>k.startsWith('ctx-'+r+'-'))", rid)
def ropac(pg, rid): return pg.evaluate("(r)=>{const l=__map.getStyle().layers.find(l=>l.id.startsWith('ctx-'+r+'-')&&l.type==='raster');return l?__map.getPaintProperty(l.id,'raster-opacity'):null}", rid)
def tab(pg, t, w):
    if w < 1200: pg.click(f"#tab-{t}"); pg.wait_for_timeout(200)
def open_group(pg):
    g = pg.locator('#layers .lp-group[data-group="plant"]')
    if not g.locator(".lp-gbody").is_visible(): g.locator(".lp-gbtn").scroll_into_view_if_needed(); g.locator(".lp-gbtn").click(); pg.wait_for_timeout(200)
def pixel(pg, x, y):
    b = pg.screenshot(clip={"x": x, "y": y, "width": 1, "height": 1}); return Image.open(io.BytesIO(b)).convert("RGB").getpixel((0, 0))
def region(pg, x, y, r=3):
    """(2r+1)^2 pixels around (x,y) as a list of RGB tuples"""
    b = pg.screenshot(clip={"x": x - r, "y": y - r, "width": 2 * r + 1, "height": 2 * r + 1}); im = Image.open(io.BytesIO(b)).convert("RGB"); return list(im.getdata())
def count_match(shown, base, rgba):
    """pixels of the window that are the class colour at its tile alpha, drawn at layer opacity OPACITY over the pixel's own basemap colour (tolerance 6 per channel)"""
    r, g, b_, a = rgba; k = OPACITY * a / 255
    return sum(1 for s_, q in zip(shown, base) if close_enough(s_, tuple(round(k * c + (1 - k) * v) for c, v in zip((r, g, b_), q))) and not close_enough(s_, q, 3))
def count_base(shown, base): return sum(1 for s_, q in zip(shown, base) if close_enough(s_, q, 3))
HIDE = "body *{visibility:hidden!important} #map,#map *{visibility:visible!important} .maplibregl-control-container,.maplibregl-control-container *{visibility:hidden!important}"
def close_enough(a, b, tol=6): return all(abs(int(p) - int(q)) <= tol for p, q in zip(a, b))
def set_year(pg, y): pg.evaluate("(i)=>{const s=document.getElementById('slider');s.value=i;s.dispatchEvent(new Event('input',{bubbles:true}));s.dispatchEvent(new Event('change',{bubbles:true}))}", (y - 2001) * 12 + 5)
def opac_all(pg, rid, v): pg.evaluate("([r,v])=>__map.getStyle().layers.filter(l=>l.id.startsWith('ctx-'+r+'-')&&l.type==='raster').forEach(l=>__map.setPaintProperty(l.id,'raster-opacity',v))", [rid, v])
def site_xy(pg): x, y = pg.evaluate("()=>{const c=__map.getCanvas().getBoundingClientRect();return [c.left+c.width/2,c.top+c.height/2]}"); return int(x), int(y)
def site_years(pg, rid, s, label="", years=None):
    """walk the slider through the fixture years of one site (layer drawn only from the file of the selected year); base = layer hidden"""
    ys = [int(k) for k in s["rgba_by_year"]] if years is None else years
    pg.evaluate("([lon,lat])=>__map.jumpTo({center:[lon,lat],zoom:13})", [s["lon"], s["lat"]]); set_year(pg, ys[0]); settle(pg); pg.wait_for_timeout(1200)
    x, y = site_xy(pg); opac_all(pg, rid, 0); pg.wait_for_timeout(900); base = region(pg, x, y); res = []
    for yr in ys:
        set_year(pg, yr); settle(pg); pg.wait_for_timeout(1500); shown = region(pg, x, y); exp = s["rgba_by_year"][str(yr)]
        if exp is None: res.append((yr, "nothing", count_base(shown, base) >= 40, count_base(shown, base)))
        else: n = count_match(shown, base, exp); res.append((yr, "class colour", n >= 10, n))
    return res

with sync_playwright() as p:
    b = p.chromium.launch(args=["--use-gl=swiftshader", "--enable-unsafe-swiftshader"])
    for (w, h, tg) in ((390, 844, "phone"), (1440, 900, "desk")):
        for scheme in ("light", "dark"):
            name = f"{tg}-{scheme}"
            if ONLY and ONLY != name: continue
            ctx = b.new_context(viewport={"width": w, "height": h}, color_scheme=scheme, device_scale_factor=1, has_touch=(tg == "phone")); pg = ctx.new_page(); errs = []; badreq = []; mbreq = []
            pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None); pg.on("pageerror", lambda e: errs.append(str(e)))
            pg.on("response", lambda r: (mbreq.append(r.status), badreq.append((r.status, r.url)) if r.status >= 400 else None) if "/mapbiomas/" in r.url else None)
            load(pg, "#v=104.0,-1.8,7&m=2005-06&t=layers")
            # --- structure
            open_group(pg)
            ids = pg.evaluate("[...document.querySelectorAll('#layers .lp-group[data-group=plant] .lp-crow')].map(r=>r.dataset.id)")
            need(ids[-3:] == ["mb_palm", "mb_pulp", "mb_mine"], f"{name}: the three rows are in the group 'Plantations and mines': {ids}")
            names = pg.evaluate("[...document.querySelectorAll('#layers .lp-crow')].filter(r=>r.dataset.id.startsWith('mb_')).map(r=>r.querySelector('.lp-name').textContent)")
            need(names == list(NAMES.values()), f"{name}: row names {names}")
            need(not any(i.startswith("mb_") for i in pg.evaluate(ONMAP)) and not srcs(pg, "mb_palm") and not srcs(pg, "mb_pulp"), f"{name}: all three off by default (not in On the map, nothing on the map)")
            need(pg.locator("select[data-var]").count() == 0, f"{name}: no variant picker anywhere")
            # --- switch on, slider year picks the file
            for r_ in ("mb_pulp", "mb_palm", "mb_mine"):
                c_ = pg.locator(f'#layers .lp-crow[data-id="{r_}"] input'); c_.scroll_into_view_if_needed(); c_.check(); pg.wait_for_timeout(400)
            settle(pg); on3 = pg.evaluate(ONMAP)
            need(on3[:3] == ["mb_mine", "mb_palm", "mb_pulp"] and "mb_pulp" in pg.url.split("s=")[-1] and "3 on" in pg.inner_text('#layers .lp-group[data-group="plant"] .lp-count'), f"{name}: ticking the three rows puts each on top of On the map {on3[:3]}; link has them; group count '{pg.inner_text('#layers .lp-group[data-group=plant] .lp-count')}'")
            need(srcs(pg, "mb_pulp") == ["ctx-mb_pulp-2005"] and srcs(pg, "mb_palm") == ["ctx-mb_palm-2005"], f"{name}: slider at Jun 2005: files {srcs(pg, 'mb_pulp')} {srcs(pg, 'mb_palm')}")
            if SHOTS: pg.screenshot(path=f"{SHOTS}/mapbiomas-{name}-2005.png")
            set_year(pg, 2015); settle(pg); pg.wait_for_timeout(800)
            need(srcs(pg, "mb_pulp") == ["ctx-mb_pulp-2015"] and srcs(pg, "mb_mine") == ["ctx-mb_mine-2015"], f"{name}: slider to 2015 swaps the files: {srcs(pg, 'mb_pulp')} {srcs(pg, 'mb_mine')}")
            if SHOTS: pg.screenshot(path=f"{SHOTS}/mapbiomas-{name}-2015.png")
            set_year(pg, 2025); settle(pg); pg.wait_for_timeout(800)
            need(srcs(pg, "mb_pulp") == ["ctx-mb_pulp-2023"], f"{name}: slider at 2025 shows the last year, 2023: {srcs(pg, 'mb_pulp')}")
            set_year(pg, 2010); settle(pg)
            # --- info panel
            pg.locator('#onmap .lp-row[data-id="mb_palm"] .lp-info').click(); pg.wait_for_timeout(300)
            dlg = pg.locator(".lp-pop"); txt = dlg.inner_text()
            for k, m in (("MapBiomas Indonesia Collection 4 v2", "source"), ("CC BY-SA", "licence"), ("plus or minus 2 years", "accuracy"), ("inflated", "2001 edge effect"), ("12 %", "12 % below Descals"), ("Papua", "Papua"), ("2023", "data end")):
                need(k in txt, f"{name}: info panel of Oil palm (MapBiomas) has {m} ({k!r})")
            need("mportant" not in txt or ("first became the class" in txt and "only grows" in txt and "raw map" in txt), f"{name}: if the panel has an Important block it carries the 'first became the class / only grows / not the raw map' sentence")
            if SHOTS: pg.screenshot(path=f"{SHOTS}/mapbiomas-{name}-info.png")
            base = ropac(pg, "mb_palm"); sl = dlg.locator("input[type=range]"); sl.fill("50"); pg.wait_for_timeout(500)
            need(abs(ropac(pg, "mb_palm") - base * 0.5) < 1e-6 and "mb_palm:0.5" in pg.url, f"{name}: slider 50 % halves the layer opacity ({base} -> {ropac(pg, 'mb_palm')}), p= in the link")
            sl.fill("100"); pg.wait_for_timeout(300); pg.keyboard.press("Escape"); pg.wait_for_timeout(200)
            # --- drag reorder
            hd = pg.locator('#onmap .lp-row[data-id="mb_pulp"] .lp-handle'); first = pg.locator('#onmap .lp-row[data-id="mb_mine"]'); first.scroll_into_view_if_needed(); fb = first.bounding_box(); bb = hd.bounding_box()
            x, y = bb["x"] + bb["width"] / 2, bb["y"] + bb["height"] / 2; ty = fb["y"] + 3
            pg.mouse.move(x, y); pg.mouse.down(); pg.mouse.move(x, (y + ty) / 2, steps=6); pg.mouse.move(x, ty, steps=6); pg.mouse.up(); pg.wait_for_timeout(600); settle(pg)
            on4 = pg.evaluate(ONMAP)
            need(on4[0] == "mb_pulp" and styleidx(pg, "ctx-mb_pulp") > styleidx(pg, "ctx-mb_mine") and "o=" in pg.url, f"{name}: mouse drag of the pulpwood row to the top: {on4[:3]}, map order follows, o= in link")
            if SHOTS: pg.screenshot(path=f"{SHOTS}/mapbiomas-{name}-three.png")
            # --- outside Indonesia
            for r_ in ("mb_pulp", "mb_mine"): pg.locator(f'#layers .lp-crow[data-id="{r_}"] input').uncheck()
            pg.evaluate("document.getElementById('sel').open=true"); pg.select_option("#country", value="MYS"); pg.wait_for_timeout(900); settle(pg)
            tag = pg.inner_text('#onmap .lp-row[data-id="mb_palm"] .lp-tag').strip().lower() if pg.locator('#onmap .lp-row[data-id="mb_palm"] .lp-tag:visible').count() else ""
            pg.locator('#onmap .lp-row[data-id="mb_palm"] .lp-info').click(); pg.wait_for_timeout(300); t2 = pg.locator(".lp-pop").inner_text(); pg.keyboard.press("Escape")
            need(tag == "no data here" or ("Malaysia" in t2 and ("Not available in" in t2 or "No data here" in t2 or "no data here" in t2)), f"{name}: Country = Malaysia: row chip '{tag}', (i) panel says Malaysia has no data: {'Not available in' in t2}")
            pg.evaluate("()=>__map.jumpTo({center:[100.50,13.75],zoom:8})"); settle(pg); pg.wait_for_timeout(500); pg.add_style_tag(content=HIDE); pg.wait_for_timeout(200)
            x, y = site_xy(pg); opac_all(pg, "mb_palm", 0); pg.wait_for_timeout(900); b0 = pixel(pg, x, y); opac_all(pg, "mb_palm", OPACITY); pg.wait_for_timeout(900); b1 = pixel(pg, x, y)
            need(close_enough(b0, b1, 2), f"{name}: over Bangkok (outside Indonesia) the layer draws nothing: pixel {b0} with the layer hidden, {b1} shown")
            need(not any(s >= 400 for s in mbreq) and len(mbreq) > 0, f"{name}: every MapBiomas tile-file request succeeded ({len(mbreq)} requests, failed: {badreq[:2]})")
            need(pg.evaluate("document.documentElement.scrollWidth<=innerWidth"), f"{name}: no horizontal scroll")
            need(not errs, f"{name}: no console errors" + (f" {errs[:3]}" if errs else ""))
            ctx.close()
            # --- known sites, additive through the years (separate page per class)
            for cls, rid in CLS.items():
                ctx = b.new_context(viewport={"width": w, "height": h}, color_scheme=scheme, device_scale_factor=1); pg = ctx.new_page(); errs = []
                pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None); pg.on("pageerror", lambda e: errs.append(str(e)))
                load(pg, f"#v=113.5,-1.8,6.5&m=2005-06&s={rid}"); pg.add_style_tag(content=HIDE)
                for s in [s for s in SITES if s["cls"] == cls and s["found"]]:
                    res = site_years(pg, rid, s)
                    need(all(r[2] for r in res), f"{name}: {s['site']} (first year {s['source_first_year']}): " + "; ".join(f"{r[0]} {r[1]} {'ok' if r[2] else 'FAIL'} ({r[3]}/49)" for r in res))
                need(not errs, f"{name}: no console errors on the {cls} sites page" + (f" {[e[:160] for e in errs[:2]]}" if errs else ""))
                s = next(s for s in SITES if s["cls"] == cls and s["found"])
                load(pg, f"#v=113.5,-1.8,6.5&m=2023-06&s={rid}&b=sat"); pg.add_style_tag(content=HIDE); pg.wait_for_timeout(1500)
                res = site_years(pg, rid, s, "sat", years=[2023])
                need(all(r[2] for r in res), f"{name}: satellite basemap, {s['site']}: " + "; ".join(f"{r[0]} {r[1]} {'ok' if r[2] else 'FAIL'} ({r[3]}/49)" for r in res))
                if SHOTS and cls == "palm": pg.screenshot(path=f"{SHOTS}/mapbiomas-{name}-sat-site.png")
                ctx.close()
    b.close()
print("\nALL OK" if not fails else f"\n{len(fails)} FAILED")
sys.exit(1 if fails else 0)
