#!/usr/bin/env python3
"""Day / Night boxes inside the MODIS fires row. Needs a build whose manifest gives the modis layer `classes` (Day id 1, Night id 2, tiles for 2002-09 only);
the preview on http://127.0.0.1:4186/ has them (test tiles overlaid on dist/, not in git).
  uv run --with playwright --with pillow --with numpy python scripts/check_daynight86.py [base_url] [shot_dir]
At 390x844 and 1440x900, light and dark: both boxes present and ticked; unticking Night hides the night points (z9.5) and the night density cells (z7) and changes the pixels, Day stays;
unticking Day does the converse; both off draws nothing and says so; x=fire-modis:2 in the link, restored on reload, bad class numbers ignored, old links unchanged; a month without split tiles
(2002-10, 2019-09) is drawn from the layer's own file exactly as before and says where day and night can be told apart; opacity from the (i) panel reaches the class layers; moving the row moves its class layers; keyboard; no console errors."""
import sys, io
from playwright.sync_api import sync_playwright
from PIL import Image
import numpy as np
BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:4186/").rstrip("/") + "/"
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
    pg.wait_for_timeout(1200)
def load(pg, h):
    pg.goto("about:blank"); pg.goto(BASE + "app/" + h); ready(pg); settle(pg)
def px(pg): return np.asarray(Image.open(io.BytesIO(pg.locator("#map").screenshot())).convert("RGB")).astype(float)
def vis(pg, pre="fire-modis"): return pg.evaluate("(p)=>Object.fromEntries(__map.getStyle().layers.filter(l=>l.id.startsWith(p)).map(l=>[l.id,l.layout.visibility||'visible']))", pre)
def hidden(v, k): return v.get(k, "none") == "none"  # a class that was never switched on has no layer yet: that is hidden too
def rendered(pg, layer): return pg.evaluate("(l)=>__map.getLayer(l)?__map.queryRenderedFeatures({layers:[l]}).length:-1", layer)
def box(pg, n): return pg.locator(f"#lyr-fire-modis input[data-cls='{n}']")
M = "m=2002-09&r=all&k=modis_raw&s=fire-modis"
Z95 = "&v=112.580,-2.933,9.5"; Z7 = "&v=112.580,-2.933,7"
with sync_playwright() as p:
    b = p.chromium.launch(args=["--use-gl=swiftshader", "--enable-unsafe-swiftshader"])
    for (w, h, tg) in ((390, 844, "phone"), (1440, 900, "desk")):
        for scheme in ("light", "dark"):
            name = f"{tg}-{scheme}"
            ctx = b.new_context(viewport={"width": w, "height": h}, color_scheme=scheme, device_scale_factor=1); pg = ctx.new_page(); errs = []
            pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None); pg.on("pageerror", lambda e: errs.append(str(e)))
            # --- points (z 9.5)
            load(pg, "#" + M + Z95 + "&t=layers")
            row = pg.locator('#onmap .lp-row[data-id="fire-modis"]')
            labels = pg.evaluate("[...document.querySelectorAll('#lyr-fire-modis .cls')].map(e=>e.innerText.trim()+':'+e.querySelector('input').checked)")
            need(labels == ["Day:true", "Night:true"] and row.locator("#lyr-fire-modis .cls").count() == 2, f"{name}: the MODIS row holds two labelled boxes, Day and Night, both ticked {labels}")
            v0 = vis(pg); need(all(x == "visible" for x in v0) and set(v0) == {"fire-modis_1-2002-09-dens", "fire-modis_1-2002-09-pts", "fire-modis_2-2002-09-dens", "fire-modis_2-2002-09-pts"}, f"{name}: 2002-09 is drawn from the day and the night file (and not from the layer's own file): {sorted(v0)}")
            d0, n0 = rendered(pg, "fire-modis_1-2002-09-pts"), rendered(pg, "fire-modis_2-2002-09-pts")
            need(d0 > 0 and n0 > 0, f"{name}: points on screen at z9.5: day {d0}, night {n0}")
            if SHOTS: pg.screenshot(path=f"{SHOTS}/dn-{name}-both.png")
            im0 = px(pg)
            box(pg, 2).scroll_into_view_if_needed(); box(pg, 2).uncheck(); settle(pg)
            v1 = vis(pg); d1, n1 = rendered(pg, "fire-modis_1-2002-09-pts"), rendered(pg, "fire-modis_2-2002-09-pts")
            need(hidden(v1, "fire-modis_2-2002-09-pts") and hidden(v1, "fire-modis_2-2002-09-dens") and v1["fire-modis_1-2002-09-pts"] == "visible", f"{name}: unticking Night hides the night points and cells, Day stays")
            need(n1 <= 0 and d1 == d0, f"{name}: night points on screen {n0} -> {max(n1,0)}, day points {d0} -> {d1}")
            diff = float((np.abs(im0 - px(pg)).max(axis=2) > 12).mean())
            need(diff > 0.0005, f"{name}: the map pixels change ({diff*100:.2f} % of pixels)")
            need("x=fire-modis:2" in pg.url, f"{name}: link has x=fire-modis:2 ({pg.url.split('&x=')[-1][:24]})")
            need("Day only" in pg.text_content("#ls-fire-modis") and not pg.locator("#ls-fire-modis").is_visible(), f"{name}: the status sentence '{pg.text_content('#ls-fire-modis')}' exists but is not drawn in the row")
            if SHOTS: pg.screenshot(path=f"{SHOTS}/dn-{name}-dayonly.png")
            box(pg, 2).check(); box(pg, 1).uncheck(); settle(pg); v2 = vis(pg)
            need(hidden(v2, "fire-modis_1-2002-09-pts") and v2["fire-modis_2-2002-09-pts"] == "visible" and "x=fire-modis:1" in pg.url, f"{name}: Night only: day hidden, night shown, x=fire-modis:1")
            box(pg, 2).uncheck(); settle(pg)
            need(all(x == "none" for x in vis(pg).values()) and "both off" in pg.text_content("#ls-fire-modis") and "fire-modis:1.2" in pg.url, f"{name}: both off draws nothing, x=fire-modis:1.2")
            box(pg, 1).check(); box(pg, 2).check(); settle(pg)
            need(all(x == "visible" for x in vis(pg).values()) and "x=" not in pg.url, f"{name}: ticking both again restores everything and removes x= from the link")
            # --- density cells (z 7)
            load(pg, "#" + M + Z7 + "&t=layers")
            dd, dn = rendered(pg, "fire-modis_1-2002-09-dens"), rendered(pg, "fire-modis_2-2002-09-dens"); imb = px(pg)
            need(dd > 0 and dn > 0, f"{name}: density cells at z7: day {dd}, night {dn}")
            box(pg, 2).scroll_into_view_if_needed(); box(pg, 2).uncheck(); settle(pg)
            d2 = float((np.abs(imb - px(pg)).max(axis=2) > 12).mean()); need(rendered(pg, "fire-modis_2-2002-09-dens") <= 0 and rendered(pg, "fire-modis_1-2002-09-dens") == dd and d2 > 0.0005, f"{name}: unticking Night removes the night cells ({dn} -> 0) and changes the density picture ({d2*100:.2f} % of pixels)")
            if SHOTS: pg.screenshot(path=f"{SHOTS}/dn-{name}-z7-dayonly.png")
            # --- link round trip
            url = pg.url; load(pg, url[url.index("#"):])
            need(not box(pg, 2).is_checked() and box(pg, 1).is_checked() and hidden(vis(pg), "fire-modis_2-2002-09-pts") and vis(pg)["fire-modis_1-2002-09-dens"] == "visible", f"{name}: reload from the link restores Night off, Day on")
            load(pg, "#" + M + Z7 + "&x=fire-modis:9.zz~nope:1&t=layers")
            need(box(pg, 1).is_checked() and box(pg, 2).is_checked(), f"{name}: unknown class numbers and rows in x= are ignored")
            load(pg, "#m=2002-09&r=all&k=modis_raw&f=modis&v=112.580,-2.933,7")  # old link: no s, no x
            need(box(pg, 1).is_checked() and box(pg, 2).is_checked() and "fire-modis" in pg.evaluate("[...document.querySelectorAll('#onmap .lp-row')].map(r=>r.dataset.id)"), f"{name}: an old link (f=modis, no x) opens with both boxes ticked and MODIS on")
            # --- other months
            load(pg, "#" + M.replace("2002-09", "2002-10") + Z7 + "&t=layers"); v = vis(pg)
            need(v and all(k.startswith("fire-modis-2002-10") and x == "visible" for k, x in v.items()), f"{name}: 2002-10 (no split tiles) is drawn from the layer's own file: {sorted(v)}")
            box(pg, 2).scroll_into_view_if_needed(); need(box(pg, 1).is_disabled() and box(pg, 2).is_disabled() and box(pg, 1).is_checked() and box(pg, 2).is_checked() and box(pg, 2).get_attribute("aria-disabled") == "true", f"{name}: in a month without class tiles both boxes are greyed (disabled, aria-disabled) and ticked: the row keeps its shape")
            row.locator(".lp-info").click(); pg.wait_for_timeout(300); mt = pg.locator('.lp-pop [data-sec="month"] p').inner_text(); pg.keyboard.press("Escape")
            need("2002-09" in mt and "told apart" in mt, f"{name}: the (i) panel, 'This month', says where Day and Night can be told apart: '{mt}'")
            load(pg, "#m=2019-08&r=all&k=modis_raw&v=112.580,-2.933,7&t=layers"); v = vis(pg)
            need(v and all(k.startswith("fire-modis-2019-08") for k in v), f"{name}: 2019-08 is drawn from the layer's own file")
            # --- VIIRS day / night (tiles for 2019-09 only) and the choice surviving a month without tiles
            VM = "m=2019-09&r=all&k=modis_raw&s=fire-viirs&v=112.580,-2.933,7&t=layers"; vb = lambda n: pg.locator(f"#lyr-fire-viirs input[data-cls='{n}']")
            load(pg, "#" + VM); vv = vis(pg, "fire-viirs")
            need(set(vv) == {"fire-viirs_1-2019-09-dens", "fire-viirs_1-2019-09-pts", "fire-viirs_2-2019-09-dens", "fire-viirs_2-2019-09-pts"} and all(x == "visible" for x in vv.values()) and vb(1).is_checked() and vb(2).is_checked() and not vb(1).is_disabled(), f"{name}: VIIRS row has Day and Night, both ticked and working in 2019-09; drawn from the class files")
            vb(2).scroll_into_view_if_needed(); vb(2).uncheck(); settle(pg); vv = vis(pg, "fire-viirs")
            need(hidden(vv, "fire-viirs_2-2019-09-pts") and hidden(vv, "fire-viirs_2-2019-09-dens") and vv["fire-viirs_1-2019-09-pts"] == "visible" and "x=fire-viirs:2" in pg.url, f"{name}: unticking VIIRS Night hides the night points and cells, x=fire-viirs:2")
            pg.evaluate("(()=>{const e=document.getElementById('slider');e.value=String(Number(e.value)-1);e.dispatchEvent(new Event('input',{bubbles:true}))})()"); settle(pg)
            need(vb(1).is_disabled() and vb(2).is_disabled() and vb(2).is_checked() and "x=fire-viirs:2" in pg.url, f"{name}: in 2019-08 (no tiles) the boxes are greyed and ticked, but the link still remembers Night off")
            pg.evaluate("(()=>{const e=document.getElementById('slider');e.value=String(Number(e.value)+1);e.dispatchEvent(new Event('input',{bubbles:true}))})()"); settle(pg)
            need(not vb(2).is_checked() and not vb(2).is_disabled() and hidden(vis(pg, "fire-viirs"), "fire-viirs_2-2019-09-pts"), f"{name}: back in 2019-09 the Night choice is restored")
            # --- opacity and order reach the class layers
            load(pg, "#" + M + Z95 + "&t=layers")
            row.locator(".lp-info").scroll_into_view_if_needed(); row.locator(".lp-info").click(); pg.locator(".lp-pop input[type=range]").fill("50"); pg.wait_for_timeout(500)
            o1, o2 = (pg.evaluate("(l)=>__map.getPaintProperty(l,'circle-opacity')", f"fire-modis_{k}-2002-09-pts") for k in (1, 2))
            need(abs(o1 - 0.175) < 1e-6 and abs(o2 - 0.175) < 1e-6, f"{name}: opacity 50 % from the (i) panel reaches both class layers (circle-opacity {o1:.3f}, {o2:.3f})"); pg.keyboard.press("Escape")
            hd = pg.locator('#onmap .lp-row[data-id="regions"] .lp-handle')
            if hd.count():
                hd.scroll_into_view_if_needed(); hd.focus(); i0 = pg.evaluate("__map.getStyle().layers.map(l=>l.id).indexOf('regions')")
                pg.keyboard.press("Space"); [pg.keyboard.press("ArrowUp") for _ in range(4)]; pg.keyboard.press("Space"); pg.wait_for_timeout(500)
                ids = pg.evaluate("__map.getStyle().layers.map(l=>l.id)"); last = lambda pre: max(i for i, x in enumerate(ids) if x.startswith(pre))
                first = lambda pre: min(i for i, x in enumerate(ids) if x.startswith(pre))
                need(ids.index("regions") > last("fire-modis_1-") and ids.index("regions") > last("fire-modis_2-") and abs(first("fire-modis_2-") - last("fire-modis_1-")) <= 4, f"{name}: the colour row dragged above MODIS draws above both class layers; the two stay together (day {first('fire-modis_1-')}-{last('fire-modis_1-')}, night {first('fire-modis_2-')}-{last('fire-modis_2-')}, regions {ids.index('regions')})")
            # --- rows hold controls only (Joshua's rule): no free text in any row of either list
            load(pg, "#" + M + Z7 + "&s=fire-modis,fire-viirs,fire-harm,loss,regions,drivers&t=layers")
            free = pg.evaluate("""(()=>{const bad=[];for(const r of document.querySelectorAll('#onmap .lp-row,#layers .lp-crow')){const c=r.cloneNode(true);
              c.querySelectorAll('.lp-name,label.cls,select,.field span,.var-row label,button,[hidden],.sr,.lp-sr').forEach(e=>e.remove());
              const t=c.textContent.replace(/\\s+/g,' ').trim();const vis=[...r.querySelectorAll('.ls,.gap,.cls-hint,.var-legend,.legend,.lp-tag,.kchip')].filter(e=>e.offsetParent!==null).length;
              if(t||vis)bad.push(r.dataset.id+': '+t.slice(0,60)+' / visible helpers '+vis)}return bad})()""")
            need(not free, f"{name}: no row of 'On the map' or the catalogue contains free text {free[:3]}")
            names = pg.evaluate("[...document.querySelectorAll('#onmap .lp-name')].map(e=>e.innerText)")
            need("MODIS" in names and "VIIRS" in names and "Harmonized VIIRS" in names and not any(n in ("MODIS fires", "VIIRS fires") for n in names), f"{name}: row names MODIS / VIIRS / Harmonized VIIRS {names}")
            need(pg.evaluate("[...document.querySelectorAll('#onmap .lp-name,#layers .lp-name')].every(e=>e.scrollWidth<=e.clientWidth+1)"), f"{name}: no layer name is cut off")
            # --- Harmonized VIIRS: Night works, Day is disabled for good
            hb = lambda n: pg.locator(f"#lyr-fire-harm input[data-cls='{n}']")
            need(hb(1).is_disabled() and hb(1).get_attribute("aria-disabled") == "true" and not hb(1).is_checked() and hb(2).is_checked() and not hb(2).is_disabled(), f"{name}: Harmonized VIIRS: Day greyed, aria-disabled, not ticked; Night ticked and tickable")
            need(not pg.locator("#lyr-fire-harm .cls-hint").is_visible() and "night passes only" in (pg.locator("#lyr-fire-harm .cls.dis").get_attribute("title") or ""), f"{name}: the reason for the disabled Day is not drawn in the row (title only)")
            hv = vis(pg, "fire-harm"); need(hv and all(x == "visible" for x in hv.values()), f"{name}: harmonized layer drawn for 2002-09 ({len(hv)} map layers)")
            hb(2).scroll_into_view_if_needed(); hb(2).uncheck(); settle(pg)
            need(all(x == "none" for x in vis(pg, "fire-harm").values()) and "x=fire-harm:2" in pg.url, f"{name}: unticking Night hides the harmonized points and cells, x=fire-harm:2")
            hb(1).evaluate("e=>e.click()"); pg.wait_for_timeout(300); need(not hb(1).is_checked() and "fire-harm:1" not in pg.url, f"{name}: a click on the disabled Day does nothing and never reaches the link")
            load(pg, "#" + M + Z7 + "&s=fire-harm&x=fire-harm:2&t=layers"); need(not hb(2).is_checked() and all(x == "none" for x in vis(pg, "fire-harm").values()), f"{name}: x=fire-harm:2 restores Night off")
            load(pg, "#" + M + Z7 + "&s=fire-harm&x=fire-harm:1&t=layers"); need(not hb(1).is_checked() and hb(1).is_disabled() and hb(2).is_checked() and "fire-harm:1" not in pg.url, f"{name}: x=fire-harm:1 (Day) in a link is ignored, the layer still shows")
            # --- no data this month: dimmed row, dot on (i), reason in (i)
            load(pg, "#" + M + Z7 + "&s=fire-modis,fire-viirs&t=layers"); vr = pg.locator('#onmap .lp-row[data-id="fire-viirs"]')
            need("lp-na" in (vr.get_attribute("class") or "") and "lp-na" not in (pg.locator('#onmap .lp-row[data-id="fire-modis"]').get_attribute("class") or ""), f"{name}: VIIRS has no data in 2002-09: its row is dimmed, MODIS is not")
            badge = vr.locator(".lp-info").evaluate("e=>getComputedStyle(e,'::after').content"); lab = vr.locator(".lp-info").get_attribute("aria-label"); vr.locator(".lp-info").click(); pg.wait_for_timeout(300)
            first = pg.evaluate("document.querySelector('.lp-pop .lp-pop-body').firstElementChild.className"); imp = pg.locator(".lp-pop .lp-pop-imp").inner_text()
            heads = pg.evaluate("[...document.querySelectorAll('.lp-pop .lp-pop-sec h3')].map(e=>e.textContent)"); mt = pg.locator('.lp-pop [data-sec="month"] p').inner_text(); pg.keyboard.press("Escape")
            need(badge == '"!"' and lab.endswith("important information") and first == "lp-pop-imp" and "No VIIRS data before" in imp and "What it shows" in heads and "This month" in heads and "No VIIRS data before" in mt, f"{name}: red '!' badge on (i) ({lab}); the panel starts with the important block ('{imp[:60]}...'), then {heads}")
            load(pg, "#" + M + Z7 + "&s=fire-modis,fire-harm&t=layers"); plain = pg.locator('#onmap .lp-row[data-id="fire-modis"] .lp-info'); hi = pg.locator('#onmap .lp-row[data-id="fire-harm"] .lp-info')
            need(plain.evaluate("e=>getComputedStyle(e,'::after').content") in ("none", "normal") and plain.get_attribute("aria-label") == "About MODIS" and hi.evaluate("e=>getComputedStyle(e,'::after').content") == '"!"', f"{name}: MODIS has a plain (i) in 2002-09, Harmonized VIIRS has the badge")
            hi.click(); pg.wait_for_timeout(300); txt = pg.locator(".lp-pop .lp-pop-imp").inner_text(); cols = pg.evaluate("(()=>{const e=document.querySelector('.lp-pop .lp-pop-imp'),p=e.querySelector('p'),f=x=>x.match(/[\\d.]+/g).map(Number);return [f(getComputedStyle(e).backgroundColor),f(getComputedStyle(p).color)]})()"); pg.keyboard.press("Escape")
            lum = lambda c: sum(w * (((v / 255) / 12.92) if v / 255 <= 0.03928 else (((v / 255) + 0.055) / 1.055) ** 2.4) for w, v in zip((0.2126, 0.7152, 0.0722), c[:3])); sc = lambda c: [x * 255 for x in c[:3]] if max(c[:3]) <= 1 else c[:3]; l1, l2 = lum(sc(cols[0])), lum(sc(cols[1])); cr = (max(l1, l2) + 0.05) / (min(l1, l2) + 0.05)
            need("Model output, experimental" in txt and "Night only; day is not computed" in txt and "failed 3 of its 4" in txt and cr >= 4.5, f"{name}: Harmonized VIIRS important block carries the sentences; text on its tinted background has contrast {cr:.1f}:1")
            # --- keyboard
            load(pg, "#" + M + Z7 + "&t=layers"); box(pg, 2).scroll_into_view_if_needed(); box(pg, 2).focus(); pg.keyboard.press("Space"); settle(pg)
            need(not box(pg, 2).is_checked() and hidden(vis(pg), "fire-modis_2-2002-09-pts"), f"{name}: the Night box toggles with Space from the keyboard")
            need(pg.evaluate("document.documentElement.scrollWidth<=innerWidth"), f"{name}: no horizontal scroll")
            need(not errs, f"{name}: no console errors" + (f" {errs[:3]}" if errs else ""))
            ctx.close()
    b.close()
print("\nALL OK" if not fails else f"\n{len(fails)} FAILED")
sys.exit(1 if fails else 0)
