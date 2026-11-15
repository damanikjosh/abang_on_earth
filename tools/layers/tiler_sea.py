#!/usr/bin/env python3
"""Raster tiler for the map's PMTiles layers:
pyramid z0-8 only (max zoom 8 = ~600 m pixels), density levels 63 (z<=6) / 15 (z7) / 7 (z8), dithered rounding, parents = mean of the 4 children,
palette cut to the levels in use (png_encode.py). Source = the 30 m (or 124 m) rasters, so the whole region is built in one pass.
usage: tiler_sea.py LAYER OUTDIR NPROC BBOX lon0,lat0,lon1,lat1 SRC_GLOB
LAYER: burn  (annual burned mask GeoTIFF, uint8/uint16, > 0 = burned; one SRC file = one output named after it)
       loss  (uint8 lossyear code 1..25 where tree cover 2000 >= 30; cumulative, one file per year 2001-2025)
       palm  (Descals uint16 planting year, cumulative 1989..2021)
       peat  (CIFOR v2.1 uint8, 1 = peat; one static file)
       drivers (uint8 class 1..7 on the 0.01 deg grid from make_drivers_class.py; seven non-cumulative class files class1..class7)
env TILER_ZMAX = maximum zoom (default 8; drivers uses 9 because its cells are ~1.1 km)"""
import sys, os, glob, io, math, numpy as np, rasterio
from rasterio.warp import reproject, Resampling, transform_bounds
from rasterio.transform import from_bounds
from multiprocessing import Pool
from pmtiles.writer import write
from pmtiles.tile import zxy_to_tileid, TileType, Compression
from png_encode import png_encode

W = 20037508.342789244
LAYER, OUT, NP = sys.argv[1], sys.argv[2], int(sys.argv[3])
BBOX = [float(v) for v in sys.argv[4].split(",")]
SRC = sys.argv[5]
ZMAX = int(os.environ.get("TILER_ZMAX", 8)); JOBZ = 5
CUM = True; TMF = False; ERA = None
if LAYER == "loss":
    YEARS = list(range(2001, 2026)); NAMES = [str(y) for y in YEARS]; SRC_M = 27.8; RGB = (194, 65, 12)
    def code(a): return a.astype(np.int64)
elif LAYER == "palm":
    YEARS = list(range(1989, 2022)); NAMES = [str(y) for y in YEARS]; SRC_M = 30.0; RGB = (122, 139, 60)
    def code(a):
        c = a.astype(np.int64) - 1988
        c[(c < 1) | (c > 33)] = 0
        return c
elif LAYER == "peat":
    YEARS = [0]; NAMES = ["peat"]; SRC_M = 124.0; RGB = (107, 74, 43)
    def code(a): return (a == 1).astype(np.int64)
elif LAYER == "burn":   # one annual burned mask per source file (burn_{year}.tif, 1 = burned); the file name's year names the output
    YEARS = [0]; NAMES = [os.path.basename(SRC).replace("*", "").replace(".tif", "").strip("_")] if "*" not in os.path.basename(SRC) else ["burn"]; SRC_M = 463.3; RGB = (200, 30, 70)
    def code(a): return (a > 0).astype(np.int64)
elif LAYER in ("tmfdef", "tmfdeg", "tmfplant"):   # JRC TMF (v1_2025): first deforestation / degradation year (cumulative, 1984-1990 lumped into 1990), static plantation class 41
    SRC_M = 30.0; TMF = True
    if LAYER == "tmfplant":
        YEARS = [0]; NAMES = ["plantation"]; RGB = (190, 70, 140); ERA = None
        def code(a): return (a == 41).astype(np.int64)
    else:
        YEARS = list(range(1990, 2026)); ERA = YEARS.index(1999)
        NAMES = [str(y) for y in (YEARS if False else ([1990, 1995] + list(range(2000, 2026, 5)) if LAYER == "tmfdef" else [1990] + list(range(2000, 2026, 5))))]
        RGB, RGB_PRE = ((230, 160, 30), (91, 58, 140)) if LAYER == "tmfdef" else ((30, 120, 150), (120, 190, 210))
        def code(a):
            c = np.clip(a.astype(np.int64) - 1989, 1, 36); c[(a < 1984) | (a > 2025)] = 0
            return c
elif LAYER == "l2p":
    YEARS = [1, 2, 3, 4, 5, 6]; NAMES = [f"class{i}" for i in YEARS]; SRC_M = 30.0; CUM = False
    RGBS = {1: (227, 26, 28), 2: (253, 141, 60), 3: (254, 204, 92), 4: (65, 182, 196), 5: (34, 94, 168), 6: (123, 50, 148)}
    def code(a): return a.astype(np.int64)
elif LAYER == "drivers":   # Sims et al. 2025 drivers of forest loss, 7 classes, one raster per class (colours: see layers.json legend)
    YEARS = [1, 2, 3, 4, 5, 6, 7]; NAMES = [f"class{i}" for i in YEARS]; SRC_M = 1113.2; CUM = False
    RGBS = {1: (136, 204, 238), 2: (51, 34, 136), 3: (127, 191, 123), 4: (68, 170, 153), 5: (85, 85, 85), 6: (187, 187, 187), 7: (153, 112, 171)}   # cool + neutral set, no yellow/orange/red/brown (the fire layers own those); min dE 10.9 under protan/deutan/tritan
    def code(a): return a.astype(np.int64)
