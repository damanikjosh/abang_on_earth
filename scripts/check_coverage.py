"""Tier B: which raster layers have data in which country? Samples random points inside each country's regions, reads the
tile under each point from the layer's PMTiles file (latest year / class 1 / static) and reports, per layer and country:
  tile = share of points whose tile exists in the file, data = share of points whose pixel has alpha > 0 (something drawn).
usage: [YEAR=2015] uv run --with pmtiles,shapely,pillow,numpy python scripts/check_coverage.py DATA_DIR REGIONS.geojson [N=300] [OUT.json]
A tile that is absent is "no tile in the file": for loss / peat / burned that means nothing there to draw (global datasets), for Descals oil palm it can
mean "no data" (the dataset has holes); see data/*.json notes. This script only measures the files; the label text is decided in build_v3.py."""
import sys, io, json, math, random, os
import numpy as np
from PIL import Image
from shapely.geometry import shape, Point
from shapely.prepared import prep
from pmtiles.reader import Reader, MmapSource
from pmtiles.tile import Compression

ddir, regs = sys.argv[1], sys.argv[2]; N = int(sys.argv[3]) if len(sys.argv) > 3 else 300; out = sys.argv[4] if len(sys.argv) > 4 else None
random.seed(7)
by = {}
for f in json.load(open(regs))["features"]: by.setdefault(f["properties"].get("country", "IDN"), []).append(shape(f["geometry"]))
pts = {}
for c, gs in by.items():
    areas = [g.area for g in gs]; P = []
    while len(P) < N:
        g = random.choices(gs, areas)[0]; x0, y0, x1, y1 = g.bounds; p = Point(random.uniform(x0, x1), random.uniform(y0, y1))
        if g.contains(p): P.append((p.x, p.y))
    pts[c] = P
def txy(lon, lat, z):
    n = 2 ** z; fx = (lon + 180) / 360 * n; fy = (1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n
    return int(fx), int(fy), int((fx % 1) * 256), int((fy % 1) * 256)
lf = json.load(open(os.path.join(ddir, "layers.json")))["layers"]
res = {}
for d in lf:
    if d.get("placeholder"): continue
    av = sorted(d.get("available") or [])
    key = "s" if d["mode"] == "static" else ("c1" if d["mode"] == "class" else (av[-1] if av else str(d.get("max"))))
    if d["mode"] == "year" and os.environ.get("YEAR") in av: key = os.environ["YEAR"]  # burned area is sparse in a calm year; YEAR=2015 shows the haze year
    path = d["path"].replace("{year}", key).replace("{month}", key).replace("{class}", key.lstrip("c") if key.startswith("c") else key)
    fn = os.path.join(ddir, path)
    with open(fn, "rb") as fh:
        r = Reader(MmapSource(fh)); h = r.header(); z = min(8, h["max_zoom"]); cache = {}; res[d["id"]] = {"file": path, "zoom": z}
        for c, P in pts.items():
            tiles = data = 0
            for lon, lat in P:
                x, y, px, py = txy(lon, lat, z)
                if (x, y) not in cache:
                    b = r.get(z, x, y)
                    if b is not None and h["tile_compression"] == Compression.GZIP:
                        import gzip; b = gzip.decompress(b)
                    cache[(x, y)] = None if b is None else np.asarray(Image.open(io.BytesIO(b)).convert("RGBA"))
                a = cache[(x, y)]
                if a is not None:
                    tiles += 1; data += int(a[py, px, 3] > 0)
            res[d["id"]][c] = {"tile": round(tiles / N, 3), "data": round(data / N, 3)}
        print(d["id"], path, {c: res[d["id"]][c] for c in pts}, flush=True)
if out: json.dump(res, open(out, "w"), indent=1)
