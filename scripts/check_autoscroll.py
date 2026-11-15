#!/usr/bin/env python3
"""dragging a row of "On the map" near the top or bottom edge of the panel scrolls the panel (a list longer than the panel used to end at the screen edge: on a phone the row could not be dropped further down). BUILT app or live site.
  uv run --with playwright python scripts/check_autoscroll86.py [base_url]      default http://127.0.0.1:4173/
390x844 (mouse and CDP touch) and 1440x900 (mouse), light and dark: with every layer on, drag the first row to the bottom edge and hold: the panel scrolls, the row moves down the list, the draw order and the link follow; dragging inside the panel
does not scroll it; dragging a lower row to the top edge scrolls back up."""
import sys
from playwright.sync_api import sync_playwright
BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:4173/").rstrip("/") + "/"
fails = []
def need(c, m):
    print(("ok   " if c else "FAIL ") + m, flush=True)
    if not c: fails.append(m)
def ready(pg): pg.wait_for_function("window.__appReady===true", timeout=90000)
ONMAP = "[...document.querySelectorAll('#onmap .lp-row')].map(r=>r.dataset.id)"
ALL = "regions,fire-viirs,fire-modis,fire-harm,loss,drivers,peat,palm,mb_palm,mb_pulp,mb_mine,burned,tmfdef,tmfdeg,plantation"
with sync_playwright() as p:
    b = p.chromium.launch(args=["--use-gl=swiftshader", "--enable-unsafe-swiftshader"])
    for (w, h, tg, touch) in ((390, 844, "phone", False), (390, 844, "phone-touch", True), (1440, 900, "desk", False)):
        for scheme in ("light", "dark"):
            name = f"{tg}-{scheme}"
            ctx = b.new_context(viewport={"width": w, "height": h}, color_scheme=scheme, has_touch=touch); pg = ctx.new_page(); errs = []
            pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None); pg.on("pageerror", lambda e: errs.append(str(e)))
            pg.goto("about:blank"); pg.goto(BASE + "app/#m=2019-09&r=all&k=viirs_raw&s=" + ALL + "&v=113,-2,6&t=layers"); ready(pg); pg.wait_for_timeout(2500)
            sc = pg.evaluate("(()=>{const e=document.querySelector('#p-layers .pbody');return {sh:e.scrollHeight,ch:e.clientHeight,top:e.scrollTop}})()")
            rows = pg.evaluate(ONMAP); need(len(rows) >= 10 and sc["sh"] > sc["ch"] + 50, f"{name}: the list ({len(rows)} rows) is longer than the panel (scrollHeight {sc['sh']} > clientHeight {sc['ch']})")
            box = pg.evaluate("(()=>{const r=document.querySelector('#p-layers .pbody').getBoundingClientRect();return [r.top,r.bottom]})()")
            first = rows[0]; hd = pg.locator(f'#onmap .lp-row[data-id="{first}"] .lp-handle'); hd.scroll_into_view_if_needed(); bb = hd.bounding_box(); x, y0 = bb["x"] + bb["width"] / 2, bb["y"] + bb["height"] / 2
            pg.evaluate("document.querySelector('#p-layers .pbody').scrollTop=0")
            cdp = ctx.new_cdp_session(pg) if touch else None
            def down(x, y):
                if cdp: cdp.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{"x": x, "y": y}]})
                else: pg.mouse.move(x, y); pg.mouse.down()
            def move(x, y):
                if cdp: cdp.send("Input.dispatchTouchEvent", {"type": "touchMove", "touchPoints": [{"x": x, "y": y}]})
                else: pg.mouse.move(x, y)
            def up(x, y):
                if cdp: cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
                else: pg.mouse.up()
            # inside the panel, away from the edges: no scrolling
            mid = (box[0] + box[1]) / 2; down(x, y0); move(x, y0 + 8); move(x, min(mid, y0 + 60)); pg.wait_for_timeout(600); st = pg.evaluate("document.querySelector('#p-layers .pbody').scrollTop"); up(x, mid); pg.wait_for_timeout(300)
            need(st == 0, f"{name}: dragging inside the panel does not scroll it (scrollTop {st})")
            # to the bottom edge and hold
            rows = pg.evaluate(ONMAP); first = rows[0]; hd = pg.locator(f'#onmap .lp-row[data-id="{first}"] .lp-handle'); bb = hd.bounding_box(); x, y0 = bb["x"] + bb["width"] / 2, bb["y"] + bb["height"] / 2
            ey = min(box[1], h) - 14
            down(x, y0)
            for k in range(1, 9): move(x, y0 + (ey - y0) * k / 8); pg.wait_for_timeout(30)
            pg.wait_for_timeout(2200); sc2 = pg.evaluate("document.querySelector('#p-layers .pbody').scrollTop"); mid_order = pg.evaluate(ONMAP).index(first); up(x, ey); pg.wait_for_timeout(500)
            after = pg.evaluate(ONMAP)
            need(sc2 > 100, f"{name}: held at the bottom edge the panel scrolled by {sc2:.0f} px")
            need(after.index(first) >= len(after) - 3 and mid_order >= len(after) - 3, f"{name}: the dragged row ({first}) followed down to position {after.index(first) + 1} of {len(after)}")
            need("o=" in pg.url or "s=" in pg.url, f"{name}: the new order is in the link")
            # and back up
            last = after[-1]; hd = pg.locator(f'#onmap .lp-row[data-id="{after[-2]}"] .lp-handle'); hd.scroll_into_view_if_needed(); bb = hd.bounding_box(); x, y0 = bb["x"] + bb["width"] / 2, bb["y"] + bb["height"] / 2
            top_before = pg.evaluate("document.querySelector('#p-layers .pbody').scrollTop"); ty = max(box[0], 0) + 12
            down(x, y0)
            for k in range(1, 9): move(x, y0 + (ty - y0) * k / 8); pg.wait_for_timeout(30)
            pg.wait_for_timeout(2200); top_after = pg.evaluate("document.querySelector('#p-layers .pbody').scrollTop"); up(x, ty); pg.wait_for_timeout(400)
            need(top_after < top_before - 50 or top_before == 0, f"{name}: held at the top edge the panel scrolls back up ({top_before:.0f} -> {top_after:.0f})")
            need(not errs, f"{name}: no console errors" + (f" {errs[:3]}" if errs else ""))
            ctx.close()
    b.close()
print("\nALL OK" if not fails else f"\n{len(fails)} FAILED")
sys.exit(1 if fails else 0)