else: raise SystemExit("layer?")
if LAYER not in ("l2p", "drivers"): RGBS = {k: RGB for k in range(len(YEARS))}
TMFL = 16   # TMF levels at every zoom (as the live TMF files: palette index up to 2 x 16 + 1 with the pre-2000 era offset)
K = len(YEARS)
F = max(1, math.ceil(2 * W / 2 ** ZMAX / 256 / SRC_M)); N = 256 * F
# levels by zoom yearly loss/palm are re-quantised to z7 15 / z8 7; peat, burned and loss-to-palm keep the v1 levels z7 31 / z8 15
LZ = (lambda z: 63 if z <= 6 else 15 if z == 7 else 7) if LAYER in ("loss", "palm") else (lambda z: 63 if z <= 6 else 31 if z == 7 else 15)
SRC_NODATA = None

def tile_bounds(z, x, y):
    s = 2 * W / 2 ** z
    return -W + x * s, W - (y + 1) * s, -W + (x + 1) * s, W - y * s

_files = None; _ds = {}
def files():
    global _files
    if _files is None:
        _files = []
        for f in sorted(glob.glob(SRC)):
            with rasterio.open(f) as d: _files.append((f, d.bounds))
    return _files

def write_tile_tmf(k, z, x, y, f16, pre):   # v3 encoding of the live TMF files: rint (no dither), a non-zero share is lifted to level 1 only at max zoom; era colour where the pre-2000 share >= half
    q = np.rint(f16.astype(np.float32) / 65535 * TMFL).astype(np.int64)
    if z == ZMAX: q[(q == 0) & (f16 > 0)] = 1
    if not q.any(): return
    L = TMFL; al = [round(255 * i / L) for i in range(L + 1)]
    if pre is not None:
        era = (pre.astype(np.int32) * 2 >= f16.astype(np.int32)); q = q + era.astype(np.int64) * (L + 1)
        rgb = [(0, 0, 0)] + [RGB] * L + [(0, 0, 0)] + [RGB_PRE] * L; al = al + al
    else: rgb = [(0, 0, 0)] + [RGB] * L
    d = f"{OUT}/tiles/{NAMES[k]}/{z}/{x}"; os.makedirs(d, exist_ok=True)
    open(f"{d}/{y}.png", "wb").write(png_encode(q.astype(np.uint8), rgb, al))

def write_tile(k, z, x, y, f16):
    L = LZ(z); u = np.random.default_rng((z * 1000003 + x) * 1000003 + y + k).random(f16.shape, dtype=np.float32)
    q = np.minimum(np.floor(f16.astype(np.float32) / 65535 * L + u), L).astype(np.int64)   # dithered rounding: unbiased, sparse loss keeps its true mean
    if not q.any(): return
    d = f"{OUT}/tiles/{NAMES[k]}/{z}/{x}"; os.makedirs(d, exist_ok=True)
    rgb = RGBS[YEARS[k] if LAYER in ("l2p", "drivers") else k]
    open(f"{d}/{y}.png", "wb").write(png_encode(q.astype(np.uint8), [(0, 0, 0)] + [rgb] * L, [round(255 * i / L) for i in range(L + 1)]))

def tile_fracs(arr):    # N x N codes -> (K,256,256) uint16 fraction per file (cumulative over codes for loss/palm, per class for l2p)
    c = code(arr).reshape(256, F, 256, F).transpose(0, 2, 1, 3).reshape(65536, F * F)
    ids = (np.arange(65536, dtype=np.int64)[:, None] * (K + 1) + c).ravel()
    cnt = np.bincount(ids, minlength=65536 * (K + 1)).reshape(65536, K + 1)[:, 1:]
    cum = (np.cumsum(cnt, axis=1) if CUM else cnt) / float(F * F)
    return np.rint(cum.T.reshape(K, 256, 256) * 65535).astype(np.uint16)

