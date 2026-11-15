#!/usr/bin/env python3
"""What cleared forest became: masked class raster from the Sims et al. 2025 forest-loss drivers map.
Source (CC BY 4.0, Zenodo 10.5281/zenodo.19485190, v1.3): 0.01 deg (~1.1 km) grid, band 1 = class 1..7, 255 = nothing. One class per cell for 2001-2025.
MASK RULE: a cell keeps its class only where Hansen/UMD GFC v1.13 (2025) shows forest loss: >= MIN_SHARE of the cell's 40 x 40 30-m pixels have lossyear 1..25.
(0.5 % = the source's own candidate-cell threshold.) So the layer never paints a cell where our forest-loss layer has nothing to show.
usage: make_drivers_class.py DRIVERS_TIF HANSEN_LOSSYEAR_DIR OUT_TIF OUT_STATS_JSON [MIN_SHARE=0.005]
Output: uint8 GeoTIFF, same 0.01 deg grid cropped to BBOX (the footprint of the other raster layers), values 1..7 or 0 = nothing."""
import sys, glob, json, numpy as np, rasterio
from rasterio.windows import from_bounds, Window
from rasterio.transform import from_origin
BBOX = (92.0, -11.5, 141.5, 29.0)   # lon0, lat0, lon1, lat1: header bounds of public/data-v4/forest-loss/*.pmtiles
CLASSES = {1: "Permanent agriculture", 2: "Hard commodities", 3: "Shifting cultivation", 4: "Logging", 5: "Wildfire", 6: "Settlements & infrastructure", 7: "Other natural disturbances"}
def main(src, hdir, out, stats_out, min_share=0.005):
    d = rasterio.open(src); assert d.transform.a == 0.01 and d.nodata == 255
    w = from_bounds(*BBOX, d.transform).round_offsets().round_lengths(); H, W = int(w.height), int(w.width)
    cls = d.read(1, window=w); x0, y0 = int(w.col_off), int(w.row_off)   # grid column / row of the window's corner
    cnt = np.zeros((H, W), np.int32)                                       # number of 30 m pixels with loss, per 1 km cell
    for f in sorted(glob.glob(hdir + "/*lossyear*.tif")):
        with rasterio.open(f) as h:
            assert h.shape == (40000, 40000) and abs(h.transform.a - 0.00025) < 1e-9
            L, T = h.transform.c, h.transform.f
            gx, gy = round((L + 180) / 0.01), round((84 - T) / 0.01)         # this tile's corner on the drivers grid (cells)
            r0, r1 = max(gy, y0), min(gy + 1000, y0 + H); c0, c1 = max(gx, x0), min(gx + 1000, x0 + W)
            if r0 >= r1 or c0 >= c1: continue
            a = h.read(1, window=Window((c0 - gx) * 40, (r0 - gy) * 40, (c1 - c0) * 40, (r1 - r0) * 40))
            cnt[r0 - y0:r1 - y0, c0 - x0:c1 - x0] = ((a > 0) & (a <= 25)).reshape(r1 - r0, 40, c1 - c0, 40).sum(axis=(1, 3))
    share = cnt / 1600.0
    keep = (cls >= 1) & (cls <= 7) & (share >= min_share)
    res = np.where(keep, cls, 0).astype(np.uint8)
    st = {"bbox": BBOX, "min_share": min_share, "cells_with_class": int(((cls >= 1) & (cls <= 7)).sum()), "cells_kept": int(keep.sum()),
          "cells_dropped_no_hansen_loss": int(((cls >= 1) & (cls <= 7) & ~keep).sum()),
          "hansen_loss_cells_without_class": int(((share >= min_share) & ~((cls >= 1) & (cls <= 7))).sum()),
          "by_class": {str(k): {"name": v, "with_class": int((cls == k).sum()), "kept": int((res == k).sum())} for k, v in CLASSES.items()},
          "dropped_share_quantiles": {}}
    dr = share[(cls >= 1) & (cls <= 7) & ~keep]
    if dr.size: st["dropped_share_quantiles"] = {q: float(np.quantile(dr, q)) for q in (0.5, 0.9, 0.99)}
    with rasterio.open(out, "w", driver="GTiff", dtype="uint8", count=1, width=W, height=H, crs="EPSG:4326", compress="lzw",
                       transform=from_origin(BBOX[0], BBOX[3], 0.01, 0.01), nodata=0) as o: o.write(res, 1)
    json.dump(st, open(stats_out, "w"), indent=1); print(json.dumps(st, indent=1))
if __name__ == "__main__":
    a = sys.argv; main(a[1], a[2], a[3], a[4], float(a[5]) if len(a) > 5 else 0.005)
