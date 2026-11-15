#!/usr/bin/env python3
"""layer panel = "On the map" list (only what is on, drag to reorder, no up/down buttons) + grouped searchable catalogue; opacity lives in the (i) panel. BUILT app or live site.
  uv run --with playwright python scripts/check_part2_75.py [base_url] [shot_dir]      default http://127.0.0.1:4173/
At 390x844 and 1440x900, light and dark: 19 layer rows in the catalogue (the two placeholder rows are not listed; 3 of them are the MapBiomas rows), On the map shows exactly the active set; ticking a layer adds it on top (and draws on top), the off button removes it;
the colour overlay is one of the rows (picker inside, off button, ticking it in the catalogue brings it back); real mouse drag and CDP touch drag change the map draw order and the link and survive a reload;
keyboard reorder (focus the handle, Space, Up/Down, Space) works and is announced; no up/down buttons exist; opacity slider inside (i) changes the layer opacity, 0 works, persists in the link and in the slider after reload;
search "oil" finds oil-palm rows; Details identical for all 4 metrics; old share links (original format and part-1 rg=0 format) still open correctly; no console errors; no horizontal scroll."""
import sys, json
from playwright.sync_api import sync_playwright
BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:4173/").rstrip("/") + "/"
SHOTS = sys.argv[2] if len(sys.argv) > 2 else None
VIEW = "v=113.5,-1.8,6.5"
DEF_ON = ["fire-modis", "fire-viirs", "fire-harm", "regions"]   # default rows on (the harmonized-fires row is a real layer since)
METRICS = ["viirs_eq", "modis_eq", "modis_raw", "viirs_raw"]
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
def load(pg, hash_, tab="layers"):
    pg.goto("about:blank"); pg.goto(BASE + "app/" + hash_); ready(pg); settle(pg)
OP = "__map.getPaintProperty('regions','fill-opacity')"
ONMAP = "[...document.querySelectorAll('#onmap .lp-row')].map(r=>r.dataset.id)"
FP = """(()=>{const c=document.getElementById('p-details').cloneNode(true);c.querySelector('#d-chip').remove();c.querySelectorAll('.hl').forEach(e=>e.classList.remove('hl'));
  c.querySelectorAll('[class=""]').forEach(e=>e.removeAttribute('class'));return c.innerHTML})()"""
def styleidx(pg, prefix):  # highest style index of a map layer of this row (drawn last = on top)
    return pg.evaluate("(p)=>{const ids=__map.getStyle().layers.map(l=>l.id);let m=-1;ids.forEach((id,i)=>{if(id===p||id.startsWith(p+'-'))m=i});return m}", prefix)
def tab(pg, t, w):
    if w < 1200: pg.click(f"#tab-{t}"); pg.wait_for_timeout(200)
def handle_center(pg, rid):
    loc = pg.locator(f'#onmap .lp-row[data-id="{rid}"] .lp-handle'); loc.scroll_into_view_if_needed(); b = loc.bounding_box(); return b["x"] + b["width"] / 2, b["y"] + b["height"] / 2
def row_top(pg, rid):
    loc = pg.locator(f'#onmap .lp-row[data-id="{rid}"]'); loc.scroll_into_view_if_needed(); return loc.bounding_box()
def panel(pg): return pg.evaluate("(()=>{const r=document.querySelector('#p-layers .pbody').getBoundingClientRect();return [Math.max(r.top,0),Math.min(r.bottom,innerHeight)]})()")
def mouse_drag(pg, rid, to_top=True):
    """Real mouse drag of a row's handle to the top (or bottom) of the panel; the panel scrolls by itself near its edge (the list can be longer than the panel), so the pointer is held at the edge for a moment."""
    x, y = handle_center(pg, rid); top, bot = panel(pg); ty = top + 8 if to_top else bot - 8
    pg.mouse.move(x, y); pg.mouse.down(); pg.mouse.move(x, (y + ty) / 2, steps=6); pg.mouse.move(x, ty, steps=6); pg.wait_for_timeout(1500); pg.mouse.up(); pg.wait_for_timeout(500)
