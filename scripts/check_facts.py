#!/usr/bin/env python3
""" live check of the homepage Facts row. BUILT site (npm run build; serve dist on 4191 or 4193) or the live site.
  uv run --with playwright python scripts/check_facts91.py http://127.0.0.1:4191/ [--shots DIR]
Checks: the row (id=facts) exists once and has 5 cards; every card has a diagram whose drawn marks are non-empty and whose text is at least 12 px at the card size; the row is placed before the technical report row;
at 390 and 1440 px, light and dark: no horizontal scroll, no console error; the homepage nav is unchanged (Home, App, Credits; no new page); every "Open on the map" link is loaded in the app, one at a time:
the layers named by s= are exactly the rows on the map, the month shown is the month in the link, the map centre and zoom match v=, class boxes in x= are unticked, tiles are loaded with no HTTP error and no console error.
With --panels (a build that has the view keys cal= and pn=): also which of the Layers card, Details card and calendar are shown, and that Play is reachable, at 1440x900, 1440x780, 820x1180 and 390x844. One headless browser at a time. Then it presses the Play control of each link and checks the month advances one step at a time to the action month named in facts_links.json, layers stay on, tiles load, no error. Exit 1 on any failure."""
import sys, re, pathlib
from urllib.parse import parse_qsl
from playwright.sync_api import sync_playwright
args = [a for a in sys.argv[1:] if not a.startswith("--")]
BASE = (args[0] if args else "http://127.0.0.1:4191/").rstrip("/") + "/"
SHOTS = pathlib.Path(sys.argv[sys.argv.index("--shots") + 1]) if "--shots" in sys.argv else None
if SHOTS: SHOTS.mkdir(parents=True, exist_ok=True)
fails = []
def need(c, m):
    print(("ok   " if c else "FAIL ") + m, flush=True)
    if not c: fails.append(m)
MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
with sync_playwright() as p:
    b = p.chromium.launch(args=["--use-gl=swiftshader", "--enable-unsafe-swiftshader"])
    links = []
    for w, scheme in ((390, "light"), (390, "dark"), (1440, "light"), (1440, "dark")):
        ctx = b.new_context(viewport={"width": w, "height": 900 if w > 500 else 844}, color_scheme=scheme, has_touch=w < 500, is_mobile=w < 500); pg = ctx.new_page()
        errs = []; pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None); pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto(BASE); pg.wait_for_timeout(1500); tag = f"{w}px {scheme}"
        need(pg.evaluate("document.querySelectorAll('#facts').length") == 1, f"[{tag}] one #facts row")
        need(pg.evaluate("document.querySelectorAll('#facts article.fact').length") == 5, f"[{tag}] 5 cards")
        need(pg.evaluate("document.documentElement.scrollWidth") <= w, f"[{tag}] no horizontal scroll (scrollWidth {pg.evaluate('document.documentElement.scrollWidth')})")
        need(pg.evaluate("(()=>{const f=document.getElementById('facts'),pp=document.getElementById('paper'),r=document.getElementById('research');return !!(f.compareDocumentPosition(pp)&4)&&!!(r.compareDocumentPosition(f)&4)})()"), f"[{tag}] Facts row sits after the research row and before the technical report row")
        need(pg.evaluate("[...document.querySelectorAll('.hdr nav a')].map(a=>a.textContent.trim()).join('|')") == "Home|App|Credits", f"[{tag}] header nav unchanged (Home|App|Credits)")
        d = pg.evaluate("""[...document.querySelectorAll('#facts article.fact')].map(a=>{const s=a.querySelector('svg.fx'),r=s.getBoundingClientRect(),k=r.width/360;
          const marks=s.querySelectorAll('polyline,rect.bar-ac,rect.bar-mu').length, vis=[...s.querySelectorAll('polyline,rect.bar-ac,rect.bar-mu')].filter(e=>{const q=e.getBoundingClientRect();return q.width>0&&q.height>=0}).length;
          const minpx=Math.min(...[...s.querySelectorAll('text')].map(t=>parseFloat(getComputedStyle(t).fontSize)*k)); const b=s.getBoundingClientRect(), inside=[...s.querySelectorAll('text')].every(t=>{const q=t.getBoundingClientRect();return q.left>=b.left-1&&q.right<=b.right+1});
          return {marks,vis,minpx,inside,w:r.width,btn:a.querySelectorAll('a[data-fact-link]').length,keep:/What to keep in mind/.test(a.textContent),src:/Source:/.test(a.textContent)}})""")
        for i, c in enumerate(d, 1):
            need(c["marks"] > 0 and c["vis"] == c["marks"], f"[{tag}] fact {i}: diagram has {c['marks']} drawn marks, all with a box")
            need(c["minpx"] >= 12, f"[{tag}] fact {i}: smallest diagram text {c['minpx']:.1f} px (>= 12)")
            need(c["inside"], f"[{tag}] fact {i}: no diagram text outside the drawing")
            need(c["btn"] >= 1 and c["keep"] and c["src"], f"[{tag}] fact {i}: button, 'What to keep in mind', 'Source'")
        if not links: links = pg.evaluate("[...document.querySelectorAll('#facts a[data-fact-link]')].map(a=>[a.dataset.factLink,a.getAttribute('href')])")
        if SHOTS:
            pg.locator("#facts").screenshot(path=str(SHOTS / f"facts_{w}_{scheme}.png"))
            for i in range(1, 6): pg.locator(f"#fact-{i}").screenshot(path=str(SHOTS / f"fact{i}_{w}_{scheme}.png"))
        need(not errs, f"[{tag}] no console error {errs[:2]}")
        ctx.close()
    need(len(links) == 5 and len({l[0] for l in links}) == 5, f"exactly 5 map links on the page, one per fact ({[l[0] for l in links]})")
    import json
    meta = {l["id"]: l for l in json.loads((pathlib.Path(__file__).resolve().parent / "facts_links.json").read_text())["links"]}
    # every link, in the app, one at a time
    ctx = b.new_context(viewport={"width": 1440, "height": 900}, color_scheme="light"); pg = ctx.new_page()
    bad = []; pg.on("console", lambda m: bad.append(m.text) if m.type == "error" else None); pg.on("pageerror", lambda e: bad.append(str(e)))
    pg.on("response", lambda r: bad.append(f"HTTP {r.status} {r.url}") if r.status >= 400 else None)
    pg.on("requestfailed", lambda r: bad.append(f"failed {r.url} {r.failure}") if "ERR_ABORTED" not in str(r.failure) else None)  # aborts happen when this script navigates away; they are not page errors
    for lid, href in links:
        bad.clear(); q = dict(parse_qsl(href.split("#", 1)[1], keep_blank_values=True))
        need("s" in q and q["s"] != "", f"[{lid}] link carries an explicit s=")
        pg.goto("about:blank"); pg.goto(BASE + href); pg.wait_for_load_state("domcontentloaded"); bad.clear()  # a fresh page load per link, as a visitor clicking the button gets
        pg.wait_for_function("window.__appReady===true", timeout=120000)
        pg.wait_for_function("window.__map.areTilesLoaded() && !window.__map.isMoving()", timeout=90000); pg.wait_for_timeout(2500)
        pg.wait_for_function("window.__map.areTilesLoaded()", timeout=60000)
        on = pg.evaluate("[...document.querySelectorAll('.lp-onmap li.lp-row[data-id]')].map(e=>e.dataset.id).sort().join(',')")
        need(on == ",".join(sorted(q["s"].split(","))), f"[{lid}] layers on the map = s= ({on})")
        y, m = q["m"].split("-"); lab = f"{MON[int(m)-1]} {y}"
        shown = pg.evaluate("document.querySelector('.tl-month output')?.textContent.trim()")
        need(shown == lab, f"[{lid}] month shown {shown!r} = {lab!r}")
        lng, lat, z = map(float, q["v"].split(",")); c = pg.evaluate("(()=>{const c=__map.getCenter();return [c.lng,c.lat,__map.getZoom()]})()")
        need(abs(c[0] - lng) < .02 and abs(c[1] - lat) < .02 and abs(c[2] - z) < .02, f"[{lid}] view {c[0]:.3f},{c[1]:.3f},{c[2]:.2f} = link {lng},{lat},{z}")
        for rc in [x.split(":") for x in q.get("x", "").split("~") if x]:
            for cls in rc[1].split("."):
                ok = pg.evaluate(f"(()=>{{const e=document.querySelector('input[data-row=\"{rc[0]}\"][data-cls=\"{cls}\"]');return !!e&&!e.checked}})()")
                need(ok, f"[{lid}] {rc[0]} class {cls} is switched off")
        need(pg.evaluate("__map.areTilesLoaded()"), f"[{lid}] tiles loaded")
        need(not bad, f"[{lid}] no HTTP error, no console error {bad[:2]}")
        if SHOTS: pg.screenshot(path=str(SHOTS / f"map_{lid}.png"))
        # Play: press the month player, watch the month advance one step at a time up to the action month, layers stay on, tiles load, no error
        bad.clear(); act = meta[lid]["action"]; ay, am = act.split("-"); alab = f"{MON[int(am)-1]} {ay}"
        pg.click("#play"); seen = [shown]
        import time; t0 = time.time()
        while time.time() - t0 < 90:
            cur = pg.evaluate("document.querySelector('.tl-month output')?.textContent.trim()")
            if cur != seen[-1]: seen.append(cur)
            if cur == alab: break
            pg.wait_for_timeout(80)
        need(seen[-1] == alab, f"[{lid}] Play: months stepped through {seen[0]} .. {seen[-1]} ({len(seen)-1} steps)")
        def idx(l): return int(l.split()[1]) * 12 + MON.index(l.split()[0])
        need(len(seen) >= 3 and all(idx(b2) - idx(a2) == 1 for a2, b2 in zip(seen, seen[1:])), f"[{lid}] Play: the month advanced one month at a time")
        pg.click("#play"); pg.wait_for_function("window.__map.areTilesLoaded()", timeout=60000); pg.wait_for_timeout(1500)
        on2 = pg.evaluate("[...document.querySelectorAll('.lp-onmap li.lp-row[data-id]')].map(e=>e.dataset.id).sort().join(',')")
        need(on2 == on and pg.evaluate("document.getElementById('play').getAttribute('aria-pressed')") == "false", f"[{lid}] Play: layers still on after the run ({on2}), player paused again")
        need(pg.evaluate("__map.areTilesLoaded()"), f"[{lid}] Play: tiles of the later months loaded")
        need(not bad, f"[{lid}] Play: no HTTP error, no console error {bad[:2]}")
        if SHOTS: pg.screenshot(path=str(SHOTS / f"play_{lid}.png"))
    ctx.close()
    # panels (needs a build with the view keys cal= and pn=): which of Layers card / Details card / calendar are shown after load, and Play is reachable, at four sizes
    if "--panels" in sys.argv:
        for w, h in ((1440, 900), (1440, 780), (820, 1180), (390, 844)):
            touch = w < 500; ctx = b.new_context(viewport={"width": w, "height": h}, color_scheme="light", has_touch=touch, is_mobile=touch); pg = ctx.new_page()
            for lid, href in links:
                q = dict(parse_qsl(href.split("#", 1)[1], keep_blank_values=True)); pg.goto("about:blank"); pg.goto(BASE + href); pg.wait_for_function("window.__appReady===true", timeout=120000); pg.wait_for_timeout(1500)
                got = pg.evaluate("""(()=>{const d=document.getElementById('dock'),dr=document.getElementById('drawer'),pl=document.getElementById('p-layers'),pd=document.getElementById('p-details'),pb=document.getElementById('play').getBoundingClientRect();
                  const e=document.elementFromPoint(pb.left+pb.width/2,pb.top+pb.height/2);
                  return {dockLayout:getComputedStyle(d).position!=='static'&&innerWidth<1200||matchMedia('(pointer:coarse)').matches,tab:d.dataset.tab,open:d.dataset.open,drawer:dr.dataset.open,
                    layers:!pl.hasAttribute('data-collapsed'),details:!pd.hasAttribute('data-collapsed'),playOK:pb.width>0&&pb.bottom<=innerHeight&&pb.top>=0&&!!e&&(e.id==='play'||!!e.closest('#play')),playOn:!document.getElementById('play').disabled}})()""")
                pn = q.get("pn"); cal = q.get("cal")
                if not got["dockLayout"]:
                    el, ed = ("l" in pn, "d" in pn) if pn is not None else (True, True); ec = (cal == "1") if cal is not None else (h >= 820)
                    need(got["layers"] == el and got["details"] == ed and (got["drawer"] == "1") == ec, f"[{lid} {w}x{h}] wide panels: layers={got['layers']} details={got['details']} calendar={got['drawer']} (want {el} {ed} {ec})")
                else:
                    tab = q.get("t") or (None if pn is None else ("layers" if "l" in pn else "details" if "d" in pn else "folded")) or "timeline"
                    ok = (got["open"] == "0") if tab == "folded" else (got["open"] == "1" and got["tab"] == tab)
                    ok = ok and (cal is None or (got["drawer"] == cal))
                    need(ok, f"[{lid} {w}x{h}] dock: tab={got['tab']} open={got['open']} drawer={got['drawer']} (want {tab}, cal={cal})")
                need(got["playOK"] and got["playOn"], f"[{lid} {w}x{h}] Play is visible, enabled and not covered")
                if got["playOK"]:
                    m0 = pg.evaluate("document.querySelector('.tl-month output')?.textContent.trim()"); pg.click("#play"); pg.wait_for_timeout(2200)
                    m1 = pg.evaluate("document.querySelector('.tl-month output')?.textContent.trim()"); pg.click("#play")
                    need(m1 != m0, f"[{lid} {w}x{h}] pressing Play steps the month ({m0} -> {m1})")
            ctx.close()
    b.close()
print("ALL OK" if not fails else f"FAILED {len(fails)}"); sys.exit(1 if fails else 0)
