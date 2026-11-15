"""every layer answers real tile requests with HTTP 206 (Range), at three places.
  uv run --with pmtiles python scripts/check_tiles.py [site_url]          default http://127.0.0.1:4801/ ; also works on https://abang.earth/
Reads data-version.json -> data folder, then for each layer in layers.json (plus the four fire layers, month 2015-09) and each of
three places per country (Indonesia, Malaysia, Brunei, Singapore): reads the PMTiles header, directory and one tile through the pmtiles reader. Every network read is a Range request;
all must answer 206. Prints "206 <bytes> <layer> <place> z<zoom>" per tile and PASS/FAIL. Exit 1 on any non-206 or a layer with no tile anywhere."""
import sys, json, math, time, urllib.request, urllib.error
from pmtiles.reader import Reader

SITE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:4801/").rstrip("/") + "/"
PLACES = {"riau": (101.8, 0.5), "c-kalimantan": (113.5, -1.9), "papua": (138.5, -4.5),                       # Indonesia
          "kuala-lumpur": (101.7, 3.1), "sabah": (117.0, 5.2), "sarawak": (112.0, 2.4),                        # Malaysia (tier B)
          "brunei-muara": (114.9, 4.9), "belait": (114.4, 4.3), "temburong": (115.2, 4.6),                      # Brunei
          "sg-central": (103.82, 1.35), "sg-west": (103.7, 1.34), "sg-east": (103.94, 1.35),                   # Singapore
          "bangkok": (100.5, 13.75), "chiang-mai": (98.99, 18.79), "surat-thani": (99.3, 9.1),                  # Thailand (tier A)
          "yangon": (96.15, 16.8), "shan": (97.5, 21.5), "tanintharyi": (98.6, 12.4),                           # Myanmar
          "vientiane": (102.6, 17.97), "luang-prabang": (102.14, 19.88), "savannakhet": (104.75, 16.55),        # Laos
          "phnom-penh": (104.92, 11.56), "tonle-sap": (104.0, 12.9), "mondulkiri": (107.1, 12.45),              # Cambodia
          "hanoi": (105.85, 21.03), "ho-chi-minh": (106.7, 10.78), "quang-nam": (108.2, 15.6),                  # Vietnam
          "manila": (121.0, 14.6), "agusan": (125.8, 8.5), "palawan": (118.7, 9.8),                             # Philippines
          "dili": (125.57, -8.55), "baucau": (126.45, -8.47), "suai": (125.25, -9.3)}                           # Timor-Leste
def get(url, rng=None):
    req = urllib.request.Request(url, headers={"Range": rng} if rng else {})
    with urllib.request.urlopen(req, timeout=60) as r: return r.status, r.read()
def jget(path): return json.loads(get(SITE + path)[1])
def tile_xy(lon, lat, z):
    n = 2 ** z; x = int((lon + 180) / 360 * n); y = int((1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n); return x, y

ptr = jget(f"data-version.json?_={int(time.time())}"); base = SITE + ptr["base"]
import os
if os.environ.get("DATA_DIR"): ptr = {"base": os.environ["DATA_DIR"].rstrip("/") + "/"}; base = SITE + ptr["base"]  # check a folder the pointer does not name yet
print("pointer:", ptr)
layers = jget(ptr["base"] + "layers.json")["layers"]; man = jget(ptr["base"] + "manifest.json")
files = []  # (name, path)
import re, pathlib
_lg = (pathlib.Path(__file__).resolve().parent.parent / "src/layergroups.ts").read_text()
UNLISTED = {i for n in ("HIDDEN_ROWS", "REMOVED_ROWS") for m in [re.search(n + r"[^=]*=\s*\[([^\]]*)\]", _lg)] if m for i in re.findall(r'"([^"]+)"', m.group(1))}  # rows the app does not list: their tiles are not shipped
for d in layers:
    if d["id"] in UNLISTED or d.get("placeholder"): continue
    av = d.get("available") or []
    if d["mode"] == "static": key = "s"
    elif d["mode"] == "class": key = "c1"
    else: key = sorted(av)[-1] if av else str(d.get("max", 2019))
    p = d["path"].replace("{year}", key).replace("{month}", key).replace("{class}", key.lstrip("c") if key.startswith("c") else key)
    files.append((d["id"], p))
for d in man["fire_layers"]["layers"]:
    if not d.get("placeholder") and d["id"] in ("modis", "viirs", "clrm", "clrv"):
        for nm, pth in ([("fire-" + d["id"], d["path"])] if d.get("path") else [("fire-" + d["id"] + "-" + c["label"].lower(), c["path"]) for c in d.get("classes", []) if c.get("path")]): files.append((nm, pth.replace("{month}", "2015-09")))
fails, nlines = [], 0
for name, path in files:
    url = base + path; st = []
    def gb(off, ln, url=url):
        s, b = get(url, f"bytes={off}-{off + ln - 1}"); st.append(s); return b
    try:
        rd = Reader(gb); h = rd.header(); found = 0
        for place, (lon, lat) in PLACES.items():
            data = None
            for z in range(min(h["max_zoom"], 7), 2, -1):
                x, y = tile_xy(lon, lat, z); data = rd.get(z, x, y)
                if data: break
            if data: found += 1; print(f"206 {len(data):>7} {name:<10} {place:<13} z{z} (file max_zoom {h['max_zoom']})"); nlines += 1
            else: print(f"---   no tile {name:<10} {place:<13} (nothing mapped there)")
        bad = [s for s in st if s != 206]
        if bad or found == 0: fails.append(f"{name}: statuses {sorted(set(st))}, tiles found {found}")
    except Exception as e: fails.append(f"{name}: {e}")
print(f"{len(files)} files, {nlines} tiles read, all reads 206: {not fails}")
print("PASS" if not fails else "FAIL " + "; ".join(fails)); sys.exit(1 if fails else 0)
