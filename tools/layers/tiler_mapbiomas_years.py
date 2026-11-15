#!/usr/bin/env python3
"""MapBiomas conversion layers, ADDITIVE BY YEAR: one cumulative PMTiles file per year, like public/data-v4/oilpalm/{year}.pmtiles (mode "cumfile").
File Y shows every 0.001 deg cell whose first year (our rule, first year the class held two years in a row and was not the class in 2000) is <= Y;
colour = one colour per class, alpha = the cell's converted share (0-100 %, final value 2001-2023, the data has no per-year share), 8 alpha levels. It only grows with Y.
Same container and encoding as the other raster layers (Web Mercator, paletted PNG, pmtiles). Parents = mean of the 4 children.
usage: tiler_mapbiomas_years.py SRC_DIR OUT_DIR NPROC CLASS(palm|pulp|mine) [ZMAX=10]   -> OUT_DIR/<class>_<year>.pmtiles, years 2001..2023"""
import sys, os, math, numpy as np, rasterio
from rasterio.warp import reproject, Resampling
from rasterio.transform import from_bounds
from multiprocessing import Pool
from pmtiles.writer import write
from pmtiles.tile import zxy_to_tileid, TileType, Compression
from png_encode import png_encode

W = 20037508.342789244
SRC, OUT, NP, CLS = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4]
ZMAX = int(sys.argv[5]) if len(sys.argv) > 5 else 10
BBOX = (93.0, -13.0, 144.0, 8.0)
JOBZ = ZMAX - 3
YEARS = list(range(2001, 2024))
LEVELS = 8
RGB = {"palm": (154, 95, 176), "pulp": (0, 157, 150), "mine": (147, 139, 56)}[CLS]   # one colour per class (mb_palette mid ramp colours; palm moved to purple so it differs from the Descals olive)
ALPHA = [0] + [round(255 * (0.25 + 0.75 * (i - 1) / (LEVELS - 1))) for i in range(1, LEVELS + 1)]   # level 1 = 25 % opaque ... level 8 = opaque


def tile_bounds(z, x, y):
    s = 2 * W / 2 ** z
    return -W + x * s, W - (y + 1) * s, -W + (x + 1) * s, W - y * s


def read(name, jx, jy):
    N = 2 ** (ZMAX - JOBZ) * 256 * 2
    dst = from_bounds(*tile_bounds(JOBZ, jx, jy), N, N)
    with rasterio.open(os.path.join(SRC, name)) as ds:
        arr = np.zeros((N, N), ds.dtypes[0])
        reproject(rasterio.band(ds, 1), arr, dst_transform=dst, dst_crs="EPSG:3857", resampling=Resampling.nearest, src_nodata=0, dst_nodata=0)
    return arr


def level(a):  # a = share 0..100 (float) -> level 0..8
    lv = np.zeros(a.shape, np.uint8)
    m = a >= 0.5
    lv[m] = np.clip(np.ceil(a[m] / 100 * LEVELS), 1, LEVELS).astype(np.uint8)
    return lv


def emit(z, x, y, a):   # a: (K,256,256) float32 share per year
    for k, yr in enumerate(YEARS):
        lv = level(a[k])
        if not lv.any(): continue
        d = f"{OUT}/tiles/{CLS}_{yr}/{z}/{x}"; os.makedirs(d, exist_ok=True)
        open(f"{d}/{y}.png", "wb").write(png_encode(lv, [(0, 0, 0)] + [RGB] * LEVELS, ALPHA))


def parent(tiles):
    par = {}
    for (x, y), a in tiles.items():
        p = par.setdefault((x // 2, y // 2), np.zeros((len(YEARS), 512, 512), np.float32))
        p[:, (y & 1) * 256:(y & 1) * 256 + 256, (x & 1) * 256:(x & 1) * 256 + 256] = a
    return {k: v.reshape(len(YEARS), 256, 2, 256, 2).mean(axis=(2, 4)) for k, v in par.items()}


def job(args):
    jx, jy = args
    year = read(f"{CLS}_year.tif", jx, jy)
    if not (year > 0).any(): return {}
    frac = read(f"{CLS}_frac.tif", jx, jy).astype(np.float32)
    n = 2 ** (ZMAX - JOBZ); K = len(YEARS)
    agg = lambda x: x.reshape(x.shape[0] // 2, 2, x.shape[1] // 2, 2).sum(axis=(1, 3)) / 4
    full = np.zeros((K, n * 256, n * 256), np.float32)
    for k, yr in enumerate(YEARS):
        full[k] = agg(np.where((year > 0) & (year <= yr), frac, 0))
    lvl = {}
    for i in range(n):
        for j in range(n):
            t = full[:, i * 256:(i + 1) * 256, j * 256:(j + 1) * 256]
            if (t >= 0.5).any(): lvl[(jx * n + j, jy * n + i)] = t.copy()
    del full, year, frac
    for z in range(ZMAX, JOBZ - 1, -1):
        for (x, y), a in lvl.items(): emit(z, x, y, a)
        if z == JOBZ: break
        lvl = parent(lvl)
    return lvl


def pack(yr):
    name = f"{CLS}_{yr}"; root = f"{OUT}/tiles/{name}"; items = []
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
                   {"name": f"MapBiomas Indonesia C4 v2 {CLS} up to {yr}", "description": "derived from MapBiomas Indonesia Collection 4 v2 (CC-BY-SA): cells whose first year by our rule is <= year; alpha = converted share", "format": "png",
                    "attribution": "MapBiomas Indonesia Collection 4 v2 (CC-BY-SA)"})
    os.system(f"rm -rf '{root}'")
    return name, len(items), os.path.getsize(out)


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True); n = 2 ** JOBZ
    mx = lambda lon: (lon + 180) / 360 * n
    my = lambda lat: (1 - math.log(math.tan(math.radians(lat)) + 1 / math.cos(math.radians(lat))) / math.pi) / 2 * n
    cand = [(jx, jy) for jx in range(int(mx(BBOX[0])), int(mx(BBOX[2])) + 1) for jy in range(int(my(BBOX[3])), int(my(BBOX[1])) + 1)]
    print(f"{CLS} ZMAX={ZMAX} jobs={len(cand)}", flush=True)
    top = {}
    with Pool(NP) as p:
        for i, r in enumerate(p.imap_unordered(job, cand)):
            top.update(r)
            if i % 20 == 0: print("jobs done", i + 1, "/", len(cand), flush=True)
    lvl = top
    for z in range(JOBZ - 1, -1, -1):
        lvl = parent(lvl)
        for (x, y), a in lvl.items(): emit(z, x, y, a)
    res = []
    with Pool(min(NP, 8)) as p:
        for r in p.imap_unordered(pack, YEARS): res.append(r)
    for r in sorted(res): print("packed", r)
    print("TOTAL_BYTES", sum(r[2] for r in res), "files", len(res), flush=True)
