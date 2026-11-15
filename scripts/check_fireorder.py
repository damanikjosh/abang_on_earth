"""Move the VIIRS fire row below Forest loss (keyboard on its drag handle), check the map stack, hard reload restores, move back.
uv run --with playwright python scripts/check_fireorder.py [base_url]"""
import sys
from playwright.sync_api import sync_playwright
BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:4173/"
IDLE = "new Promise(r=>{const m=window.__map;const f=()=>m.loaded()&&!m.isMoving()?r():m.once('idle',r);requestAnimationFrame(()=>requestAnimationFrame(f))})"
ROWS = "[...document.querySelectorAll('#onmap .lp-row')].map(r=>r.dataset.id)"
STACK = "(()=>{const L=__map.getStyle().layers.map(l=>l.id);const last=(p)=>{let k=-1;L.forEach((id,i)=>{if(id.startsWith(p))k=i});return k};return {fireV:last('fire-viirs'),loss:last('ctx-loss-'),regions:last('regions')}})()"
fails = []
with sync_playwright() as p:
    b = p.chromium.launch(args=["--use-gl=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"])
    pg = b.new_page(viewport={"width": 1440, "height": 900}); errs = []
    pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
    pg.goto(BASE + "app/#m=2019-09&l=loss"); pg.wait_for_function("window.__appReady===true"); pg.wait_for_timeout(2000); pg.evaluate(IDLE)
    rows = pg.evaluate(ROWS); print("start", rows); s0 = pg.evaluate(STACK); print(s0)
    if not s0["fireV"] > s0["loss"]: fails.append("fire not above loss by default")
    g = pg.locator("#onmap .lp-row[data-id=fire-viirs] .lp-handle"); g.focus(); pg.keyboard.press("Space")  # keyboard: Space picks the row up, arrows move it, Space drops it
    for _ in range(rows.index("loss") - rows.index("fire-viirs")): pg.keyboard.press("ArrowDown")
    pg.keyboard.press("Space")
    pg.wait_for_timeout(500); pg.evaluate(IDLE); r1 = pg.evaluate(ROWS); s1 = pg.evaluate(STACK); print("moved", r1, s1)
    if not (r1.index("fire-viirs") > r1.index("loss") and s1["fireV"] < s1["loss"]): fails.append("fire not below loss after move")
    pg.wait_for_timeout(400); pg.reload(); pg.wait_for_function("window.__appReady===true"); pg.wait_for_timeout(2000); pg.evaluate(IDLE)
    r2 = pg.evaluate(ROWS); s2 = pg.evaluate(STACK); print("reload", r2, s2)
    if r2 != r1 or not s2["fireV"] < s2["loss"]: fails.append("order not restored after reload")
    pg.locator("#onmap .lp-row[data-id=fire-viirs] .lp-handle").focus(); pg.keyboard.press("Space")
    for _ in range(r2.index("fire-viirs")): pg.keyboard.press("ArrowUp")
    pg.keyboard.press("Space")
    pg.wait_for_timeout(500); pg.evaluate(IDLE); r3 = pg.evaluate(ROWS); s3 = pg.evaluate(STACK); print("back", r3, s3)
    if not (r3.index("fire-viirs") < r3.index("loss") and s3["fireV"] > s3["loss"]): fails.append("move back failed")
    if errs: fails.append(f"console errors {errs[:3]}")
    b.close()
print("FAIL" if fails else "PASS", fails)