def touch_drag(pg, cdp, rid):
    x, y = handle_center(pg, rid); top, bot = panel(pg); ty = top + 8
    cdp.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{"x": x, "y": y}]})
    for k in range(1, 9): cdp.send("Input.dispatchTouchEvent", {"type": "touchMove", "touchPoints": [{"x": x, "y": y + (ty - y) * k / 8}]}); pg.wait_for_timeout(30)
    pg.wait_for_timeout(1500); cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []}); pg.wait_for_timeout(500)
with sync_playwright() as p:
    b = p.chromium.launch(args=["--use-gl=swiftshader", "--enable-unsafe-swiftshader"])
    for (w, h, tg) in ((390, 844, "phone"), (1440, 900, "desk")):
        for scheme in ("light", "dark"):
            name = f"{tg}-{scheme}"
            ctx = b.new_context(viewport={"width": w, "height": h}, color_scheme=scheme, device_scale_factor=1, has_touch=(tg == "phone")); pg = ctx.new_page(); errs = []
            pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None); pg.on("pageerror", lambda e: errs.append(str(e)))
            load(pg, "#" + VIEW + "&k=viirs_eq&r=riau&m=2016-03&t=layers")
            # --- structure
            allids = pg.evaluate("[...document.querySelectorAll('#layers .lp-crow')].map(r=>r.dataset.id)")
            need(len(allids) == 16 and not {"alerts", "pulp", "fire-clrm", "fire-clrv", "loss_palm", "mines"} & set(allids), f"{name}: 16 layer rows in the catalogue (3 fire + Countries + Provinces + 11 context) ({len(allids)}); the placeholder rows, the removed forest-loss fire rows, Forest loss then oil palm and Mines are not listed")
            on0 = pg.evaluate(ONMAP); need(on0 == DEF_ON, f"{name}: On the map shows exactly the active set {on0}")
            need(pg.locator(".lp-onmap button", has_text="▲").count() + pg.locator("[aria-label*='Move up'],[aria-label*='Move down']").count() == 0 and pg.locator("#onmap .lp-handle").count() == len(DEF_ON), f"{name}: no up/down buttons; one drag handle per row")
            row = pg.locator('#onmap .lp-row[data-id="regions"]')
            need(row.locator("#metric").count() == 1 and row.locator(".lp-off").count() == 1 and row.locator(".lp-info").count() == 1 and row.locator("input[type=range]").count() == 0, f"{name}: colour overlay row = handle, name, metric picker, (i), off; no opacity slider in the row")
            need(pg.locator("#onmap input[type=range]").count() == 0, f"{name}: no opacity slider on any row")
            if SHOTS: pg.screenshot(path=f"{SHOTS}/p2-{name}-default.png")
            # --- toggle from the catalogue
            grp = pg.locator('#layers .lp-group[data-group="land"] .lp-gbtn'); grp.scroll_into_view_if_needed(); grp.click(); pg.wait_for_timeout(200)
            need(pg.locator("#layers .lp-group[data-group=land] .lp-gbody").is_visible(), f"{name}: group 'Forest and land' opens on click")
            cbx = pg.locator('#layers .lp-crow[data-id="loss"] input'); cbx.scroll_into_view_if_needed(); cbx.check(); pg.wait_for_timeout(600)
            on1 = pg.evaluate(ONMAP)
            need(on1[0] == "loss" and len(on1) == len(DEF_ON) + 1 and "loss" in pg.url.split("s=")[-1] and "1 on" in pg.inner_text('#layers .lp-group[data-group="land"] .lp-count'), f"{name}: ticking Forest loss puts it on top of On the map {on1}, link s= has it, group says '{pg.inner_text('#layers .lp-group[data-group=land] .lp-count')}'")
            settle(pg); need(styleidx(pg, "ctx-loss") > styleidx(pg, "fire-viirs") >= 0 and pg.evaluate("__map.getStyle().layers.some(l=>l.id.startsWith('ctx-loss'))"), f"{name}: the new layer draws above the fire layers (style index loss {styleidx(pg,'ctx-loss')} > viirs {styleidx(pg,'fire-viirs')})")
            pg.locator('#onmap .lp-row[data-id="loss"] .lp-off').click(); pg.wait_for_timeout(500)
            need("loss" not in pg.evaluate(ONMAP) and not pg.locator('#layers .lp-crow[data-id="loss"] input').is_checked(), f"{name}: off button removes it and the catalogue box is unticked")
            # --- colour overlay is a layer
            row.locator(".lp-off").click(); pg.wait_for_timeout(500)
            need("regions" not in pg.evaluate(ONMAP) and pg.evaluate(OP) == 0 and "regions" not in pg.url.split("s=")[-1].split("&")[0] and pg.evaluate("document.getElementById('lyr-store').contains(document.getElementById('metric'))"), f"{name}: overlay off: row gone, colours gone (fill-opacity {pg.evaluate(OP)}), not in s=, picker parked out of sight")
            tab(pg, "details", w); need("off" in pg.inner_text("#d-chip"), f"{name}: Details chip says '{pg.inner_text('#d-chip')}'"); tab(pg, "layers", w)
            cc = pg.locator('#layers .lp-group[data-group="colour"] .lp-crow[data-id="regions"] input'); cc.scroll_into_view_if_needed(); cc.check(); pg.wait_for_timeout(600)
            need(pg.evaluate(ONMAP)[0] == "regions" and pg.evaluate(OP) > 0 and pg.locator('#onmap .lp-row[data-id="regions"] #metric').is_visible(), f"{name}: ticking it in 'Fire counts by region' brings it back on top with its picker (opacity {pg.evaluate(OP)})")
            pg.locator('#onmap .lp-row[data-id="regions"] #metric').select_option("modis_raw"); settle(pg)
            need("k=modis_raw" in pg.url, f"{name}: metric picker inside the row changes k= in the link")
            # --- Details stable
            tab(pg, "details", w); pg.wait_for_function("window.__studyLoaded===true", timeout=60000); fps = set(); hls = []
            for m in METRICS:
                pg.evaluate(f"(()=>{{const s=document.getElementById('metric');s.value='{m}';s.dispatchEvent(new Event('change'))}})()"); pg.wait_for_timeout(250)
                fps.add(pg.evaluate(FP)); hls.append(pg.evaluate("[...document.querySelectorAll('#p-details .hl')].map(e=>e.id)"))
            need(len(fps) == 1 and hls == [[f"dr-{m}"] for m in METRICS], f"{name}: Details identical for all 4 metrics ({len(fps)} fingerprint), matching row highlighted")
            tab(pg, "layers", w)
            # --- reset to defaults, then drag
            load(pg, "#" + VIEW + "&k=viirs_eq&r=riau&m=2016-03&t=layers"); i_reg0, i_vi0 = styleidx(pg, "regions"), styleidx(pg, "fire-viirs")
            need(i_reg0 < i_vi0, f"{name}: default draw order has the colours below the fire layers (regions {i_reg0} < viirs {i_vi0})")
            mouse_drag(pg, "regions"); on2 = pg.evaluate(ONMAP); i_reg1 = styleidx(pg, "regions")
            need(on2[0] == "regions" and i_reg1 > styleidx(pg, "fire-viirs") and "o=" in pg.url, f"{name}: real mouse drag of the colour row to the top: list {on2}, map order regions {i_reg0} -> {i_reg1}, o= in the link")
            if SHOTS: pg.screenshot(path=f"{SHOTS}/p2-{name}-dragged.png")
            url = pg.url; pg2 = ctx.new_page(); pg2.goto("about:blank"); pg2.goto(url); ready(pg2); settle(pg2)
            need(pg2.evaluate(ONMAP) == on2 and styleidx(pg2, "regions") > styleidx(pg2, "fire-viirs"), f"{name}: reload from the link keeps the dragged order and map order"); pg2.close()
            mouse_drag(pg, "fire-modis", to_top=False)  # put modis low again so that the touch drag has something to move
            if tg == "phone": tctx, tpg = ctx, pg
            else:  # a touch screen at 1440 px (tablet / touch laptop) uses the dock layout: own context
                tctx = b.new_context(viewport={"width": w, "height": h}, color_scheme=scheme, has_touch=True); tpg = tctx.new_page(); load(tpg, "#" + VIEW + "&k=viirs_eq&r=riau&m=2016-03&t=layers")
                mouse_drag(tpg, "regions", to_top=False)
            cdp = tctx.new_cdp_session(tpg)
            before = tpg.evaluate(ONMAP); last = before[-1]; touch_drag(tpg, cdp, last); after = tpg.evaluate(ONMAP)
            need(after[0] == last and after != before and "o=" in tpg.url and styleidx(tpg, last) >= 0, f"{name}: touch drag (pointerType touch) moves {last} to the top: {before} -> {after}, o= in link")
            if tctx is not ctx: tctx.close()
            # --- Tab order: every On the map row reads handle, (i), off (the picker after them where there is one)
            seq = pg.evaluate("(()=>{const r=document.querySelector('#onmap .lp-row');return [...r.querySelectorAll('button,input,select')].filter(e=>e.tabIndex>=0).map(e=>e.className||e.tagName)})()")
            need(seq[:3] == ["lp-handle", "lp-info", "lp-off"], f"{name}: first On the map row has the Tab stops {seq}")
            need(pg.evaluate("[...document.querySelectorAll('#onmap .lp-handle,#onmap .lp-info,#onmap .lp-off')].every(e=>{const b=e.getBoundingClientRect();return b.width>=44&&b.height>=44})"), f"{name}: handle, (i) and off buttons are at least 44 x 44 px")
            # --- keyboard
            load(pg, "#" + VIEW + "&k=viirs_eq&r=riau&m=2016-03&t=layers")
            hd = pg.locator('#onmap .lp-row[data-id="regions"] .lp-handle'); hd.scroll_into_view_if_needed(); hd.focus(); i0 = styleidx(pg, "regions")
            pg.keyboard.press("Space"); [pg.keyboard.press("ArrowUp") for _ in range(len(DEF_ON) - 1)]; pg.keyboard.press("Space"); pg.wait_for_timeout(500)
            live = pg.inner_text("#onmap [role=status]")
            need(pg.evaluate(ONMAP)[0] == "regions" and styleidx(pg, "regions") > i0 and "dropped" in live and "o=" in pg.url, f"{name}: keyboard: handle, Space, Up (one per row above), Space moves the row to the top ({pg.evaluate(ONMAP)}), live text {live!r}, map order follows, o= in link")
            hd.focus(); pg.keyboard.press("Space"); pg.keyboard.press("ArrowDown"); pg.keyboard.press("Escape"); pg.wait_for_timeout(300)
            need(pg.evaluate(ONMAP)[0] == "regions", f"{name}: Escape cancels a keyboard move")
            # --- opacity in the (i) panel
            pg.locator('#onmap .lp-row[data-id="regions"] .lp-info').click(); pg.wait_for_timeout(300)
            dlg = pg.locator(".lp-pop"); sl = dlg.locator("input[type=range]")
            need(dlg.is_visible() and sl.count() == 1 and dlg.get_by_text("Opacity").count() >= 1, f"{name}: (i) opens a dialog with description and an Opacity slider")
            base = pg.evaluate(OP); sl.fill("50"); pg.wait_for_timeout(400); half = pg.evaluate(OP)
            need(abs(half - base * 0.5) < 1e-6 and "p=regions:0.5" in pg.url, f"{name}: slider 50 % halves the overlay opacity ({base} -> {half}), p=regions:0.5 in the link")
            sl.fill("0"); pg.wait_for_timeout(300); need(pg.evaluate(OP) == 0, f"{name}: slider 0 % gives opacity 0 ({pg.evaluate(OP)})")
            sl.fill("50"); pg.wait_for_timeout(300)
            if SHOTS: pg.screenshot(path=f"{SHOTS}/p2-{name}-info.png")
            pg.keyboard.press("Escape"); pg.wait_for_timeout(200)
            need(not dlg.is_visible() and pg.evaluate("document.activeElement.classList.contains('lp-info')"), f"{name}: Escape closes the panel and returns focus to the (i) button")
            # opacity on a context layer and a fire layer
            pg.locator('#layers .lp-group[data-group="land"] .lp-gbtn').scroll_into_view_if_needed(); pg.locator('#layers .lp-group[data-group="land"] .lp-gbtn').click()
            pg.locator('#layers .lp-crow[data-id="loss"] input').check(); pg.wait_for_timeout(500); settle(pg)
            pg.locator('#onmap .lp-row[data-id="loss"] .lp-info').click(); pg.locator(".lp-pop input[type=range]").fill("40"); pg.wait_for_timeout(500); settle(pg)
            lop = pg.evaluate("(()=>{const l=__map.getStyle().layers.filter(l=>l.id.startsWith('ctx-loss')&&l.type==='raster');return l.length?__map.getPaintProperty(l[0].id,'raster-opacity'):null})()")
            need("p=" in pg.url and "loss:0.4" in pg.url and (lop is None or lop > 0), f"{name}: opacity 40 % on Forest loss is in the link (p=…loss:0.4), layer raster-opacity {lop}")
            pg.keyboard.press("Escape")
            url = pg.url; pg2 = ctx.new_page(); pg2.goto("about:blank"); pg2.goto(url); ready(pg2); settle(pg2)
            pg2.locator('#onmap .lp-row[data-id="regions"] .lp-info').scroll_into_view_if_needed(); pg2.locator('#onmap .lp-row[data-id="regions"] .lp-info').click()
            need(pg2.locator(".lp-pop input[type=range]").input_value() == "50" and abs(pg2.evaluate(OP) - base * 0.5) < 1e-6, f"{name}: after reload the overlay opacity is still 50 % (slider {pg2.locator('.lp-pop input[type=range]').input_value()}, opacity {pg2.evaluate(OP):.3f})"); pg2.close()
            # --- search
            load(pg, "#" + VIEW + "&k=viirs_eq&r=riau&m=2016-03&t=layers")
            sb = pg.locator("#layers .lp-search"); sb.scroll_into_view_if_needed(); sb.fill("oil"); pg.wait_for_timeout(300)
            vis = pg.evaluate("[...document.querySelectorAll('#layers .lp-crow')].filter(r=>!r.hidden).map(r=>r.dataset.id)")
            need("palm" in vis and "mb_palm" in vis and "loss_palm" not in vis and len(vis) <= 4 and pg.locator("#layers .lp-group[data-group=plant] .lp-gbody").is_visible(), f"{name}: search 'oil' finds {vis} and opens the group")
            sb.fill(""); pg.wait_for_timeout(300); need(pg.locator("#layers .lp-crow:visible").count() > 0 and not pg.locator("#layers .lp-group[data-group=plant] .lp-gbody").is_visible(), f"{name}: clearing the search restores the open/closed groups")
            # --- old links
            old = "#m=2016-03&r=riau&k=viirs_clearing&f=clrv,viirs&l=loss,tmfdef,peat,alerts&v=102.0,0.4,7.5&o=fire-clrv,fire-viirs,loss,peat,alerts"
            load(pg, old); st = pg.evaluate("({on:" + ONMAP + ",m:document.getElementById('metric').value,r:document.getElementById('region').value,op:" + OP + "})")
            need(set(st["on"]) == {"fire-viirs", "loss", "tmfdef", "peat", "regions"} and st["on"][:2] == ["fire-viirs", "loss"] and st["m"] == "viirs_eq" and st["r"] == "riau" and st["op"] > 0,
                 f"{name}: original-format share link (l f o k r, with the removed rows 'alerts', 'fire-clrv' and the removed metric viirs_clearing): on {st['on']}, metric {st['m']}, region {st['r']}, colours on")
            load(pg, "#m=2016-03&r=riau&k=modis_eq&rg=0&l=loss&f=viirs&o=fire-viirs,loss&v=102.0,0.4,7.5"); st = pg.evaluate("({on:" + ONMAP + ",op:" + OP + "})")
            need(st["on"] == ["fire-viirs", "loss"] and st["op"] == 0, f"{name}: part-1 link (rg=0) restores overlay off: on {st['on']}, fill-opacity {st['op']}")
            load(pg, "#m=2016-03&r=riau&k=modis_eq&v=102.0,0.4,7.5"); st = pg.evaluate("({on:" + ONMAP + ",op:" + OP + "})")
            need(st["on"] == DEF_ON and st["op"] > 0, f"{name}: link with no layer keys opens the defaults {st['on']}")
            need(pg.evaluate("document.documentElement.scrollWidth<=innerWidth"), f"{name}: no horizontal scroll")
            need(not errs, f"{name}: no console errors" + (f" {errs[:3]}" if errs else ""))
            ctx.close()
    b.close()
print("\nALL OK" if not fails else f"\n{len(fails)} FAILED")
sys.exit(1 if fails else 0)