def parent(tiles):
    par = {}
    for (x, y), a in tiles.items():
        p = par.setdefault((x // 2, y // 2), np.zeros((K, 512, 512), np.uint16))
        p[:, (y & 1) * 256:(y & 1) * 256 + 256, (x & 1) * 256:(x & 1) * 256 + 256] = a
    return {k: np.rint(v.reshape(K, 256, 2, 256, 2).astype(np.float32).mean(axis=(2, 4))).astype(np.uint16) for k, v in par.items()}

OUTY = {"tmfdef": [1990, 1995] + list(range(2000, 2026, 5)), "tmfdeg": [1990] + list(range(2000, 2026, 5))}
def emit(z, x, y, a):
    if not TMF:
        for k in range(K): write_tile(k, z, x, y, a[k])
        return
    if LAYER == "tmfplant": write_tile_tmf(0, z, x, y, a[0], None); return
    for i, yr in enumerate(OUTY[LAYER]): write_tile_tmf(i, z, x, y, a[YEARS.index(yr)], a[ERA])

def job(t):
    jx, jy = t; n = 2 ** (ZMAX - JOBZ); lvl = {}
    for cx in range(jx * n, jx * n + n):
        for cy in range(jy * n, jy * n + n):
            b = tile_bounds(ZMAX, cx, cy)
            ll = transform_bounds("EPSG:3857", "EPSG:4326", *b)
            if ll[2] < BBOX[0] or ll[0] > BBOX[2] or ll[3] < BBOX[1] or ll[1] > BBOX[3]: continue
            arr = None
            for f, fb in files():
                if fb.right < ll[0] or fb.left > ll[2] or fb.top < ll[1] or fb.bottom > ll[3]: continue
                if f not in _ds: _ds[f] = rasterio.open(f)
                tmp = np.zeros((N, N), np.uint16)
                reproject(rasterio.band(_ds[f], 1), tmp, dst_transform=from_bounds(*b, N, N), dst_crs="EPSG:3857",
                          resampling=Resampling.nearest, **({"src_nodata": 0, "dst_nodata": 0} if _ds[f].nodata is None else {"src_nodata": None, "dst_nodata": None}))
                # a source with its own nodata (CIFOR peat: 16 = no data) is read as plain values (code() then selects 1 = peat); passing nodata 16 with dst 0 filled whole tiles with 1
                arr = tmp if arr is None else np.maximum(arr, tmp)
            if arr is None or not (code(arr) > 0).any(): continue
            lvl[(cx, cy)] = tile_fracs(arr)
    for z in range(ZMAX, JOBZ - 1, -1):
        for (x, y), a in lvl.items():
            emit(z, x, y, a)
        if z == JOBZ: break
        lvl = parent(lvl)
    return lvl

def pack(name):
    root = f"{OUT}/tiles/{name}"; items = []
    if not os.path.isdir(root): return name, 0, 0
    for z in os.listdir(root):
        for x in os.listdir(f"{root}/{z}"):
            for f in os.listdir(f"{root}/{z}/{x}"): items.append((zxy_to_tileid(int(z), int(x), int(f[:-4])), f"{root}/{z}/{x}/{f}", int(z)))
    items.sort(); out = f"{OUT}/{name}.pmtiles"
    with write(out) as w:
        for tid, p, z in items: w.write_tile(tid, open(p, "rb").read())
        b = BBOX; zs = [i[2] for i in items]
        w.finalize({"tile_type": TileType.PNG, "tile_compression": Compression.NONE, "min_zoom": min(zs), "max_zoom": max(zs),
                    "min_lon_e7": int(b[0] * 1e7), "min_lat_e7": int(b[1] * 1e7), "max_lon_e7": int(b[2] * 1e7), "max_lat_e7": int(b[3] * 1e7), "center_zoom": 5,
                    "center_lon_e7": int((b[0] + b[2]) / 2 * 1e7), "center_lat_e7": int((b[1] + b[3]) / 2 * 1e7)},
                   {"name": f"{LAYER} {name}", "description": f"alpha = share of area; levels by zoom (see LZ), max zoom 8 (compressed recipe)", "format": "png"})
    os.system(f"rm -rf {root}")
    return name, len(items), os.path.getsize(out)

if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True); n = 2 ** JOBZ; cand = []
    mx = lambda lon: (lon + 180) / 360 * n
    my = lambda lat: (1 - math.log(math.tan(math.radians(lat)) + 1 / math.cos(math.radians(lat))) / math.pi) / 2 * n
    for jx in range(max(0, int(mx(BBOX[0])) - 1), min(n, int(mx(BBOX[2])) + 2)):
        for jy in range(max(0, int(my(BBOX[3])) - 1), min(n, int(my(BBOX[1])) + 2)):
            ll = transform_bounds("EPSG:3857", "EPSG:4326", *tile_bounds(JOBZ, jx, jy))
            if ll[2] < BBOX[0] or ll[0] > BBOX[2] or ll[3] < BBOX[1] or ll[1] > BBOX[3]: continue
            if any(not (fb.right < ll[0] or fb.left > ll[2] or fb.top < ll[1] or fb.bottom > ll[3]) for _, fb in files()): cand.append((jx, jy))
    print(f"F={F} N={N} jobs={len(cand)} files={len(files())}", flush=True)
    top = {}
    with Pool(NP) as p:
        for i, r in enumerate(p.imap_unordered(job, cand)):
            top.update(r)
            if i % 10 == 0: print("jobs done", i + 1, "/", len(cand), flush=True)
    lvl = top
    for z in range(JOBZ - 1, -1, -1):
        lvl = parent(lvl)
        for (x, y), a in lvl.items():
            emit(z, x, y, a)
    res = []
    with Pool(min(NP, 8)) as p:
        for r in p.imap_unordered(pack, NAMES): res.append(r); print("packed", r, flush=True)
    print("TOTAL_BYTES", sum(r[2] for r in res), "max", max(r[2] for r in res), "files", len(res), flush=True)
